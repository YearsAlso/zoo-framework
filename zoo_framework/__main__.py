"""`python -m zoo_framework` 的入口.

命令行的实现在 `zoo_framework.cli`。这里只做转发，使模块方式启动这一历史入口
继续可用——它的存在不影响 `zoo_framework.cli` 作为唯一实现的位置。
"""

from zoo_framework.cli import zfc

if __name__ == "__main__":
    zfc()
