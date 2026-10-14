## Context

`WorkerRegistry` 用三张按名称键控的表承载三种注册形态：`_worker_classes`（类，延迟实例化）、
`_worker_factories`（零参工厂，延迟实例化）、`_worker_instances`（实例）。`get_worker` 按
「实例 → 工厂 → 类」查找，并在后两种形态首次命中时把结果**写回** `_worker_instances` 作为缓存。

缺陷根因：写回缓存的键是**名称**，与「产出它的定义」无关。以同名注册新类时只更新
`_worker_classes[name]`，`_worker_instances[name]` 的旧对象仍在，且因查找优先级最高而被继续
返回——新类永远拿不到实例化机会。

## Decision

采用**重注册替换缓存实例**（任务给出的二选一之一），而不是「显式报错」：

- 显式报错会与既有可重复构造行为冲突：`Master._register_default_workers` 每次构造 `Master` 都以
  同一批名称重新注册**同一批类**，报错将使 `worker-lifecycle` 的「构造过程可重复」失效。
- 仓库既有的书写语义就是覆盖：`WorkerDispatchCore.add_worker` 注释明写「同名重注册（如
  `Master.register_worker` 覆盖旧实例）」。
- 因此语义定为：**定义变化即替换、同一定义幂等**。

实现上新增 `_lazy_instances`，只标记「由工厂 / 类延迟实例化出来」的缓存项。作废只针对这类缓存；
`register_instance` 显式登记的实例是调用方的既有对象（且查找优先级本就更高），MUST NOT 因类 /
工厂重注册被连带丢弃。

### 具体判据

- `register_class(name, cls)`：`_worker_classes[name] is not cls` 时作废该名称的延迟实例化缓存。
- `register_factory(name, f)`：`_worker_factories[name] is not f` 时同样作废。
- `register_instance(name, obj)`：写入实例并把该名称移出延迟缓存。
- `get_worker`：由工厂 / 类实例化时把名称加入延迟缓存。

## Non-goals

- 不改查找优先级（实例仍优先于工厂 / 类）。
- 不销毁被替换的旧实例（不调用 `_destroy`）：销毁会引入未被请求的副作用，旧实例按普通对象回收。
- 不把同名旧实例移出**调度列表**：那是调度层（`WorkerDispatchCore.add_worker`）的既有行为，与
  「注册表返回旧实例」是两件事；本变更只在注册表侧修「返回新定义实例」。
- 不改 `register_instance` 的类型校验与 `register_class` 的注册期构造参数校验。

## Language

正文与注释用中文，代码 docstring 保持 Google 风格（`Args:` / `Returns:` / `Raises:`），与仓库既有
文件一致。
