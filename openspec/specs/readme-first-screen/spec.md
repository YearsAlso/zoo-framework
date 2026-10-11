# readme-first-screen Specification

## Purpose
定义 README 首屏的转化契约与发布物卫生规则，使首次到访者在 10 秒内得到"这是什么 / 解决什么 / 凭什么选它"的答案，且发布物中不泄漏作者待办、不出现互相矛盾的测试数量。

## Requirements

### Requirement: 首屏信息结构

README（双语各自）SHALL 在徽章与分隔线后的 8 行内依次出现：一句话定位（MUST 同时含 "in-process"、无 broker 表述与"为 AI 生成代码而设计"）、目标读者或问题场景叙述、demo 图占位标记；随后 SHALL 立即出现一段 ≤30 行的完整可运行最小示例。

#### Scenario: 首屏三件事在 8 行内可见
- **WHEN** 阅读 README 双语任一半的前 8 个正文行（logo/徽章/跳转之后）
- **THEN** 定位句、问题场景、demo 占位三要素均已出现

#### Scenario: 最小示例可独立运行
- **WHEN** 把 README 首屏的最小 Python 代码块复制到空目录的 main.py 并以 Python 3.13 运行
- **THEN** 程序启动并打印 Worker 计数输出，无需任何额外文件

### Requirement: 发布物不含作者待办

README 双语半 SHALL NOT 含任何作者备忘性质的注释块（录制工具推荐、操作步骤、占位说明长文）。demo 图位置 SHALL 以单行注释标记 `TODO(demo)` 表达，其格式在双语半一致。

#### Scenario: 备忘注释清零
- **WHEN** 执行 `grep -in "ScreenToGif\|asciinema" README.md README.zh.md`
- **THEN** 零命中

### Requirement: 测试数量声明单一真源

README 与 CONTRIBUTING（双语合计全部出现处）对测试套件规模的声明 SHALL 采用"见 CI badge"表述；SHALL NOT 出现裸写的用例总数（如 367 / 662 / 837）；双语两半的表述 MUST 平行。

#### Scenario: 消除矛盾数字
- **WHEN** 执行 `grep -cn "367\|662" README.md README.zh.md CONTRIBUTING.md`
- **THEN** 每个文件命中数均为 0
- **AND** 提及测试规模之处（如有）引导读者查看 CI Tests badge

### Requirement: 文档站首页面向用户

`docs/README.md` SHALL 以用户指南入口为第一导航（这是什么 / 5 分钟上手 / 核心概念 / API / 常见问题）， SHALL 把"架构设计 / 贡献指南 / 调试指南"降级入贡献者子章节；其核心概念示意 MUST 与 README 核心概念表的语义一致（Master = 生命周期入口、FIFO = 每通道队列）。

#### Scenario: 首页导航顺序
- **WHEN** 阅读 docs/README.md 导航区
- **THEN** 用户指南条目先于贡献者条目

#### Scenario: 隐喻语义一致
- **WHEN** 比较 docs/README.md 与 README.md 对 Master / FIFO 的表述
- **THEN** 两者语义一致（生命周期入口 / 每通道队列），无"园长"等旧隐喻独词
