import os


class CmdUtils:
    """执行 shell 命令的工具.

    【安全说明——这是**有意保留**，不是遗漏】本类的契约就是"把调用方给的命令串交给
    shell 执行"（见各方法的 ``cmd`` 参数），因此 `os.popen` / `os.system` 触发的
    **B605（start_process_with_a_shell，shell 注入面）是这一契约的固有属性**，不是
    可改掉的实现细节：能保住契约的替代写法（如 `shlex.split` + `subprocess.run(shell=False)`）
    会丢掉管道、重定向、`&&` 等 shell 语义，属**语义变更**，不在这里替作者决定；而
    `os.system` 的返回值语义（退出码）与 `popen().read()` 的（标准输出）也不相同。
    故按仓库既有做法（见 `persistence_scheduler.py` 对 pickle 的处理）用**定向 `# nosec`**
    收口，并把风险写在这里而不是抹掉。

    **风险边界**：本类在仓库内**零调用点**（仅经 `utils/__init__` 的 `__all__` 导出，
    属公开 API）。真正的风险取决于**调用方**是否把不可信输入拼进 ``cmd`` ——
    这个判断在调用方，不在本类。
    """

    @classmethod
    def cmd_read(cls, cmd: str) -> str:
        """执行cmd命令."""
        with os.popen(cmd) as p:  # nosec B605
            response = p.read()
        return response.strip()

    @classmethod
    def cmd_write(cls, cmd: str) -> None:
        """执行cmd命令."""
        os.system(cmd)  # nosec B605

    @classmethod
    def cmd_write_with_result(cls, cmd: str) -> int:
        """执行cmd命令."""
        return os.system(cmd)  # nosec B605
