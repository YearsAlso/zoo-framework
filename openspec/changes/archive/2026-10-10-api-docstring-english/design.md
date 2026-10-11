# Design: 用户可见层 API 文档英文化

## Context

实测盘点（2026-10-09，Windows 11 GBK 控制台 + CPython 3.13.14）：

| 层 | 现状 | 英语用户观感 |
|---|---|---|
| `help(zoo_framework)` 顶层 | 中文 docstring + 版本号过期写 0.8.0 | **乱码**（GBK 控制台） |
| raise/log/print 消息 | 22 处中文，9 个文件 | 乱码或读不懂 |
| 公开类 docstring | ~20 个文件有中文 | IDE 悬浮读不懂 |
| 内部行注释 | ~2500 行中文 | 读源码才撞见 |

**关键抉择**：范围裁到「用户可见层」，内部注释/`docs/`/OpenSpec 正文维持中文——

- 与 OpenSpec zh-CN 约定不冲突（config.yaml 规定 spec 正文 zh-CN）
- CLAUDE.md 「注释用中文」约定保留（内部注释不动）
- 单人维护成本可控（标注文档语言是发布面参数，不是开发流程参数）

## Goals / Non-Goals

- **Goal**： traceback/`help()`/IDE 悬浮提示对英语母语用户可读
- **Goal**： Windows GBK 控制台不再出现框架自身的乱码输出
- **Non-Goal**： 不做 i18n 框架（消息直接写英文，不引入 gettext/MessageFactory）
- **Non-Goal**： 不动内部行注释、`docs/`、模板注释、config comments
- **Non-Goal**： 不动异常类型、异常时机、插值变量

## Decisions

### D1: 异常消息只换语言，不改契约

`raise ValueError(f"无法识别的作用域 {scope_kind!r}；可选 {list(ScopeKind.ALL)}")`
→ `raise ValueError(f"unknown scope kind {scope_kind!r}; expected one of {list(ScopeKind.ALL)}")`

规则：
- 异常类型不变；插值变量与 `!r` 格式不变（测试对异常类型的断言不受影响）
- 「分号 + 可选列表」结构保留，仅语言换
- 语义级关键词（如 `MUST NOT 静默退回进程级`）译为对应英文 MUST NOT 语义，不软化

### D2: docstring 只换公开面，作者/版本信息保留中文署名

- 模块 docstring、类 docstring、有中文的方法 docstring 全换英文
- `__author__`/`__email__`/`__license__` 不动（不是文档）
- docstring 内的示例（`Examples:`）段落中英文 affection 相同，统一英文

### D3: 内部注释不动

`#` 行注释维持中文。理由：内部读者（维护者，中文）效率优先；英文用户读源码时至少已具备读 doc 的上下文。

### D4: 验证方式

1. `help('zoo_framework')` 在 GBK 控制台无乱码、无中文（stdout 重定向到文件后 `grep -P '[\x{4e00}-\x{9fff}]'` 为空）
2. `grep -rPn '(raise|logger|print).*[\x{4e00}-\x{9fff}]' zoo_framework --include='*.py'` 零命中
3. `pytest` 全绿（异常类型断言全数不变）
4. `mypy` 零错误（docstring 类型 stub 无关，预期零影响）
