"""容器外进程级载体的显式归类登记表（变更 declare-debt-carriers / issue #50 切片一）.

背景：`scoped-container` 交付的容器只持有"被解析的实例"，够不到类属性与注册面；
`specs/scoped-container` 要求「框架自身的进程级共享 MUST 被显式归类」，而此前测试隔离
靠 `tests/conftest.py` 里手工维护的复位清单——新增一个进程级共享没有机制保证它被
登记。本模块把"归类声明"变成数据、把"复位清单"变成从登记表生成的函数：

- `CARRIERS` 是唯一真源：每个进程级共享载体一条声明（归类 + 理由 + 可选复位）。
- `reset_process_state()` 供测试基座逐项执行复位——conftest 不再手抄清单。
- 泄漏拦截：`tests/test_process_state_registry.py` 扫描框架全部模块级/类级可变容器，
  不匹配本表任何条目（对象身份或规范名）即判失败——新增进程级共享忘了归类时，
  红的是测试，而不是"某天的测试串扰谜题"。

条目分类（对应 #50 的"两类不能混为一谈"）：
- `注册面` / `配置面`：不是被解析的实例，不强行塞进容器；此处给出显式归类与理由
- `待收编`：#50 认定的进程级共享实例（切片二处理收编方式），当前先复位隔离
- `执行设施`：无用户可见状态的运行设施（线程池），不随用例重建
- `容器本身`：框架进程级容器的复位入口
- `常量`：运行期只读，声明即归类

认领方式：对象会被**重新绑定**的载体（如 `ParamsFactory.config_params` 在载入时
整体替换）MUST 按规范名认领；只原地 mutate 的载体按对象身份认领——两条路都通，
选错会让"跑过别的用例之后"的扫描误报。
"""

import sys
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Carrier:
    """一个进程级载体的归类声明.

    Attributes:
        canonical: 规范名（"模块尾段:对象名"，给人读）
        category: 分类，取值见模块 docstring
        reason: 归类理由（判为容器外时 MUST 说明为什么）
        watch: 被登记的对象本体，扫描按对象身份匹配；会被重绑定的对象放 names
        names: 允许出现的规范全名（"module.attr" / "module.Class.attr"）
        reset: 测试复位动作；None 表示该载体无需/不应随用例复位
    """

    canonical: str
    category: str
    reason: str
    watch: object | None = None
    names: tuple[str, ...] = ()
    reset: Callable[[], None] | None = None


