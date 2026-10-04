---
name: doc-comment
description: 注释编写规范 Skill — Zoo Framework 项目的 Python docstring（Google-style）/单行注释与 Rust doc comment 编写规范（概述独占、分文件强制规范、绝对禁止场景），software-engineer 编码时强制遵循，doc-writer 补齐注释时同样使用；唯一事实源
---

# Doc Comment — 注释编写规范

Zoo Framework 项目代码的注释规范唯一事实源。**双用途**：
- **编码约束**：software-engineer 编写/修改代码时按本规范添加注释
- **补齐工具**：doc-writer 为已变更代码补齐缺失注释时按本规范执行

核心准则：**只补缺失注释、绝不堆砌冗余说明，所有注释统一简体中文，只描述业务含义，不复述代码逻辑**。

## 注释格式强制规则

### Docstring 结构规则

Google-style 小节标题（`Args:` / `Returns:` / `Raises:` / `Yields:`）必须各起独立小节，**严禁**与概述挤在同一行；概述一句话后空行再起小节：

```python
# ✅ 正确：概述 + 空行 + Google 小节
def dispatch(self, result: WorkerResult) -> None:
    """把 Worker 执行结果投递到对应主题的reactor。

    结果仅在 thread-pool 模式下经回调派发；普通线程模式结果被丢弃。

    Args:
        result: Worker 执行结果，携带 topic、content、cls_name

    Raises:
        KeyError: 目标通道未注册且不允许懒创建时
    """

# ❌ 错误：概述与 Args 同行
def dispatch(self, result):
    """投递结果。 Args: result 结果"""
```

### 单行注释

内部成员优先使用 `#` 单行注释：

```python
# 幂等初始化：存档存在且校验通过则加载，否则新建并挂滚动备份
self._load_or_init_state()
```

两种形式选择标准：
- **业务语义复杂**、需要多句描述 → 多行 Google-style docstring
- **一句话能说清** → `#` 单行注释或单行 docstring

## 分文件强制注释规范

### 1. Worker 子类（workers/*.py）
- 类顶部 docstring 说明职责、循环/一次性语义（`is_loop`）、线程模型
- `_execute()` 必须有 docstring 说明执行体业务作用与返回的 `WorkerResult` 内容
- 生命周期钩子（`_on_error`/`_on_done`/`_destroy_result`）覆写时说明副作用

### 2. 事件与反应堆（event/*.py、reactor/*.py）
- `@event` 装饰的 reactor 函数必须有 docstring：`Args:` 说明 topic/content 结构约定，`Returns:` 说明返回语义（通道两侧的契约文档）
- `response_mechanism` 等协议字段在定义处注释四种取值语义

### 3. Params 类（params/*.py、core/params_*.py）
- 每个 `ParamsPath(...)` 的行注释说明：配置键含义、默认值依据、aliases 吸收的历史键名
- 类顶部 docstring 说明对应关注点（worker/event/log/state_machine）

### 4. 状态机与持久化（statemachine/*.py、core/persistence_scheduler.py）
- `StateIndex`、`PersistenceStrategy` 公开方法必须有 docstring（含原子写/校验/备份约定）
- 涉及 pickle 存档兼容性的行为必须注释（格式、类名不可轻改）

### 5. 值对象与常量（workers/worker_*.py、constant/*.py）
- 类顶部 docstring 说明字段来源与消费方；含义不直观的常量值加行注释
- 自解释字段不重复注释（`topic`、`content`、`cls_name` 等基础字段）

### 6. Plugin 扩展点（plugin/*.py）
- `Plugin` ABC 的 `initialize(context)`/`destroy()` 契约必须有 docstring（`Args:` 说明 context 携带内容）

### 7. Rust 探针（bench/pyo3_probe/src/*.rs）
- 公开项必须有 `///` doc comment，首行一句话概述
- 可能 panic 加 `# Panics`；返回 `Result` 加 `# Errors`
- GIL 相关 `with_gil` 段加行注释说明为何必须在此持锁

## 绝对禁止添加注释的场景

1. `__init__` 里 `self.x = x` 式参数转存、自解释简单属性
2. 明显装饰器（`@cage`、`@property` 本身不需解释）
3. 简单 lambda / 一行能看懂的推导式
4. 纯注册/布线代码（channel 绑定、handler 注册行）
5. 测试里的断言复述
6. 已被规范 docstring 覆盖的内部私有短方法

## 工作约束

1. 仅新增/调整注释文本，**严禁改动任何业务代码逻辑**
2. 注释语言精简，一句话讲清业务目的
3. 若当前文件注释全部规范完整，仅输出：【文档校验完成】当前文件注释规范完整，无需补充
