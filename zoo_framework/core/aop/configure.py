from typing import Any

from zoo_framework.utils import LogUtils
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict

# 创建一个线程安全的字典，用于存储配置函数
#
# 【已知欠债】模块级注册表、进程级共享；须由测试单独复位（见
# tests/test_scaffold_cli_contract.py 的清理辅助）。属容器外、未收编的载体；依据与判据见
# specs/scoped-container 的「框架自身的进程级共享 MUST 被显式归类」。
config_funcs: ThreadSafeDict[str, Any] = ThreadSafeDict()

# 注册封状态（变更 aop-determinism / issue #51）：@configure 的注册发生在**导入时**，
# Master 构造时遍历并**无参调用**一次。封之后的注册不属于"当前这个 Master 的消费
# 窗口"——历史上的形态是静默失效（若后续再无 Master，它默默蒸发）。现改为：
# 照常登记 + 大声告警"只有下一个 Master() 会消费它"。
# 为什么不硬报错：同一进程内重复运行入口（测试、reloader、notebook）会重新导入
# 配置模块再注册，随后紧接新的 Master()——这是脚手架契约测试锁定的合法形态
# （test_scaffold_cli_contract 的 assertions_survive_prior_runs），封死会破它。
# 注意另一半——模块"从未被导入"导致注册表缺项——在运行时不可观测（不导入就没有
# 任何代码可执行），框架不承诺发现它；唯一缓解是**入口显式 import**全部含
# @configure 的模块（脚手架模板已如此产出，契约由"每条生成导入都真实可执行"
# 守护）。该不对称已写进 specs/aop 的条款。
_sealed = False


def seal_config_funcs() -> None:
    """封住注册表：Master 消费完 config_funcs 后调用（#51）."""
    global _sealed
    _sealed = True


def unseal_config_funcs_for_tests() -> None:
    """解封（测试接缝）：每个用例前由 conftest 复位，避免跨用例泄漏."""
    global _sealed
    _sealed = False


def configure(topic: str):
    """装饰器工厂函数，用于将函数注册到指定的主题下。

    注册时机 MUST 在 Master 构造之前（导入时副作用即为此设计）；封后的注册
    照常登记但 MUST 大声告警——"只有下一个 Master() 会消费它"，若无后续构造
    则它默默失效，这正是历史上静默的形态（#51）。

    参数:
        topic (str): 主题名称，用于标识配置函数的分类或用途。

    返回:
        function: 返回一个装饰器函数，该装饰器将传入的函数注册到 config_funcs 字典中。
    """

    def inner(func):
        if _sealed:
            LogUtils.warning(
                f"@configure('{topic}') was registered after a Master was already constructed:"
                "the current instance will not consume it; it only takes effect when the next Master() is constructed;"
                "if no further Master is constructed in this process, this registration has no effect."
            )
        # 将传入的函数以主题为键存储到线程安全字典中
        config_funcs[topic] = func
        return func

    return inner
