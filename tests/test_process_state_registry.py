"""进程级共享载体 MUST 被显式归类（变更 declare-debt-carriers / issue #50 切片一）.

机制替代清单：walk `zoo_framework` 全部模块，收集**模块级与类级的可变容器**
（dict / list / set / ThreadSafeDict），每一个都必须能按**对象身份**或**规范全名**
匹配到 `core.process_state.CARRIERS` 的某条归类声明——否则失败。新增一个进程级
共享而忘记归类时，红的是这里，而不是"某天的测试串扰谜题"。

豁免规则（本身也是"显式归类"的一部分，理由写在断言消息里）：
- Enum 类整体跳过：`_member_map_` 等是 stdlib 元数据，不是框架状态
- dunder 名与内置模块对象跳过
- `frozenset`/`tuple` 等不可变容器不在候选（无运行期写入面）
"""

import enum
import importlib
import pkgutil

import pytest

import zoo_framework
from zoo_framework.core.process_state import CARRIERS, known_carrier_ids, known_carrier_names
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict

_MUTABLE_CONTAINER = (dict, set, list, ThreadSafeDict)


def _iter_modules():
    for info in pkgutil.walk_packages(zoo_framework.__path__, "zoo_framework."):
        try:
            yield importlib.import_module(info.name)
        except Exception:
            continue


def _candidates():
    """产出 (规范全名, 对象) 候选：模块级属性 + 非 Enum 类的类级属性."""
    for mod in _iter_modules():
        for name, value in vars(mod).items():
            if name.startswith("__"):
                continue
            if isinstance(value, type):
                if issubclass(value, enum.Enum):
                    continue
                for cname, cvalue in vars(value).items():
                    if cname.startswith("__"):
                        continue
                    if isinstance(cvalue, _MUTABLE_CONTAINER):
                        yield f"{value.__module__}.{value.__name__}.{cname}", cvalue
                continue
            if isinstance(value, _MUTABLE_CONTAINER):
                yield f"{mod.__name__}.{name}", value


def test_every_process_level_mutable_container_is_declared():
    """扫描到的每个进程级可变容器都必须在登记表里有归类声明."""
    ids = known_carrier_ids()
    names = known_carrier_names()
    undeclared = [
        f"{name} ({type(obj).__name__})"
        for name, obj in _candidates()
        if id(obj) not in ids and name not in names
    ]
    assert not undeclared, (
        "以下进程级共享未在 core/process_state.CARRIERS 归类"
        "（新增载体必须同时登记：分类 + 理由 + 是否复位）：\n  "
        + "\n  ".join(sorted(set(undeclared)))
    )


def test_registry_entries_are_complete():
    """每条声明 MUST 有分类与理由；待收编项 MUST 可被复位或注明不复位原因."""
    allowed = {"注册面", "配置面", "待收编", "执行设施", "容器本身", "常量"}
    for canonical, carrier in CARRIERS.items():
        assert carrier.category in allowed, f"{canonical} 的分类 {carrier.category!r} 不在允许集"
        assert len(carrier.reason) >= 12, f"{canonical} 的理由过短，不足以支撑归类"
        # 可扫描对象由 test_every_process_level_mutable_container_is_declared 自己把关；
        # 非容器型条目（标志位、执行器、单例）允许仅凭声明在册。


def test_reset_process_state_is_idempotent():
    """复位接缝自身可反复执行（conftest 每用例前后各一次的前提）."""
    from zoo_framework.core.process_state import reset_process_state

    reset_process_state()
    reset_process_state()


@pytest.mark.parametrize("canonical", ["reactor_map", "_channel_map"])
def test_absorbed_carriers_are_container_backed(canonical: str):
    """#50 交付 1（方案 A）：两处注册表已收编为容器实例态，分类为容器本身."""
    matches = [c for c in CARRIERS.values() if canonical in c.canonical]
    assert matches, f"{canonical} 未登记"
    assert matches[0].category == "容器本身"
