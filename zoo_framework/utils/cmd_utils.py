"""cmd_utils - zoo_framework/utils/cmd_utils.py

模块功能描述:

作者: XiangMeng
版本: 0.5.1-beta

import os


class CmdUtils:
    """CmdUtils - 类功能描述"""
    @classmethod
    def cmd_read(cls, cmd):
        """执行cmd命令."""
        with os.popen(cmd) as p:
            response = p.read()
        return response.strip()

    @classmethod
    def cmd_write(cls, cmd):
        """执行cmd命令."""
        os.system(cmd)

    @classmethod
    def cmd_write_with_result(cls, cmd):
        """执行cmd命令."""
        return os.system(cmd)
"""
