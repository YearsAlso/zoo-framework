# 变更：用户可见层 API 文档英文化（报错消息 + 公开 docstring）

## Why

英语母语用户 `pip install` 后的体验经实测存在三层不友好，严重程度排序：

1. **运行时报错乱码**——约 22 处 raise/log 中文消息；Windows GBK 控制台下中文消息直接变乱码（连「读不懂」都算不上）。跨平台 IO 能力 `cross-platform-io` 只覆盖文件 IO，未覆盖控制台 stderr 输出。
2. **`help()`/IDE 悬浮中文**——顶层与子包 `__init__` docstring、公开类 docstring 中文。
3. **内部注释 2549 行**——只在读源码时撞见，不在本变更范围。

本仓库的维护语言是中文（OpenSpec zh-CN、CLAUDE.md 约定），本变更**不改变维护语言**：只把「装上包就能看见的那一层」换成英文，内部注释、`docs/`、OpenSpec 正文维持中文。

## What Changes

- 报错消息（`raise`/`logger`/`print`）全部换英文，保留 `{key!r}` 等变量插值。
- 带有中文 docstring 的 `__init__.py`（顶层 + 子包）全部换英文。
- 各公开类/函数（`__all__` 导出面 + 用户直接 import 的文件，约 20 个文件）的模块/类/方法 docstring 换英文，Google-style 分节（`Args:`/`Returns:`）保持。
- 内部行注释（`#`）**不动**，维持中文。

## Capability Impact

- 修改 `aop`：`@params`/`@event`/`@worker` 装饰器语义不变，仅用户可见文案语言变化
- 修改 `cross-platform-io`：在其范围内新增控制台 stderr/stdout 用户信息语言的 SHALL
- 其余能力（`worker-scheduling`、`event-dispatch`、`scoped-container` 等）行为不变——异常类型、异常时机、异常字段（插值变量）保持不变，仅消息内容语言变化
