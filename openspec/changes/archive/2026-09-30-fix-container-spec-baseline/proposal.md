## Why

`scoped-container` 归档时，一条**全称断言**被写进了主 spec 基线，而它为假。

`openspec/specs/scoped-container/spec.md` 的 Requirement「框架自身的进程级共享 MUST 被显式归类」原文是：

> 框架内部需要进程级共享的对象 SHALL 通过容器显式注册为进程级作用域，**MUST NOT 依赖隐式的全局单例状态**。

但框架里仍有至少两处隐式的全局单例状态，且都持有进程级共享数据：

| 位置 | 形态 |
|---|---|
| `zoo_framework/core/worker_registry.py` | 模块级 `_global_registry`，由 `get_worker_registry()` 惰性创建 |
| `zoo_framework/reactor/event_reactor_manager.py` | `reactor_map = ThreadSafeDict()` —— **类属性**（`channel_register._channel_map` 同理） |

**这不是实现违规，而是规范句写宽了。** `scoped-container` 的范围自始就是 8 处 `@cage` 使用点，`WorkerRegistry` 从一开始就被划到范围外并记为独立缺陷；错在把那句话写成了**全称**，于是把范围外的东西也一并断言了。旁证就在同一份 spec 里：该 Requirement 的两个 Scenario **只点名**"事件通道管理器或响应器管理器"，即已迁入容器的那批——**规范句绝对、场景窄**，二者本就不一致。

同一次复查还查出三处**基线缺口**（不是假断言，是"该写而没写"）：

1. **`exclusive` 的契约未被覆盖** —— Requirement「线程安全归属 MUST 被显式声明」给了"由容器保证串行访问"这个取值，但没有任何要求或场景描述该取用入口的语义。
2. **原型级作用域在基线里空白** —— 「解析 MUST 以作用域为界」写的是"作用域**至少包括**进程级与会话级"，第三种的语义一字未提。
3. **声明只需"存在"、无需"为真"** —— 基线要求每个注册项 MUST 声明其线程安全归属、且 MUST NOT 以隐式默认值代替声明；但**没有**要求声明与实例的真实行为相符。

第 3 条的分量最大：清点时发现 `EventRegister`（裸 `list`）与 `WaiterResultReactor`（执行期读可变字段）两处不对，实现据此把它们的归属声明为 `SINGLE_THREAD` 而**不是**想当然的 `INSTANCE_GUARANTEED`——因为**一个为假的声明比不声明更糟**，它把未验证的安全假设写进代码。这个判断在实现里成立，在基线里没有依据。

## What Changes

- **收窄**「框架自身的进程级共享 MUST 被显式归类」，使其对现状为真；并在基线里**显式记下已知欠债**（上述容器外的进程级载体）与承接锚点，而不是把门槛降到刚好通过、也不假装它们已被收编
- **新增** `exclusive`（顺序独占取用）的契约要求：块内串行、锁按注册项划分且可重入、返回真实实例而非代理
- **新增** 原型级作用域的语义要求：何时算新实例、能否 `replace`、能否 `reset`、与 `on_release` 的关系
- **新增** "线程安全归属声明 MUST 与实例实际行为相符"的要求，并给出可核对的依据形式

**Non-goals**

- **不迁移**残留的隐式全局单例（`WorkerRegistry._global_registry`、两个类级注册表）——那是另一个变更，且量级不同：把**类属性**收编进容器与把**实例**注册进容器不是同一种改动（类属性没有实例身份，要先决定"它是谁的字段"）
- 不改变任何运行时行为（本变更除注释与用例之外不动实现）

## Impact

- 受影响 spec：`scoped-container`（1 条修改 + 3 条新增）
- 受影响代码：无行为改动；仅在两处 `SINGLE_THREAD` 声明处补可核对依据的注释，并新增用例把这两处声明固定住（防止将来被静默"升级"为 `INSTANCE_GUARANTEED`）
- 承接锚点：容器外的进程级载体记录在案，待后续变更决定是否收编
