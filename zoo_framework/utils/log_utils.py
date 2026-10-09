import logging


class SafeStreamHandler(logging.StreamHandler):
    """A stream handler that never discards a whole log line over character encoding.

    When ``emit`` raises, logging's default implementation calls
    ``handleError``, and the result is **the whole log line vanishing
    together with the timestamp**, leaving only a
    ``--- Logging error ---`` and a stack trace on stderr. This handler
    writes the message in an encoding the target stream can represent and
    degrades unrepresentable characters to reversible escape sequences, so
    the line content and its timestamp are always written.

    Intended for logs with emoji or Chinese on non-UTF-8 consoles (e.g.
    ``cp936`` in a Chinese Windows environment).

    Semantic boundary: glyphs may be degraded (emoji become escape sequences
    standing for their code points), but **no line is ever lost**.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            stream = self.stream
            encoding = getattr(stream, "encoding", None) or "utf-8"
            # Encode once against the target encoding, letting it fail, and
            # replace unrepresentable characters with escape sequences, then
            # decode back to a string - the write afterwards cannot fail
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
    """Write the current run identity into structured fields of the log record.

    The fields are ``run_id`` / ``session_id``. It **does not change the
    format string**, so existing text output is byte-identical, but records
    gain two fields extractable programmatically - e.g. filtering by
    ``run_id`` to pick out all logs of one run.

    The values come from the run identity of the **current context** (see
    :mod:`zoo_framework.core.run_identity`). When no identity is bound, both
    fields are ``None``; a value MUST NOT be invented.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Deferred import: this module is loaded early in the package import;
        # run_identity lives inside the core package, and a top-level import
        # would drag in core.__init__'s import order
        from zoo_framework.core.run_identity import current_identity

        identity = current_identity()
        record.run_id = identity.run_id if identity is not None else None
        record.session_id = identity.session_id if identity is not None else None
        return True


def _install_identity_filter() -> None:
    """Attach the identity filter to the root logger.

    Idempotent: repeated imports or calls never attach a second one.
    ``LogUtils`` logs through the root logger, so attaching at the root
    covers all of the framework's own logs.
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
    def debug(cls, message: str, cls_name: str | None = None) -> None:
        if cls_name is None:
            cls_name = cls.__name__
        message = cls._format_message(message, cls_name)
        logging.debug(message)

    @classmethod
    def info(cls, message: str, cls_name: str | None = None) -> None:
        if cls_name is None:
            cls_name = cls.__name__
        message = cls._format_message(message, cls_name)
        logging.info(message)

    @classmethod
    def warning(cls, message: str, cls_name: str | None = None) -> None:
        if cls_name is None:
            cls_name = cls.__name__
        message = cls._format_message(message, cls_name)
        logging.warning(message)

    @classmethod
    def error(cls, message: str, cls_name: str | None = None) -> None:
        if cls_name is None:
            cls_name = cls.__name__
        message = cls._format_message(message, cls_name)
        logging.error(message)
