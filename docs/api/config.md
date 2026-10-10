# 配置

## 先看这里

**配置键的权威清单是[配置参考](../guides/config-reference.md)** ——它是一张按段整理的表，
列出每个键、默认值与说明。本页只是从源码自动生成的附表。

> **为什么这里不是主源**：配置类使用 `@params` 描述符模式（类属性在导入时被替换为
> 配置项描述符），因此没有 `__init__` 签名、也没有逐属性的 docstring，
> griffe 只能渲染出源码原文。**契约级的键位说明只能由人工维护**，
> 放在[配置参考](../guides/config-reference.md)里。

加载方式：

```python
from zoo_framework.core import Master
from zoo_framework.core.master import MasterConfig

master = Master()                                          # 读 ./config.json
master = Master(MasterConfig(config_path="./config.json"))  # 指定路径
```

## 配置类源码

::: zoo_framework.params.worker_params.WorkerParams
    options:
      show_source: true

::: zoo_framework.params.event_params.EventParams
    options:
      show_source: true

::: zoo_framework.params.state_machine_params.StateMachineParams
    options:
      show_source: true

::: zoo_framework.params.log_params.LogParams
    options:
      show_source: true

::: zoo_framework.params.native_params.NativeParams
    options:
      show_source: true

::: zoo_framework.params.adaptive_params.AdaptiveParams
    options:
      show_source: true
