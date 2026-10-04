## Why

框架需要一个"跨 Worker 拿到同一个对象"的机制——不要每个 Worker 各建一份数据库连接池、设备句柄或工具客户端。这个需求成立且常见，也是当初模仿 Spring 的动机之一。

但现有实现 `@cage` 把 **DI 的语义压进了 AOP 的载体**（装饰器），产出的是三处可复现的缺陷，而不是"设计欠缺"：

| 实测 | 结果 |
|---|---|
| 按类名做键 | `cage_register_map` 的键只是 `cls.__name__`（实测键为 `['Service']`）。两个同名类互相覆盖：第二个同名类的实例化**返回第一个的实例**，`a is b == True`，且**不报错** |
| 用"替换类"实现单例 | 装饰后 `type(Service).__name__ == 'function'`；`issubclass(...)` 与 `isinstance(a, Service)` **双双抛 TypeError**。前者正是让 `Master()` 不可构造的 P0 元凶（已修） |
| 无生命周期 | `cage` 模块公开名为空，无 `reset`/`destroy`/`scope`/`clear`。无法释放、无法按测试隔离、无法按会话或设备隔离 |

根因不是随机的：**装饰器只能返回别的东西**，所以"用装饰器实现单例"必然走"替换类"这条路，而替换类必然摧毁类型契约。也就是说，DI 的正确性要求（键唯一、类型可判定、作用域、生命周期、可替换）在装饰器语义里**无处安放**。

同时需求被表述为"跨 Worker 拿到**同一个**对象"时，"全局同一性"其实是个错目标：进程级全局单例意味着所有会话、所有设备共用一个对象——Agent 线会串会话数据，设备线会写错设备。真正需要的是**作用域解析**。

`@cage` 目前从未被任何 spec 覆盖，且已在 8 处使用（`event_channel_manager`、`event_channel_register`、`event_provider`、`event_register`、`event_reactor_manager`、`waiter_result_reactor`、`state_machine_manager`、`state_node_index_factory`）——全部是进程级管理器，对它们而言全局同一性是对的。所以本变更不是"废除全局共享"，而是**把作用域显式化**，让每个消费点声明自己要哪一种。

## What Changes

**新增「作用域容器」能力**

- 以**显式容器 + 作用域句柄**提供解析：同一作用域内同一实例、不同作用域不同实例；作用域取值为进程级 / 会话级 / 原型级
- 注册项标识改为**限定名**（模块 + 限定名）并支持显式名覆盖，使同名类可区分——直接消除实测的串号缺陷
- 解析结果 **MUST 保留类型契约**：可用于 `isinstance` 与 `issubclass` 判定，MUST NOT 出现"装饰后类型不是类"的情形
- **生命周期显式**：提供获取与释放入口，释放触发注册项声明的销毁钩子，且可查询作用域下存活实例数
- **线程安全归属作为注册必填声明**：容器保证串行 / 实例自身保证 / 仅单线程作用域可用。未声明 MUST 拒绝注册
- **测试接缝**：可按作用域替换实现与重置，用于注入假实现

**同一反模式的第二处：`@params` 的解析缓存**

核对时发现 `@params` 用**完全相同的键策略**缓存已解析的参数类：`core/aop/params.py` 的 `config_params[cls.__name__]`。后果与 `@cage` 同族但更隐蔽——同名参数类会**跳过解析**并直接复用已解析的那个，即拿到**别的模块的配置值**，且发生在 import 期（无任何错误提示）。

| 位置 | 键 | 后果 |
|---|---|---|
| `core/aop/cage.py` | `cls.__name__` | 同名类解析到**错的对象**（已实测：`b.who()` 返回第一个 Service） |
| `core/aop/params.py` | `cls.__name__` | 同名参数类**复用他人的配置值**，静默 |

根因是同一个：**进程级缓存以裸类名做键**。本变更一并修掉，并把 `@params` 刚获得、但尚无 spec 覆盖的两条语义（别名回退、假值与缺失的区分）固定下来，防止回归。

**迁移与约束**

- 把框架自身 8 处进程级共享对象显式注册为进程级作用域，不再依赖隐式全局状态
- 把 `@params` 的解析缓存键由裸类名改为限定名，并规格化其别名回退与假值语义
- 禁止再新增"用装饰器替换类"的用法，遏制该模式的蔓延
- **不**重构 `aop/` 包中与上述两件事无关的装饰器（`configure`/`logger`/`stopwatch`/`validation` 的欠账另行处理）

## Capabilities

### New Capabilities

- `scoped-container`:作用域解析的语义（作用域为界、标识唯一、类型契约保留）、生命周期与释放、线程安全归属的显式声明、以及测试替换接缝
- `config-resolution`:参数类解析的标识（进程内唯一、不依赖裸类名）、别名回退顺序、以及已配置假值与缺失的区分

### Modified Capabilities

无。`@cage` 与 `@params` 此前**都没有任何 spec 覆盖**，本变更是二者第一次被规格化；其余既有能力的要求不变。

## Impact

**受影响代码**

| 类别 | 位置 |
|---|---|
| 新增 | 作用域容器（模块位置待定，见 design Open Questions） |
| 迁移 | 8 处 `@cage` 使用点：`event/event_channel_manager.py`、`event/event_channel_register.py`、`event/event_provider.py`、`event/event_register.py`、`reactor/event_reactor_manager.py`、`reactor/waiter_result_reactor.py`、`statemachine/state_machine_manager.py`、`statemachine/state_node_index_factory.py` |
| 既有测试改写 | `tests/test_aop.py` 的两条 `cage` 断言（`test_cage_decorator` 的"可正常实例化"、`test_cage_singleton_behavior` 的 `instance1 is instance2`）需按新语义改写 |

**依赖（硬前置）**

本变更是 `scheduler-model-seam` 的**下游**：作用域需要一个可表达的会话边界，而该边界由 `scheduler-model-seam` 新增的**会话标识**提供。**该标识未落地前本变更不得开工**——否则作用域只能退化为进程级，等于没做。

**公开 API 影响（BREAKING）**

- `@cage` 的现有语义若变更（标识由类名改为限定名、不再替换类），直接依赖"装饰后是同一个类"或"同名即同一实例"的代码会观察到差异
- 框架自身 8 处使用点改为显式注册，若有外部代码以 `X()` 形式直接取用这些管理器，调用方式可能改变

**不涉及的边界**

- **不做 AOP**。不施加通知、不定义连接点、不做切点匹配——本变更只解决"按作用域取得同一对象"，与横切无关
- 不做构造期自动装配图、不做循环依赖检测、不做配置驱动 bean 定义
- 不重构 `aop/` 包内与 DI 无关的装饰器
- 不改 `@params` 的配置机制（它是另一件事，尽管同在 `aop/` 包内）
- 不改 `pyproject.toml` 的依赖列表，不引入 Rust
