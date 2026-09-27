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
