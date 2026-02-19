import os


class CmdUtils:
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
