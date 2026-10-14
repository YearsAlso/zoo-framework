"""add-state-append-and-cas：状态层两条写路径原语（集合追加 + 条件写 CAS）.

覆盖 spec delta 的 ADDED 场景：集合键逐条追加且不重写既有元素、并发追加不丢更新、
基于节点版本的条件写原子生效且版本严格递增、节点版本可用于乐观并发控制，以及
既有 `set_state` 的整值替换语义不受影响。
"""

import threading
from itertools import pairwise

import pytest

import zoo_framework.statemachine.state_node as _state_node_module
from zoo_framework.statemachine import StateMachineManager
from zoo_framework.statemachine.state_node import StateNode
from zoo_framework.statemachine.state_node_type import StateNodeType


def _node(scope_obj, key):
    """取某键的底层 StateNode（测试用读取版本）."""
    return scope_obj.get_state_node(key)


class TestVersionMonotonic:
    """节点版本 MUST 在每次成功写入后严格递增（原语 4 的前提）."""

    def test_consecutive_writes_strictly_increase(self):
        """Scenario: 连续多次成功写入，版本严格递增."""
        node = StateNode(key="k", value="v0")
        versions = [node.get_version()]
        for i in range(1, 5):
            node.set_value(f"v{i}")
            versions.append(node.get_version())

        assert all(b > a for a, b in pairwise(versions)), versions

    def test_observer_payload_version_equals_written_version(self):
        """Scenario: 观察者载荷中的版本等于写入后的节点版本."""
        payloads: list[dict] = []
        node = StateNode(key="k", value="old")
        node.add_effect(lambda payload: payloads.append(dict(payload)))

        node.set_value("new")

        assert payloads == [{"value": "new", "version": node.get_version()}]

    def test_same_second_writes_still_strictly_increase(self, monkeypatch):
        """秒级时间戳不前进时，版本仍严格递增（防 ABA 假通过）."""
        monkeypatch.setattr(_state_node_module.time, "time", lambda: 1000.0)
        node = StateNode(key="k", value="old")

        node.set_value("a")
        v1 = node.get_version()
        node.set_value("b")
        v2 = node.get_version()

        assert v1 == 1001
        assert v2 == 1002
        assert v2 > v1

    def test_legacy_pickle_payload_normalized(self):
        """旧存档（同时含 version 与 _version）反序列化后 get_version 可读."""
        legacy_state = {
            "_effect_list": [],
            "_version": 100,
            "version": 250,
            "_is_top": False,
            "_parent": None,
            "_children": [],
            "_type": StateNodeType.string,
            "_value": "v",
            "key": "k",
        }
        node = StateNode.__new__(StateNode)
        node.__setstate__(legacy_state)

        assert node.get_version() == 250
        assert "version" not in node.__dict__


class TestAppend:
    """集合键追加（原语 1）."""

    def test_append_on_missing_key_creates_it(self):
        """Scenario: 对不存在的键追加自动以空集合为基."""
        sm = StateMachineManager()
        sm.append_state("s", "k", "X")

        assert sm.get_state("s", "k") == ["X"]

    def test_append_preserves_order(self):
        """Scenario: 逐条追加后按序读回全部元素."""
        sm = StateMachineManager()
        for item in ("A", "B", "C"):
            sm.append_state("s", "k", item)

        assert sm.get_state("s", "k") == ["A", "B", "C"]

    def test_append_does_not_rebuild_existing(self):
        """Scenario: 追加不重写既有元素（就地 append，非重建）."""
        sm = StateMachineManager()
        sm.append_state("s", "k", "A")
        original = sm.get_state("s", "k")

        sm.append_state("s", "k", "B")

        assert sm.get_state("s", "k") is original, "追加重建了集合，既有元素被替换"
        assert original == ["A", "B"]

    def test_append_is_not_idempotent(self):
        """重复追加产生多条元素；去重属调用方职责."""
        sm = StateMachineManager()
        sm.append_state("s", "k", "A")
        sm.append_state("s", "k", "A")

        assert sm.get_state("s", "k") == ["A", "A"]

    def test_append_to_non_list_raises_and_preserves_value(self):
        """Scenario: 对非集合值（整数）的键追加明确失败，原值不被覆盖."""
        sm = StateMachineManager()
        sm.set_state("s", "k", 5)

        with pytest.raises(TypeError):
            sm.append_state("s", "k", 1)

        assert sm.get_state("s", "k") == 5

    def test_append_to_dict_value_raises(self):
        """Scenario: 对 dict（子树）值键追加抛 TypeError，不覆盖原值."""
        sm = StateMachineManager()
        sm.set_state("s", "k", {"a": 1})

        with pytest.raises(TypeError):
            sm.append_state("s", "k", 2)

        assert sm.get_state("s", "k") == {"a": 1}

    def test_set_state_still_replaces_collection(self):
        """Scenario: 既有整值替换语义不受追加影响."""
        sm = StateMachineManager()
        sm.append_state("s", "k", "A")
        sm.append_state("s", "k", "B")

        sm.set_state("s", "k", ["Z"])

        assert sm.get_state("s", "k") == ["Z"]


