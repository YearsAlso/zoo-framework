from typing import TypeVar, cast

# ruff 的 UP047 要求改用 PEP 695 的 `def param[T](...)` 语法，但 **mypy 1.7.1 尚不支持
# PEP 695**（报 "PEP 695 generics are not yet supported"）——而 1.7.1 既是 pre-commit 钉住的
# 版本、也是 CI 安装的那版。两个工具要求相反，故保留 TypeVar 写法并在此定向 noqa，
# 而不是让任何一方报错。升级 mypy 才能解掉这条（属依赖变更，不在本变更范围）。
_T = TypeVar("_T")


class ParamsPath:
    """配置项路径。

    支持为同一配置项声明多个候选路径：按 ``value`` 优先、``aliases`` 依次回退的顺序
    解析，用于兼容历史键名。任一候选缺失时由调用方决定回退到默认值。

    Args:
        value: 首选配置路径，形如 ``worker:pool:size``
        default: 全部候选都缺失时使用的默认值
        aliases: 备选配置路径，按顺序回退
    """

    def __init__(self, value, default="", aliases=None):
        self.value = value
        self.default = default
        self.aliases = list(aliases or [])

    def get_default(self):
        return self.default

    def get_value(self):
        return self.value

    def get_aliases(self) -> list:
        return list(self.aliases)


def param(  # noqa: UP047 — 见文件头说明：mypy 1.7.1 不支持 PEP 695，两个工具要求相反
    value: str, default: _T, aliases: list[str] | None = None
) -> _T:
    """声明一个参数项。

    `@params` 会在导入期把类属性**改写为解析后的字面值**，因此该属性解析后的静态类型理应就是
    那个字面值的类型，而不是 `ParamsPath`。直接用 `ParamsPath(...)` 声明会让静态类型停留在
    `ParamsPath`，于是凡把它当 `str` / `int` 使用的地方都报类型错误（全仓库曾有 14 处声明、
    7 条此类错误）。本封装让声明处直接得到正确的静态类型，**运行期仍返回 `ParamsPath` 实例**
    （`cast` 是空操作），供 `@params` 读取路径与默认值——配置机制不变。

    Args:
        value: 首选配置路径，形如 ``worker:pool:size``
        default: 全部候选缺失时使用的默认值；**其类型即该项解析后的静态类型**
        aliases: 备选配置路径，按顺序回退

    Returns:
        静态类型取自 ``default`` 的类型；运行期是 ``ParamsPath`` 实例
    """
    return cast("_T", ParamsPath(value=value, default=default, aliases=aliases))
