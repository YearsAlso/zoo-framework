"""add-state-query-index-and-incremental-persistence 原语 2：查询型索引默认实现.

覆盖 spec delta 的 ADDED 场景：内置索引按节点值查询（谓词 / 关键词子串）、未配置
索引类型时用现状默认、未知索引类型显式失败、无匹配返回空结果、并发写入下查询不崩溃。
"""

import threading

import pytest

from zoo_framework.statemachine.state_index_factory import (
    QueryableIndex,
    StateIndexFactory,
    ThreadSafeDictIndex,
)
from zoo_framework.statemachine.state_node import StateNode


def _seed(index, pairs):
    """把 (键, 值) 对写入索引."""
    for key, value in pairs:
        index.set(key, StateNode(key=key, value=value))


class TestFactoryRegistration:
    """查询型索引 MUST 经既有注册接缝按名选取（原语 2）."""

    def test_queryable_registered_by_name(self):
        """Scenario: 内置索引可按名创建."""
        assert "queryable" in StateIndexFactory.get_available_types()
        assert isinstance(StateIndexFactory.create_index("queryable"), QueryableIndex)

    def test_existing_types_untouched(self):
        """既有内置类型仍在（不删既有实现，向后兼容）."""
        available = StateIndexFactory.get_available_types()
        assert "dict" in available
        assert "hierarchical" in available

    def test_queryable_is_a_state_index(self):
        """查询型索引仍实现既有 StateIndex ABC 的全部抽象方法（不新增抽象方法）."""
        index = StateIndexFactory.create_index("queryable")
        index.set("k", StateNode(key="k", value="v"))
        assert index.has("k") is True
        assert index.get("k").get_value() == "v"
        assert index.find_by_prefix("k")[0].get_value() == "v"
        assert index.get_all()["k"].get_value() == "v"
        assert index.remove("k").get_value() == "v"
        assert index.has("k") is False


class TestPredicateQuery:
    """按节点值谓词过滤（原语 2）."""

    def test_predicate_returns_exactly_matching_nodes(self):
        """Scenario: 内置索引可按节点值查询——返回恰好满足谓词的节点."""
        index = QueryableIndex()
        _seed(index, [("a", 1), ("b", 2), ("c", 3), ("d", 4)])

        matched = index.query(lambda v: v >= 3)

        assert {n.get_key() for n in matched} == {"c", "d"}
        assert len(matched) == 2

    def test_empty_index_returns_empty(self):
        """Scenario: 无匹配返回空结果——空索引."""
        index = QueryableIndex()
        assert index.query(lambda _value: True) == []

    def test_no_match_returns_empty_without_raising(self):
        """Scenario: 无匹配返回空结果——有节点但无一满足谓词."""
        index = QueryableIndex()
        _seed(index, [("a", 1), ("b", 2)])
        assert index.query(lambda v: v > 100) == []

    def test_predicate_receives_node_value(self):
        """谓词入参是节点值，而非节点对象."""
        index = QueryableIndex()
        _seed(index, [("a", "hello")])
        seen: list[object] = []

        def predicate(value):
            seen.append(value)
            return True

        index.query(predicate)

        assert seen == ["hello"]


class TestKeywordQuery:
    """按关键词朴素过滤（大小写敏感的子串 / 等值，原语 2）."""

    def test_substring_match_is_case_sensitive(self):
        """Scenario: 关键词按大小写敏感的子串匹配."""
        index = QueryableIndex()
        _seed(index, [("a", "hello world"), ("b", "HELLO"), ("c", "world")])

        assert {n.get_key() for n in index.find_by_keyword("world")} == {"a", "c"}
        assert {n.get_key() for n in index.find_by_keyword("hello")} == {"a"}
        assert index.find_by_keyword("HELLO")[0].get_key() == "b"

    def test_keyword_equality_is_a_substring_special_case(self):
        """等值匹配是子串匹配的特例（整值即关键词时命中）."""
        index = QueryableIndex()
        _seed(index, [("a", "exact")])
        assert {n.get_key() for n in index.find_by_keyword("exact")} == {"a"}

    def test_no_match_returns_empty(self):
        """Scenario: 无匹配返回空结果——关键词无命中."""
        index = QueryableIndex()
        _seed(index, [("a", "hello")])
        assert index.find_by_keyword("zzz") == []


def _run_concurrent_query_round(per_thread: int = 200) -> list[BaseException]:
    """一轮并发写入 + 查询；返回线程内捕获到的异常（无则空列表）."""
    index = QueryableIndex()
    errors: list[BaseException] = []

    def writer(tid: int) -> None:
        try:
            for i in range(per_thread):
                index.set(f"k{tid}_{i}", StateNode(key=f"k{tid}_{i}", value=i))
        except BaseException as exc:  # 线程内异常必须上报，否则线程静默死掉
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(t,)) for t in range(4)]
    for t in threads:
        t.start()
    while any(t.is_alive() for t in threads):
        result = index.query(lambda v: isinstance(v, int) and v % 2 == 0)
        assert isinstance(result, list)
        index.find_by_keyword("1")
    for t in threads:
        t.join()

    return errors


class TestConcurrentQuery:
    """并发写入下查询 MUST NOT 崩溃（弱一致可接受，原语 2）."""

    def test_query_under_concurrent_writes(self):
        """Scenario: 持续并发写入时执行查询不抛异常（重跑多次）."""
        for _ in range(5):
            errors = _run_concurrent_query_round()
            assert errors == [], f"并发查询 / 写入出现异常: {errors!r}"


class TestManagerSelectsIndexByConfig:
    """索引类型由 stateMachine:indexType 在运行期选取（原语 2）."""

    def test_default_is_dict_index(self, monkeypatch):
        """Scenario: 未配置索引类型时为现状默认（dict）."""
        from zoo_framework.params import StateMachineParams
        from zoo_framework.statemachine import StateMachineManager

        monkeypatch.setattr(StateMachineParams, "STATE_INDEX_TYPE", "dict")
        manager = StateMachineManager()
        manager.create_scope("s")

        assert isinstance(manager.get_and_create_scope("s")._state_index, ThreadSafeDictIndex)

    def test_configured_queryable_index_is_used(self, monkeypatch):
        """配置 queryable 时 scope 用查询型索引."""
        from zoo_framework.params import StateMachineParams
        from zoo_framework.statemachine import StateMachineManager

        monkeypatch.setattr(StateMachineParams, "STATE_INDEX_TYPE", "queryable")
        manager = StateMachineManager()
        manager.create_scope("q")

        assert isinstance(manager.get_and_create_scope("q")._state_index, QueryableIndex)

    def test_unknown_index_type_raises(self, monkeypatch):
        """Scenario: 未知索引类型显式失败（ValueError），不静默回退默认."""
        from zoo_framework.params import StateMachineParams
        from zoo_framework.statemachine import StateMachineManager

        monkeypatch.setattr(StateMachineParams, "STATE_INDEX_TYPE", "no-such-index")
        manager = StateMachineManager()

        with pytest.raises(ValueError):
            manager.create_scope("bad")

        assert manager.get_state_machines().has_key("bad") is False
