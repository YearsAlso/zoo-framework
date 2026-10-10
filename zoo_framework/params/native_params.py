"""原生任务执行配置（独立键族 ``native:*``）.

纪律：本模块经 lazy import 使用（``Master._create_waiter`` 等处已有先例），
在 ``ParamsFactory`` 读完 config.json 之前被 import 会冻结在默认值——与既有
参数类一致，不新增例外。
"""

from zoo_framework.core import param
from zoo_framework.core.aop import params


@params
class NativeParams:
    # 原生任务执行总开关；默认关闭——未装/不启用原生扩展时框架一切如旧
    NATIVE_ENABLED = param(value="native:enabled", default=False)
    # 期望的执行契约版本；留空表示接受框架当前版本，经适配器与扩展握手比对
    NATIVE_CONTRACT_VERSION = param(value="native:contractVersion", default=0)
    # 按 Worker 名覆盖契约描述的路径前缀，实际键为
    # ``native:task:<task_name>:maxInputBytes`` 等。这不是配置项本身，
    # 而是拼装路径用的前缀，故不声明为 ParamsPath。
    NATIVE_TASK_PREFIX = "native:task"
