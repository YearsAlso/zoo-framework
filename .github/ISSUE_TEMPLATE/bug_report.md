---
name: Bug 反馈 / Bug report
about: 报告一个可复现的缺陷 / Report a reproducible defect
title: "[Bug] "
labels: bug
assignees: ''
---

<!--
框架的设计前提是「错误输入必须大声失败」，所以完整的报错文本通常就是定位原因最快的路。
请尽量填完下面的「复现」与「错误输出」。/ This framework is designed to fail loudly on
bad input, so the full error text is usually the fastest route to the cause. Please fill in
"Reproduction" and "Error output" as completely as you can.
-->

## 环境 / Environment

| | |
|---|---|
| zoo-framework 版本 / version | <!-- `pip show zoo-framework` --> |
| Python 版本 / version | <!-- `python -V`，需要 3.13+ --> |
| 操作系统 / OS | |
| 调度模式 / scheduling mode | <!-- `worker:mode`：thread / thread_pool；`worker:pool:enable` 的值 --> |
| 解释器 / interpreter | <!-- `python -c "import sys; print(sys.executable)"` --> |

> 如果 `import zoo_framework` 本身失败，请先确认解释器 —— 裸 `python` 可能解析到一个
> 无法导入本包的旧环境。/ If the import itself fails, check the interpreter first.

## 复现步骤 / Steps to reproduce

1.
2.
3.

## 最小复现代码 / Minimal reproduction

```python
# 请贴出可以直接运行的最小代码，不要贴整个项目
```

## 期望行为 / Expected behaviour

<!-- 描述期望发生什么 -->

## 实际行为 / Actual behaviour

<!-- 描述实际发生了什么。如果是静默失效（没报错但行为不对），请特别说明 —— 这在本项目
     属于缺陷，我们需要知道。 -->

## 错误输出 / Error output

```
<!-- 完整的 traceback 或日志。不要只贴最后一行。 -->
```

## 配置 / Configuration

<!-- 相关配置片段（config.json 及其 _exports 引用的文件）。请删除任何敏感值。 -->

```json
```

## 补充信息 / Additional context

<!-- 首次出现的时间、是否可稳定复现、是否与特定平台有关等 -->