class TestCompareAndSet:
    """条件写 CAS（原语 4）."""

    def test_cas_success_bumps_version(self):
        """Scenario: 版本匹配时写入成功且版本递增."""
        sm = StateMachineManager()
        sm.set_state("s", "k", "v1")
        scope = sm.get_and_create_scope("s")
        v = _node(scope, "k").get_version()

        assert sm.compare_and_set("s", "k", v, "v2") is True
        assert sm.get_state("s", "k") == "v2"
        assert _node(scope, "k").get_version() > v

    def test_cas_stale_version_does_not_write(self):
        """Scenario: 过期版本时写入不发生，原值保留."""
        sm = StateMachineManager()
        sm.set_state("s", "k", "v1")
        scope = sm.get_and_create_scope("s")
        v1 = _node(scope, "k").get_version()
        sm.set_state("s", "k", "v2")

        assert sm.compare_and_set("s", "k", v1, "v3") is False
        assert sm.get_state("s", "k") == "v2"

    def test_cas_missing_node_raises(self):
        """Scenario: 节点不存在时条件写明确失败而非退化成功."""
        sm = StateMachineManager()
        sm.set_state("s", "other", "x")

        with pytest.raises(KeyError):
            sm.compare_and_set("s", "k", 1, "v")

    def test_cas_missing_scope_raises(self):
        """作用域不存在时条件写明确失败，且不留下空作用域."""
        sm = StateMachineManager()

        with pytest.raises(KeyError):
            sm.compare_and_set("noscope", "k", 1, "v")

        assert sm.get_state_machines().has_key("noscope") is False

    def test_cas_none_expected_version_raises(self):
        """无可比较版本（None）时条件写明确失败."""
        sm = StateMachineManager()
        sm.set_state("s", "k", "v")

        with pytest.raises(TypeError):
            sm.compare_and_set("s", "k", None, "new")


class TestConcurrency:
    """并发正确性：读-改-写段持 scope 级锁."""

    def test_concurrent_append_no_lost_updates(self):
        """Scenario: 并发追加不丢更新，总数等于各线程追加数之和."""
        sm = StateMachineManager()
        sm.get_and_create_scope("s")  # 预建 scope，聚焦节点级原子性
        thread_count, per_thread = 8, 50
        barrier = threading.Barrier(thread_count)

        def worker(tid: int) -> None:
            barrier.wait()
            for i in range(per_thread):
                sm.append_state("s", "k", (tid, i))

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(thread_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(sm.get_state("s", "k")) == thread_count * per_thread

    def test_concurrent_cas_same_version_only_one_wins(self):
        """Scenario: 相同期望版本的并发条件写恰好一个成功."""
        sm = StateMachineManager()
        sm.set_state("s", "k", "initial")
        scope = sm.get_and_create_scope("s")
        version = _node(scope, "k").get_version()
        barrier = threading.Barrier(2)
        results: list[bool] = []

        def writer(value: str) -> None:
            barrier.wait()
            results.append(sm.compare_and_set("s", "k", version, value))

        threads = [threading.Thread(target=writer, args=(f"w{i}",)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results.count(True) == 1
        assert results.count(False) == 1
        assert sm.get_state("s", "k") in ("w0", "w1")

    def test_cas_and_unconditional_writes_keep_versions_increasing(self):
        """无条件 set_state 与 CAS 混用下版本仍严格递增."""
        sm = StateMachineManager()
        sm.set_state("s", "k", 0)
        scope = sm.get_and_create_scope("s")
        node = _node(scope, "k")
        versions = [node.get_version()]

        for i in range(1, 11):
            sm.set_state("s", "k", i)
            versions.append(node.get_version())

        assert sm.compare_and_set("s", "k", node.get_version(), 100) is True
        versions.append(node.get_version())

        assert all(b > a for a, b in pairwise(versions)), versions
