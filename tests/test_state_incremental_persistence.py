"""add-state-query-index-and-incremental-persistence 原语 3：增量持久化与 TTL 淘汰.

覆盖 spec delta 的 ADDED 场景：未修改的作用域不被重写、增量落盘后在新进程语境读回
与整表落盘等价、未启用增量模式时行为与现状一致、过期作用域被淘汰且幂等、未配置 TTL
时不淘汰、落盘失败显式化（PersistenceError）；另覆盖 D2 的旧整表文件迁移路径。
"""

import copy
import os
import pickle
import time

import pytest

import zoo_framework.statemachine.state_scope as _state_scope_module
from zoo_framework.core.container import framework_container
from zoo_framework.core.persistence_scheduler import PersistenceError, PicklePersistenceStrategy
from zoo_framework.statemachine import StateMachineManager
from zoo_framework.statemachine.state_scope import StateScope
from zoo_framework.workers.state_machine_work import (
    StateMachineWorker,
    _scope_file_name,
)


@pytest.fixture
def incremental(tmp_path, monkeypatch):
    """启用增量持久化，picklePath 指向临时目录."""
    from zoo_framework.params import StateMachineParams

    directory = tmp_path / "state_dir"
    monkeypatch.setattr(StateMachineParams, "PICKLE_PATH", str(directory))
    monkeypatch.setattr(StateMachineParams, "INCREMENTAL_SAVE", True)
    return directory


@pytest.fixture
def recorded_saves(monkeypatch):
    """记录 PicklePersistenceStrategy.save 收到的每次 filepath."""
    saved: list[str] = []
    original = PicklePersistenceStrategy.save

    def record(self, data, filepath):
        saved.append(filepath)
        return original(self, data, filepath)

    monkeypatch.setattr(PicklePersistenceStrategy, "save", record)
    return saved


def _fresh_manager():
    """等价于新进程：清空进程级单例后返回全新 manager."""
    framework_container().reset()
    return StateMachineManager()


# =============================================================================
# 脏作用域记账（原语 3）
# =============================================================================


class TestDirtyAccounting:
    """写入成功才把该作用域标记为脏；未写 / 写失败 / 版本不匹配都不标记."""

    def test_only_written_scope_is_dirty(self):
        """Scenario（3.1）: 写入 scope A 后 A 为脏、仅预建的 B 不为脏."""
        manager = StateMachineManager()
        manager.create_scope("B")  # 预建但不写
        manager.set_state("A", "k", 1)

        assert manager.get_dirty_scopes() == {"A"}

    def test_failed_append_does_not_mark_dirty(self):
        """写失败（非 list 追加）不产生脏标记——"当且仅当被修改过"."""
        manager = StateMachineManager()
        manager.set_state("s", "k", 5)
        manager.clear_dirty_scopes()

        with pytest.raises(TypeError):
            manager.append_state("s", "k", 1)

        assert manager.get_dirty_scopes() == set()

    def test_cas_mismatch_does_not_mark_dirty_but_success_does(self):
        """CAS 版本不匹配未修改状态 → 不脏；匹配写入 → 脏."""
        manager = StateMachineManager()
        manager.set_state("s", "k", "v1")
        scope = manager.get_and_create_scope("s")
        stale = scope.get_state_node("k").get_version()
        manager.set_state("s", "k", "v2")
        manager.clear_dirty_scopes()

        assert manager.compare_and_set("s", "k", stale, "v3") is False
        assert manager.get_dirty_scopes() == set()

        current = scope.get_state_node("k").get_version()
        assert manager.compare_and_set("s", "k", current, "v4") is True
        assert manager.get_dirty_scopes() == {"s"}

    def test_remove_marks_scope_dirty(self):
        """删除也是一次修改——否则增量模式下被删的作用域不会同步落盘."""
        manager = StateMachineManager()
        manager.set_state("s", "k", "v")
        manager.clear_dirty_scopes()

        manager.remove_state("s", "k")

        assert manager.get_dirty_scopes() == {"s"}

    def test_load_clears_dirty(self):
        """整表替换恢复后不应残留待落盘的脏作用域."""
        manager = StateMachineManager()
        manager.set_state("s", "k", "v")
        assert manager.get_dirty_scopes() == {"s"}

        manager.load_state_machines({})

        assert manager.get_dirty_scopes() == set()


# =============================================================================
# last_modified 时间戳（原语 3 / TTL 基准）
# =============================================================================


