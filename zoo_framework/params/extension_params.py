"""扩展包分发配置（独立键族 ``plugin:*``）.

纪律：本模块经 lazy import 使用（在 ``load_extensions`` 内导入），在
``ParamsFactory`` 读完 config.json 之前被 import 会冻结在默认值——与既有参数类一致，
不新增例外。

刻意**只声明一个布尔键**：``@params`` 会把解析结果写回**类属性**，若在此声明路径
列表（list）会被 ``tests/test_process_state_registry.py`` 判为未登记的类级可变容器。
来源根目录改以显式参数传入，不走配置。
"""

from zoo_framework.core import param
from zoo_framework.core.aop import params


@params
class ExtensionParams:
    # 项目级扩展包是否受显式信任；默认关闭——未配置时不加载任何项目级扩展包
    TRUST_PROJECT = param(value="plugin:trustProject", default=False)