def _register_all() -> dict[str, Carrier]:
    """构建登记表：所有被登记对象在此一次性导入（惰性于函数内，避免导入环）。"""
    # 按属性取子模块会被包面同名函数遮蔽（aop/__init__ 导入的是函数），
    # 故先触发导入、再从 sys.modules 拿真模块对象。
    import zoo_framework.core.aop.configure
    import zoo_framework.core.aop.params  # noqa: F401

    configure_mod = sys.modules["zoo_framework.core.aop.configure"]
    params_mod = sys.modules["zoo_framework.core.aop.params"]

    from zoo_framework.cli import DEFAULT_CONF as _cli_default
    from zoo_framework.core.container import framework_container
    from zoo_framework.core.params_factory import ParamsFactory
    from zoo_framework.core.waiter.base_waiter import LEGACY_POLICY_TO_BACKPRESSURE
    from zoo_framework.fifo.single_fifo import SingleFIFO
    from zoo_framework.plugin import Plugin
    from zoo_framework.reactor.event_reactor_req import get_channel_manager
    from zoo_framework.statemachine.state_index_factory import StateIndexFactory

    # ---- 复位动作（具名函数：返回 None，不把 tuple 表达式当 Callable 用） ----

    def reset_config_funcs() -> None:
        configure_mod.config_funcs.clear()
        configure_mod.unseal_config_funcs_for_tests()

    def reset_params_cache() -> None:
        params_mod.config_params.clear()
        params_mod._resolved_generation.clear()

    def reset_config_dict() -> None:
        ParamsFactory.config_params = {}
        ParamsFactory._generation = 0

    def reset_channel_manager() -> None:
        manager = get_channel_manager()
        manager._channels.clear()
        manager._reactor_channels.clear()

    def reset_container() -> None:
        framework_container().reset()

    carriers: list[Carrier] = [
        # ---- 注册面 / 配置面（不塞进容器，声明 + 复位） ----------------------
        Carrier(
            canonical="core.aop.configure:config_funcs",
            category="注册面",
            reason=(
                "@configure 的导入期注册表，不是被解析的实例；消费与封的契约见 "
                "specs/aop。复位=清空并解封（用例从干净注册面开始）。"
            ),
            watch=configure_mod.config_funcs,
            reset=reset_config_funcs,
        ),
        Carrier(
            canonical="core.aop.configure:_sealed",
            category="注册面",
            reason="注册表封位（bool，扫描不可见），随 config_funcs 一并复位。",
            reset=configure_mod.unseal_config_funcs_for_tests,
        ),
        Carrier(
            canonical="core.aop.params:config_params",
            category="配置面",
            reason=(
                "@params 的解析缓存（限定名 -> 类）与 #51 的解析世代记录：解析副记录的"
                "注册面而非容器项；复位=清空（测试内可重新解析），"
                "与 ParamsFactory.config_params 的重绑定语义无关（本表原地 mutate）。"
            ),
            watch=params_mod.config_params,
            reset=reset_params_cache,
        ),
        Carrier(
            canonical="core.aop.params:_resolved_generation",
            category="配置面",
            reason="#51 的解析世代记录，与 config_params 同生命周期，随其一并复位。",
            watch=params_mod._resolved_generation,
        ),
        Carrier(
            canonical="core.params_factory:ParamsFactory.config_params",
            category="配置面",
            reason=(
                "get_params 实际读取的配置字典（类属性）。载入时**整体重绑定**而非原地"
                "替换，故按规范名认领；复位连同载入世代计数一起归零。"
            ),
            names=("zoo_framework.core.params_factory.ParamsFactory.config_params",),
            reset=reset_config_dict,
        ),
        # ---- 已收编进容器（变更 absorb-debt-carriers / #50 交付 1 方案 A） ------
        Carrier(
            canonical="reactor.event_reactor_manager:reactor_map",
            category="容器本身",
            reason=(
                "已由【已知欠债】收编：注册表降为 process_scoped 实例的属性，"
                "容器 reset 即彻底复位；类级读取经元类代理转发到进程级实例，"
                "故按规范名认领。"
            ),
            names=("zoo_framework.reactor.event_reactor_manager.EventReactorManager.reactor_map",),
        ),
        Carrier(
            canonical="event.event_channel_register:_channel_map",
            category="容器本身",
            reason="同 reactor_map：已收编为实例态，容器 reset 即彻底复位。",
            names=("zoo_framework.event.event_channel_register.EventChannelRegister._channel_map",),
        ),
        Carrier(
            canonical="core.worker_registry:get_worker_registry",
            category="容器本身",
            reason=(
                "原模块级隐式单例 _global_registry 已收编：进程级入口经框架容器解析，"
                "容器 reset 后重建新实例即完全复位（直接构造私有实例不受影响）。"
            ),
        ),
        # ---- 执行设施（无用户可见状态，不随用例重建） ------------------------
        Carrier(
            canonical="statemachine.state_node:_effect_executor",
            category="执行设施",
            reason=(
                "align-execution-primitives 引入的模块级共享线程池：执行设施而非状态"
                "存储；每用例重建只会泄漏线程，回收依赖 concurrent.futures 的 atexit 钩子。"
            ),
        ),
        # ---- 容器本身与复位接缝 ----------------------------------------------
        Carrier(
            canonical="core.container.registry:framework_container",
            category="容器本身",
            reason="框架进程级容器的复位入口——conftest 原第一条手工复位来源。",
            reset=reset_container,
        ),
        Carrier(
            canonical="reactor.event_reactor_req:channel_manager",
            category="注册面",
            reason=(
                "通道监听配置（get_channel_manager 单例的内部表）：非解析实例，"
                "登记为容器外；复位=清空两张内部表（现行 conftest 语义）。"
            ),
            reset=reset_channel_manager,
        ),
        # ---- 待收编（登记后由后续切片处理） ------------------------------
        Carrier(
            canonical="fifo.single_fifo:SingleFIFO.index_list",
            category="待收编",
            reason=(
                "类属性 dict 跨实例共享——single_fifo 文档自标【已知欠债】，#50 清单"
                "未列（扫描机制上线后新发现）。本切片只声明归类，不随用例复位"
                "（改复位语义超出范围）；与 reactor_map 同形态，收编在后续变更。"
            ),
            watch=SingleFIFO.index_list,
        ),
        Carrier(
            canonical="cli:DEFAULT_CONF",
            category="常量",
            reason="脚手架默认配置模板；运行期只读（scaffold 侧同名条目为别名）。",
            watch=_cli_default,
            names=("zoo_framework.cli.scaffold.DEFAULT_CONF",),
        ),
        Carrier(
            canonical="conf.log_config:颜色与级别映射",
            category="常量",
            reason="日志级别/颜色表；运行期只读。",
            names=(
                "zoo_framework.conf.log_config.level_relations",
                "zoo_framework.conf.log_config.log_colors_config",
            ),
        ),
        Carrier(
            canonical="core.waiter.base_waiter:LEGACY_POLICY_TO_BACKPRESSURE",
            category="常量",
            reason="历史策略名映射；运行期只读。",
            watch=LEGACY_POLICY_TO_BACKPRESSURE,
        ),
        Carrier(
            canonical="plugin:Plugin.dependencies",
            category="常量",
            reason="类属性空列表仅作缺省值；实例写入经 self 遮蔽，不改类对象。",
            watch=Plugin.dependencies,
        ),
        Carrier(
            canonical="core.container.thread_safety:ThreadSafety.DESCRIPTIONS",
            category="常量",
            reason="线程安全声明的人读描述表；命名像枚举实为普通类，运行期只读。",
            names=("zoo_framework.core.container.thread_safety.ThreadSafety.DESCRIPTIONS",),
        ),
        Carrier(
            canonical="statemachine.state_index_factory:StateIndexFactory._index_types",
            category="注册面",
            reason=(
                "索引类型工厂的注册表（装饰器导入期写入、运行期只增不改），"
                "与 config_funcs 同形态：不塞进容器，声明即归类；跨用例不需复位。"
            ),
            watch=StateIndexFactory._index_types,
        ),
    ]
    table = {c.canonical: c for c in carriers}
    # 登记表自身：构建后只读（新增载体靠改源码而非运行期注册），按名认领，
    # 以免扫描机制被自己的真源卡住。
    table["core.process_state:CARRIERS"] = Carrier(
        canonical="core.process_state:CARRIERS",
        category="常量",
        reason="登记表自身：构建后只读，自登记以免扫描机制被自己的真源卡住。",
        names=("zoo_framework.core.process_state.CARRIERS",),
    )
    return table


#: 登记表唯一真源（导入即构建；被登记模块的导入在 _register_all 内完成）。
CARRIERS: dict[str, Carrier] = _register_all()


def reset_process_state() -> None:
    """按登记表逐项复位——测试基座唯一入口（替代 conftest 手抄清单）.

    单项复位异常不掩盖剩余复位：先跑完全部，再汇总抛出。
    """
    failures: list[str] = []
    for name, carrier in CARRIERS.items():
        if carrier.reset is None:
            continue
        try:
            carrier.reset()
        except Exception as exc:  # 汇总后统一报，避免一项失败吞掉其余复位
            failures.append(f"{name}: {exc!r}")
    if failures:
        raise RuntimeError("进程级载体复位失败：\n" + "\n".join(failures))


def known_carrier_ids() -> set[int]:
    """扫描拦截用：已登记对象的身份集."""
    return {id(c.watch) for c in CARRIERS.values() if c.watch is not None}


def known_carrier_names() -> set[str]:
    """扫描拦截用：已登记的规范全名集（重绑定型/别名载体）."""
    return {n for c in CARRIERS.values() for n in c.names}
