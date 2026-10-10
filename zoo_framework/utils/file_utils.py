import locale
import os
import shutil

from .log_utils import LogUtils


class FileUtils:
    # The unified encoding for text files.
    # MUST be declared explicitly, MUST NOT rely on the platform default
    # encoding - the default on Windows in a Chinese locale is GBK, which
    # would parse the same config into different values on different
    # platforms (silently).
    DEFAULT_ENCODING = "utf-8"

    @classmethod
    def read_text(cls, path: str) -> str:
        """Read a text file, preferring UTF-8 decoding.

        On decode failure, fall back to the platform default encoding and log
        a warning: the fallback keeps files written by older versions on
        non-UTF-8 platforms readable; the warning keeps that debt visible -
        a silent fallback would leave "mojibake that looks fine" configs
        undetectable.

        Args:
            path: the file path

        Returns:
            the file content
        """
        with open(path, "rb") as f:
            raw = f.read()

        try:
            return raw.decode(cls.DEFAULT_ENCODING)
        except UnicodeDecodeError:
            fallback = locale.getpreferredencoding(False)
            LogUtils.warning(
                f"file {path} is not UTF-8; it was read with the platform default encoding {fallback};"
                "consider migrating the file to UTF-8",
                cls.__name__,
            )
            return raw.decode(fallback, errors="replace")

    @classmethod
    def write_text(cls, path: str, content: str) -> None:
        r"""Write a text file as UTF-8.

        No newline translation (``newline="\\n"``): first, so the artifact is
        byte-identical on all platforms; second, so "read then write back"
        is idempotent - platform-dependent newline translation would add an
        extra ``\\r`` to CRLF on every read-write round trip.

        Args:
            path: the file path
            content: the content to write
        """
        with open(path, "w", encoding=cls.DEFAULT_ENCODING, newline="\n") as f:
            f.write(content)

    @classmethod
    def dir_exists(cls, path: str) -> bool:
        return os.path.exists(path)

    @classmethod
    def file_exists(cls, path: str) -> bool:
        if cls.is_dir(path):
            return False
        return os.path.exists(path)

    @classmethod
    def get_file_parent(cls, path: str) -> str:
        return os.path.dirname(path)

    @classmethod
    def get_file_name(cls, path: str) -> str:
        return os.path.basename(path)

    @classmethod
    def mkdir(cls, path: str) -> None:
        if cls.dir_exists(path):
            return
        os.mkdir(path)

    @classmethod
    def dir_exists_and_create(cls, path: str) -> bool:
        if cls.dir_exists(path):
            return True

        os.makedirs(path)
        return True

    @classmethod
    def is_dir(cls, path: str) -> bool:
        # [Behavior fix, not a pure annotation] The original implementation
        # wrote `os.path.isdir(path)` with **no return**, so is_dir always
        # returned None. This is not an "un-annotated" case - the return
        # value was **dropped**: at its call site, the `if cls.is_dir(path):
        # return False` in `file_exists` therefore never held, and a
        # directory was treated as an existing file. Only with the return
        # added does is_dir's semantics match its name and the
        # `os.path.isdir` it calls.
        # The blast radius has been verified as **empty**: is_dir has exactly
        # one call site in the repo (`file_exists`), and the three call
        # sites of `file_exists` (the config path in `params_factory.py`,
        # and the pickle paths in `persistence_scheduler.py` and
        # `state_machine_work.py`) **all pass files**, so "directories no
        # longer count as existing" changes no existing call path.
        return os.path.isdir(path)

    @classmethod
    def file_remove(cls, path: str) -> None:
        if not cls.file_exists(path):
            return

        os.remove(path)

    @classmethod
    def get_file_size(cls, path: str) -> int:
        if not cls.file_exists(path):
            raise Exception(f"File {path} not found")

        if not os.path.isfile(path):
            raise Exception(f"File {path} not found")

        return os.path.getsize(path)

    @classmethod
    def create_file(cls, path: str) -> None:
        with open(path, "w", encoding=cls.DEFAULT_ENCODING):
            pass

    @classmethod
    def copy_file(cls, src_path: str, target_path: str) -> None:
        shutil.copy(src_path, target_path)