class _FakeClock:
    """可控墙钟，替换 state_scope 模块的 time 引用."""

    def __init__(self, now: float = 1000.0):
        self.now = now

    def time(self) -> float:
        return self.now


class TestLastModified:
    """写入刷新 last_modified；随 scope 序列化；旧载荷缺字段兜底."""

    def test_write_refreshes_last_modified(self, monkeypatch):
        """Scenario（3.2）: 写入后时间戳被刷新，读不刷新."""
        clock = _FakeClock(1000.0)
        monkeypatch.setattr(_state_scope_module, "time", clock)
        manager = StateMachineManager()
        scope = manager.get_and_create_scope("s")
        assert scope.last_modified == 1000.0

        clock.now = 2000.0
        manager.set_state("s", "k", "v")

        assert scope.last_modified == 2000.0

    def test_pickle_roundtrip_preserves_last_modified(self):
        """TTL 需跨进程重启成立——时间戳必须随 scope 一起被 pickle."""
        scope = StateScope()
        scope.set_state_node("k", "v")

        restored = pickle.loads(pickle.dumps(scope))

        assert restored.last_modified == scope.last_modified
        assert restored.get_state_value("k") == "v"

    def test_legacy_payload_without_field_is_backfilled(self):
        """Scenario（3.2）: 反序列化旧存档（缺 last_modified）不抛错且有兜底值."""
        scope = StateScope()
        scope.set_state_node("k", "v")
        payload = scope.__getstate__()
        payload.pop("last_modified")  # 模拟本字段引入前的旧存档

        restored = StateScope.__new__(StateScope)
        restored.__setstate__(payload)

        assert restored.last_modified > 0


# =============================================================================
# 增量落盘（原语 3 / D2 每作用域文件）
# =============================================================================


