"""fix-state-restore（#72）：状态机读盘恢复的回归测试.

缺陷形态：落盘对象是 `ThreadSafeDict`（非 `dict` 子类），旧守卫恒假——
`load_state_machines` 对自家写出的文件**实际什么都没加载**，`have_loaded()`
却声称已加载。本文件把 issue 的最小复现固化为用例，并覆盖 worker 的真实
读盘路径（pickle 临时文件），缺陷正是从这条无人验证的路径上长期存活的。
"""

import copy
import pickle

import pytest

from zoo_framework.core.container import framework_container
from zoo_framework.statemachine import StateMachineManager
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict
from zoo_framework.workers.state_machine_work import StateMachineWorker


@pytest.fixture
def fresh_manager():
    """等价于新进程：进程级单例清空后返回全新实例."""
    framework_container().reset()
    manager = StateMachineManager()
    yield manager
    framework_container().reset()


class TestLoadGuard:
    def test_thread_safe_dict_roundtrip_restores_state(self, fresh_manager):
        """issue 最小复现：ThreadSafeDict 落盘形态必须真正恢复."""
        manager = StateMachineManager()
        manager.set_state("s", "k", "v")
        data = pickle.loads(pickle.dumps(manager.get_state_machines()))
        assert isinstance(data, ThreadSafeDict)  # 缺陷前提：落盘形态不是 dict

        framework_container().reset()
        restored = StateMachineManager()
        restored.load_state_machines(data)

        assert restored.have_loaded() is True
        assert restored.get_state("s", "k") == "v", "状态必须真正恢复，而非仅声称已加载"
        assert len(restored._state_scope_map) == 1

    def test_plain_dict_is_wrapped_and_restored(self, fresh_manager):
        """普通 dict 入参兼容旧文件/手工注入，包成 ThreadSafeDict 后 has_key 可用."""
        fresh_manager.load_state_machines({"s": copy.deepcopy(_scope())})
        assert isinstance(fresh_manager.get_state_machines(), ThreadSafeDict)
        assert fresh_manager.get_state("s", "k") == "v"

    def test_unknown_type_raises_instead_of_silently_ignoring(self, fresh_manager):
        """未知类型明确拒绝——静默忽略正是旧缺陷（假象已加载）的同族形态."""
        with pytest.raises(TypeError, match="ThreadSafeDict"):
            fresh_manager.load_state_machines(["not", "a", "mapping"])
        assert fresh_manager.have_loaded() is False

    def test_none_means_no_content_to_restore(self, fresh_manager):
        """None：无可恢复内容，进入新状态并置 loaded（与 worker 各兜底分支一致）."""
        fresh_manager.load_state_machines(None)
        assert fresh_manager.have_loaded() is True
        assert len(fresh_manager.get_state_machines()) == 0


class TestWorkerLoadPath:
    """StateMachineWorker._load_state_machines 的真实读盘路径（缺陷存活处）."""

    def test_worker_loads_own_saved_file(self, fresh_manager, tmp_path, monkeypatch):
        from zoo_framework.params import StateMachineParams

        pickle_path = str(tmp_path / "state_machines.pkl")
        monkeypatch.setattr(StateMachineParams, "PICKLE_PATH", pickle_path)

        fresh_manager.set_state("scope-a", "key", "value")
        # 以 worker 的保存路径落盘（deepcopy + pickle，与 _save_state_machines 同形）
        with open(pickle_path, "wb") as f:
            pickle.dump(copy.deepcopy(fresh_manager.get_state_machines()), f)

        framework_container().reset()
        worker = StateMachineWorker()
        restored = StateMachineManager()
        worker._load_state_machines(restored)

        assert restored.have_loaded() is True
        assert restored.get_state("scope-a", "key") == "value", (
            "worker 读回必须真正恢复状态；旧实现此处为 None 且日志谎称成功"
        )

    def test_backup_recovery_path_also_restores(self, fresh_manager, tmp_path, monkeypatch):
        """损坏主文件 → _load_from_backup 的恢复同样落到真实状态（同一空操作链路）."""
        from zoo_framework.params import StateMachineParams

        pickle_path = str(tmp_path / "state_machines.pkl")
        monkeypatch.setattr(StateMachineParams, "PICKLE_PATH", pickle_path)

        fresh_manager.set_state("scope-b", "key", "backed-up")
        worker = StateMachineWorker()
        # 先有一份合法主文件（_create_backup 对不存在的主文件直接返回），再备份、再损坏
        with open(pickle_path, "wb") as f:
            pickle.dump(copy.deepcopy(fresh_manager.get_state_machines()), f)
        worker._create_backup(pickle_path)
        with open(pickle_path, "wb") as f:
            f.write(b"broken payload")  # 触发 UnpicklingError → 走备份

        framework_container().reset()
        restored = StateMachineManager()
        worker._load_state_machines(restored)

        assert restored.get_state("scope-b", "key") == "backed-up"


def _scope():
    """构造一个带初始节点的状态作用域（与 manager 内部形态一致）."""
    from zoo_framework.statemachine.state_scope import StateScope

    scope = StateScope()
    scope.set_state_node("k", "v")
    return scope
