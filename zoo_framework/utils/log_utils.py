import logging


class SafeStreamHandler(logging.StreamHandler):
    """不会因字符编码而丢弃整行日志的流处理器.

    ``logging`` 的默认实现在 ``emit`` 抛异常时会调用 ``handleError``，结果是**整条日志
    连同时间戳一起消失**，只在 stderr 留下一段 ``--- Logging error ---`` 与堆栈。
    本处理器把消息按目标流能表示的编码写出，无法表示的字符降级为可还原的转义序列，
    从而保证行内容与时间戳始终被写出。

    适用于非 UTF-8 的控制台（例如 Windows 中文环境的 ``cp936``）上的含 emoji 或中文的日志。

    语义边界：字形可能被降级（emoji 会变成代表其码位的转义序列），但**不会丢行**。
    """

    def emit(self, record):
        try:
            message = self.format(record)
            stream = self.stream
            encoding = getattr(stream, "encoding", None) or "utf-8"
            # 先按目标编码做一次允许失败的编码，把无法表示的字符替换为转义序列，
            # 再解码回字符串——此时写出必然成功
            safe = message.encode(encoding, errors="backslashreplace").decode(
                encoding, errors="replace"
            )
            stream.write(safe + self.terminator)
            self.flush()
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)


class IdentityFilter(logging.Filter):
    """把当前运行标识写入日志记录的结构化字段.

    字段名为 ``run_id`` / ``session_id``。它**不改变格式串**，因此既有的文本输出
    一字不变，但记录上多了两个可被程序化提取的字段——例如按 ``run_id`` 过滤出
    一次运行产生的全部日志。

    取值来自**当前上下文**的运行标识（见 :mod:`zoo_framework.core.run_identity`）。
    未绑定标识时两个字段为 ``None``，MUST NOT 编造值。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # 延迟导入：本模块在包导入早期被加载，而 run_identity 位于 core 包内，
        # 顶层导入会卷入 core.__init__ 的导入顺序
        from zoo_framework.core.run_identity import current_identity

        identity = current_identity()
        record.run_id = identity.run_id if identity is not None else None
        record.session_id = identity.session_id if identity is not None else None
        return True


def _install_identity_filter() -> None:
    """把标识过滤器挂到根日志器上.

    幂等：重复导入或重复调用都不会挂第二个。``LogUtils`` 走的是根日志器，因此
    过滤器挂在根上即可覆盖框架自身的全部日志。
    """
    root = logging.getLogger()
    if not any(isinstance(existing, IdentityFilter) for existing in root.filters):
        root.addFilter(IdentityFilter())


_install_identity_filter()


class LogUtils:
    @classmethod
    def _format_message(cls, message: str, cls_name: str) -> str:
        return f"{cls_name} - {message}"

    @classmethod
    def debug(cls, message: str, cls_name: str | None = None):
        if cls_name is None:
            cls_name = cls.__name__
        message = cls._format_message(message, cls_name)
        logging.debug(message)

    @classmethod
    def info(cls, message: str, cls_name: str | None = None):
        if cls_name is None:
            cls_name = cls.__name__
        message = cls._format_message(message, cls_name)
        logging.info(message)

    @classmethod
    def warning(cls, message: str, cls_name: str | None = None):
        if cls_name is None:
            cls_name = cls.__name__
        message = cls._format_message(message, cls_name)
        logging.warning(message)

    @classmethod
    def error(cls, message: str, cls_name: str | None = None):
        if cls_name is None:
            cls_name = cls.__name__
        message = cls._format_message(message, cls_name)
        logging.error(message)
