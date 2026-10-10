# 运行时（Master）

生命周期入口：加载配置、注册 Worker、启动调度、优雅停机。

```python
from zoo_framework.core import Master
```

## Master

::: zoo_framework.core.master.Master
    options:
      show_source: true
      members:
        - __init__
        - register_worker
        - run
        - shutdown
        - get_health_report
        - get_worker_stats

## MasterConfig

::: zoo_framework.core.master.MasterConfig

## 参数与路径解析

::: zoo_framework.core.params_factory.ParamsFactory
::: zoo_framework.core.params_path.ParamsPath