class TestIncrementalSave:
    """只写脏作用域、读回等价、未启用时整表落盘."""

    def test_only_dirty_scope_rewritten(self, incremental, recorded_saves):
        """Scenario: 修改 A 后落盘只涉及 A，未修改的 B 不被重写."""
        manager = StateMachineManager()
        worker = StateMachineWorker()
        manager.set_state("A", "k", "a1")
        manager.set_state("B", "k", "b1")
        worker._save_state_machines(manager)

        a_file = str(incremental / _scope_file_name("A"))
        b_file = str(incremental / _scope_file_name("B"))
        b_bytes = (incremental / _scope_file_name("B")).read_bytes()

        # 无脏 → 零落盘（整表模式会重写全部）
        recorded_saves.clear()
        worker._save_state_machines(manager)
        assert recorded_saves == []

        manager.set_state("A", "k", "a2")
        recorded_saves.clear()
        worker._save_state_machines(manager)

        assert a_file in recorded_saves, "被修改的 A 未被重写"
        assert b_file not in recorded_saves, "未修改的 B 被重写了"
        assert (incremental / _scope_file_name("B")).read_bytes() == b_bytes

    def test_incremental_roundtrip_matches_whole_table(self, incremental):
        """Scenario: 增量模式写入若干作用域后，在新进程语境读回与整表等价."""
        manager = StateMachineManager()
        worker = StateMachineWorker()
        manager.set_state("A", "x", 1)
        manager.set_state("B", "y", 2)
        manager.set_state("A", "z", [1, 2])
        worker._save_state_machines(manager)

        fresh = _fresh_manager()
        StateMachineWorker()._load_state_machines(fresh)

        assert fresh.get_state("A", "x") == 1
        assert fresh.get_state("B", "y") == 2
        assert fresh.get_state("A", "z") == [1, 2]

    def test_disabled_keeps_whole_table_file(self, tmp_path, monkeypatch):
        """Scenario: 未启用增量 → 整表被写出，行为与合入前一致."""
        from zoo_framework.params import StateMachineParams

        path = tmp_path / "zooStates.pic"
        monkeypatch.setattr(StateMachineParams, "PICKLE_PATH", str(path))
        monkeypatch.setattr(StateMachineParams, "INCREMENTAL_SAVE", False)

        manager = StateMachineManager()
        worker = StateMachineWorker()
        manager.set_state("A", "k", "v")
        worker._save_state_machines(manager)

        assert os.path.isfile(str(path)), "未启用增量时未整表落盘"
        assert not os.path.isdir(str(path))
        assert not os.path.exists(str(path) + ".migrated.bak")
        with open(path, "rb") as f:
            data = pickle.load(f)
        assert data["A"].get_state_value("k") == "v"

    def test_migrates_legacy_whole_table_file(self, incremental):
        """Scenario（3.4）: 旧整表文件 → 目录布局，数据无丢失且原文件留档."""
        manager = StateMachineManager()
        manager.set_state("A", "k", "legacy")
        with open(str(incremental), "wb") as f:
            pickle.dump(copy.deepcopy(manager.get_state_machines()), f)
        assert os.path.isfile(str(incremental))

        fresh = _fresh_manager()
        StateMachineWorker()._load_state_machines(fresh)

        assert fresh.get_state("A", "k") == "legacy", "迁移过程丢失了数据"
        assert os.path.isdir(str(incremental))
        assert os.path.isfile(str(incremental) + ".migrated.bak"), "原文件未留档"

        # 目录布局可再次读回（等价）
        again = _fresh_manager()
        StateMachineWorker()._load_state_machines(again)
        assert again.get_state("A", "k") == "legacy"

    def test_save_failure_raises_persistence_error(self, tmp_path, monkeypatch):
        """Scenario（3.7）: 目标目录不可创建 → 显式 PersistenceError，不静默."""
        from zoo_framework.params import StateMachineParams

        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory", encoding="utf-8")
        monkeypatch.setattr(StateMachineParams, "PICKLE_PATH", str(blocker / "sub"))
        monkeypatch.setattr(StateMachineParams, "INCREMENTAL_SAVE", True)

        manager = StateMachineManager()
        manager.set_state("A", "k", "v")
        manager.clear_dirty_scopes()
        manager.set_state("A", "k", "v2")  # 保证有脏

        with pytest.raises(PersistenceError):
            StateMachineWorker()._save_state_machines(manager)

    def test_evicted_scope_files_removed(self, incremental, monkeypatch):
        """淘汰后增量模式清理其持久化文件与 manifest 条目."""
        from zoo_framework.params import StateMachineParams

        monkeypatch.setattr(StateMachineParams, "SCOPE_TTL_SECONDS", 60)
        manager = StateMachineManager()
        worker = StateMachineWorker()
        manager.set_state("A", "k", "v")
        manager.set_state("B", "k", "v")
        worker._save_state_machines(manager)
        a_file = incremental / _scope_file_name("A")
        assert a_file.exists()

        manager.get_and_create_scope("A").last_modified = time.time() - 1000
        worker._evict_expired_scopes(manager)

        assert manager.get_state("A", "k") is None
        assert not a_file.exists(), "淘汰后未清理持久化文件"

        fresh = _fresh_manager()
        StateMachineWorker()._load_state_machines(fresh)
        assert fresh.get_state("A", "k") is None
        assert fresh.get_state("B", "k") == "v"


# =============================================================================
# TTL 淘汰（原语 3）
# =============================================================================


class TestEviction:
    """按 last_modified 淘汰过期作用域；幂等；未配置 TTL 不淘汰."""

    def test_expired_scope_evicted_and_query_returns_none(self):
        """Scenario: 过期作用域被移除且按作用域查询返回空."""
        manager = StateMachineManager()
        manager.set_state("old", "k", "v")
        manager.set_state("new", "k", "v")
        manager.get_and_create_scope("old").last_modified = time.time() - 1000

        expired = manager.evict_expired_scopes(60)

        assert expired == ["old"]
        assert manager.get_state("old", "k") is None
        assert manager.get_state("new", "k") == "v"

    def test_eviction_is_idempotent(self):
        """Scenario: 重复淘汰不抛错（第二次为空操作）."""
        manager = StateMachineManager()
        manager.set_state("old", "k", "v")
        manager.get_and_create_scope("old").last_modified = time.time() - 1000

        assert manager.evict_expired_scopes(60) == ["old"]
        assert manager.evict_expired_scopes(60) == []

    def test_ttl_zero_never_evicts(self):
        """Scenario: 未配置 TTL（0）时不淘汰任何作用域."""
        manager = StateMachineManager()
        manager.set_state("keep", "k", "v")
        manager.get_and_create_scope("keep").last_modified = time.time() - 10**9

        assert manager.evict_expired_scopes(0) == []
        assert manager.evict_expired_scopes(None) == []
        assert manager.get_state("keep", "k") == "v"
