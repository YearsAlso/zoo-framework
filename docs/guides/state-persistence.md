# 状态持久化

[教程 02](../tutorial/02-state-persistence.md) 走过一遍基本用法。本页补齐语义边界。

## 读写

```python
from zoo_framework.statemachine import StateMachineManager

sm = StateMachineManager()  # 进程级单例，任何地方拿到的是同一个

sm.set_state("order", "status", "pending")  # 首次写入即创建作用域
sm.set_state("order", "status", "paid")  # 覆盖

sm.get_state("order", "status")  # -> 'paid'
sm.get_state("order", "nothing")  # -> None（键不存在）

sm.set_state("order", "item.count", 2)  # 点分键路径，自动嵌套
sm.get_state("order", "item.count")  # -> 2

sm.remove_state("order", "status")
```

| 方法 | 说明 |
|---|---|
| `set_state(scope, key, value)` | 整值写入；`scope` 不存在时自动创建 |
| `get_state(scope, key)` | 读取；不存在返回 `None` |
| `remove_state(scope, key)` | 删除 |
| `append_state(scope, key, item)` | 向集合键**逐条追加**一个元素；键不存在时以 `[item]` 建节点 |
| `compare_and_set(scope, key, expected_version, value)` | **条件写**；版本匹配才写入，返回是否已写 |
| `observe_state(scope, key, cb)` | 订阅变更 |
| `unobserve_state(scope, key, cb)` | 取消订阅 |

## 追加与条件写

两条原语是 `set_state` 整值替换之外的补充入口，默认不调用即零行为变化。

**追加（`append_state`）** 只新增元素、不重写既有元素，读取按追加顺序返回：

```python
sm.append_state("order", "log", "created")  # 键不存在时自动以 ["created"] 建节点
sm.append_state("order", "log", "paid")
sm.get_state("order", "log")  # -> ['created', 'paid']
```

只支持列表值：对非列表（整数、dict 子树等）追加会抛 `TypeError` 且不覆盖原值。
重复追加**不幂等**，去重由调用方负责。

**条件写（`compare_and_set`）** 用于同 scope 跨线程的「读取-改-写」——在
原子临界区内比较版本、相等才写入，避免丢更新：

```python
sm.set_state("order", "status", "pending")
scope = sm.get_and_create_scope("order")
version = scope.get_state_node("status").get_version()  # 节点版本，严格递增

sm.compare_and_set("order", "status", version, "paid")  # -> True（已写）
sm.compare_and_set("order", "status", version, "cancelled")  # -> False（版本已过期）
```

版本不匹配**不是异常**，而是返回 `False`，便于重新读取版本后重试；节点或作用域
不存在、`expected_version` 为 `None` 时才抛错。节点版本在每次成功写入后严格递增。

## 观察者

```python
def on_status_change(payload):
    print(payload["value"])


sm.observe_state("order", "status", on_status_change)
sm.set_state("order", "status", "shipped")  # 触发回调
sm.unobserve_state("order", "status", on_status_change)
```

> **记得取消订阅。** 回调会持有引用；长期运行的进程里忘记 `unobserve_state`
> 是内存增长的常见来源——示例 Worker 里就有针对这一点的写法。

## 落盘

| 项 | 值 |
|---|---|
| 路径 | `stateMachine:picklePath`，默认 `./zooStates.pic` |
| 间隔 | `stateMachine:delay`，默认 5 秒 |
| 停机 | `Master.shutdown()` 时**再存一次**（这是最后一次保存） |
| 方式 | 先写 `.tmp`，再**原子替换** |
| 备份 | 替换前把旧文件复制进同级 `backups/`，**保留最近 5 份** |

## 查询型索引（可选）

默认索引（`stateMachine:indexType="dict"`）只支持按键与前缀查找。要**按节点值**找东西，
把 `stateMachine:indexType` 设为 `"queryable"`：新作用域会用查询型索引，在既有键索引
之上提供谓词与关键词两种朴素过滤。

```python
from zoo_framework.statemachine.state_index_factory import StateIndexFactory

index = StateIndexFactory.create_index("queryable")
index.set("user:1", node_1)
index.set("user:2", node_2)

index.query(lambda value: value.get("age", 0) >= 18)  # 按值谓词过滤
index.find_by_keyword("alice")  # 大小写敏感的子串匹配
```

定位是**朴素默认实现**：不做排序、相关度或语义 / 向量检索——重查询场景请注册专用索引
（`StateIndexFactory.register_index_type`）并用该键选用。两点须知：

- 查询结果是**弱一致**的：并发写入下一个正在被改写的节点可能被看到、也可能看不到，
  不保证强一致快照；但查询不会因并发写入而崩溃。
- 未知索引名会抛 `ValueError`（不静默回退到默认类型）。

## 增量持久化（可选）：只写脏作用域

默认每次落盘都把**全部**作用域重写一遍。把 `stateMachine:incrementalSave` 设为 `true`
后进入增量模式：

- `stateMachine:picklePath` 由「文件」变为「**目录**」，内含一个 manifest
  （作用域名 → 文件名）与每作用域一个文件；
- 每拍**只写自上次落盘后被修改过的作用域**，未修改的作用域不会被重写；
- 写入顺序为「先写脏作用域文件、后原子替换 manifest」，启动恢复以 manifest 为准、
  孤儿文件忽略；
- 落盘失败仍抛显式 `PersistenceError`（沿用既有的原子写与失败显式化语义）。

> **首次启用撞上旧整表文件**时，会先按旧格式读入、以目录布局重写，并把原文件改名为
> `<原名>.migrated.bak` 留档（不删数据、不静默误读）。回滚时需先把目录布局导出回整表
> 文件再还原提交。

## 作用域 TTL（可选）

`stateMachine:scopeTtlSeconds` 设为正数即启用按作用域淘汰：每拍扫描，把
`now - last_modified` 超过该值的作用域从内存移除（增量模式下同时清理其持久化文件）。
被淘汰后按该作用域查询返回 `None`（空）。

- **时间基准是墙钟**（`time.time()`），语义是「**最后写入**」而非最后访问——读路径不刷新
  时间戳。墙钟意味着它跨进程重启成立，但也意味着系统时间回拨 / 跨机时钟漂移会影响判定。
- 默认 `0` 表示**不淘汰**（行为与合入前一致）。

## 三条必须知道的语义

### 1. 恢复是「整表替换」，不是逐键合并

读盘时用文件里的状态**整体替换**内存状态。手工改过状态文件、或多个进程共用一个文件，
行为都不会如你所愿。

### 2. 只有优雅停机才触发最后一次保存

`kill -9`、断电、容器强制销毁都不会。`stateMachine:delay` 决定了你最多丢多少。

### 3. 状态在内存里，不在数据库里

它的规模上限就是你愿意放进内存的量。需要持久化大量业务数据的场景，
本框架不是合适的地方。

## 多进程

**不要多个进程共用同一个状态文件。** 恢复语义是整表替换，它们会互相覆盖。

需要跨进程共享状态请用 Celery 这类方案——本框架明确不做跨进程协调，
见[与其它方案对比](comparison.md)。
