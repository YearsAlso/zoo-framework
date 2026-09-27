import locale
import os
import shutil

from .log_utils import LogUtils


class FileUtils:
    # 文本文件的统一编码。
    # MUST 显式声明，MUST NOT 依赖运行平台的默认编码——Windows 中文环境的默认编码是
    # GBK，会让同一份配置在不同平台上被解析成不同的值（且不报错）。
    DEFAULT_ENCODING = "utf-8"

    @classmethod
    def read_text(cls, path) -> str:
        """读取文本文件，优先按 UTF-8 解码.

        解码失败时回退到平台默认编码并输出告警：回退是为了让旧版本在非 UTF-8 平台上
        写出的文件仍可读取，告警是为了让这笔技术债可见——静默回退会让"读出来是乱码
        但看起来正常"的配置无从察觉。

        Args:
            path: 文件路径

        Returns:
            文件内容
        """
        with open(path, "rb") as f:
            raw = f.read()

        try:
            return raw.decode(cls.DEFAULT_ENCODING)
        except UnicodeDecodeError:
            fallback = locale.getpreferredencoding(False)
            LogUtils.warning(
                f"文件 {path} 不是 UTF-8 编码，已按平台默认编码 {fallback} 读取；"
                "建议将该文件迁移为 UTF-8",
                cls.__name__,
            )
            return raw.decode(fallback, errors="replace")

    @classmethod
    def write_text(cls, path, content: str) -> None:
        r"""以 UTF-8 写入文本文件.

        不启用换行翻译（``newline="\\n"``）：一是让产物在所有平台上字节一致，
        二是保证"读出再写回"是幂等的——平台相关的换行翻译会让 CRLF 在每次
        读-写往返中多出一个 ``\\r``。

        Args:
            path: 文件路径
            content: 待写入的内容
        """
        with open(path, "w", encoding=cls.DEFAULT_ENCODING, newline="\n") as f:
            f.write(content)

    @classmethod
    def dir_exists(cls, path):
        return os.path.exists(path)

    @classmethod
    def file_exists(cls, path):
        if cls.is_dir(path):
            return False
        return os.path.exists(path)

    @classmethod
    def get_file_parent(cls, path):
        return os.path.dirname(path)

    @classmethod
    def get_file_name(cls, path):
        return os.path.basename(path)

    @classmethod
    def mkdir(cls, path):
        if cls.dir_exists(path):
            return
        os.mkdir(path)

    @classmethod
    def dir_exists_and_create(cls, path) -> bool:
        if cls.dir_exists(path):
            return True

        os.makedirs(path)
        return True

    @classmethod
    def is_dir(cls, path):
        os.path.isdir(path)

    @classmethod
    def file_remove(cls, path):
        if not cls.file_exists(path):
            return

        os.remove(path)

    @classmethod
    def get_file_size(cls, path):
        if not cls.file_exists(path):
            raise Exception(f"File {path} not found")

        if not os.path.isfile(path):
            raise Exception(f"File {path} not found")

        return os.path.getsize(path)

    @classmethod
    def create_file(cls, path):
        with open(path, "w", encoding=cls.DEFAULT_ENCODING):
            pass

    @classmethod
    def copy_file(cls, src_path, target_path):
        shutil.copy(src_path, target_path)
