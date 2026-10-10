# API 参考

本分区由 **`mkdocstrings` 从代码 docstring 自动生成**，与实现同步，不手工维护。

| 页面 | 覆盖 |
|---|---|
| [运行时](runtime.md) | `Master` 与生命周期入口 |
| [Worker](workers.md) | 任务单元基类与内建 Worker |
| [调度](scheduler.md) | 调度模型、背压策略与派发 |
| [容器](container.md) | 作用域容器与作用域 |
| [状态](state.md) | 状态机、作用域与状态节点 |
| [事件](events.md) | 事件通道、反应器、优先级与重试 |
| [配置](config.md) | 各 `*Params` 配置类与配置解析 |
| [插件](plugins.md) | 插件注册与发现 |
| [原生执行](native.md) | Rust 原生任务契约与适配器 |
| [示例集](examples.md) | 使用片段（手工维护，非参考） |

> **这篇参考的可靠性**：每个签名、参数、返回值与异常都直接从源码提取。
> 若你发现页面与代码不符，那是 docstring 的问题，请提 PR 改 docstring，而不是改本页。
