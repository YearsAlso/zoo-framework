"""file_utils - zoo_framework/utils/file_utils.py

文件工具模块，提供常用的文件操作功能。

功能：
- 文件读写操作
- 目录管理
- 路径处理
- 文件信息获取

作者: XiangMeng
版本: 0.5.1-beta

import os
import shutil


class FileUtils:
    """文件工具类

    提供各种文件操作相关的实用方法。
    """

    @classmethod
    def read_file(cls, file_path):
        """读取文件内容"""
        with open(file_path, encoding='utf-8') as f:
            return f.read()

    @classmethod
    def write_file(cls, file_path, content):
        """写入文件内容"""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

    @classmethod
    def append_file(cls, file_path, content):
        """追加文件内容"""
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(content)

    @classmethod
    def file_exists(cls, file_path):
        """检查文件是否存在"""
        return os.path.exists(file_path)

    @classmethod
    def create_directory(cls, dir_path):
        """创建目录"""
        os.makedirs(dir_path, exist_ok=True)

    @classmethod
    def delete_file(cls, file_path):
        """删除文件"""
        if os.path.exists(file_path):
            os.remove(file_path)

    @classmethod
    def delete_directory(cls, dir_path):
        """删除目录"""
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)

    @classmethod
    def list_files(cls, dir_path, pattern=None):
        """列出目录中的文件"""
        files = []
        for root, dirs, filenames in os.walk(dir_path):
            for filename in filenames:
                if pattern is None or pattern in filename:
                    files.append(os.path.join(root, filename))
        return files

    @classmethod
    def get_file_size(cls, file_path):
        """获取文件大小（字节）"""
        return os.path.getsize(file_path)

    @classmethod
    def get_file_extension(cls, file_path):
        """获取文件扩展名"""
        return os.path.splitext(file_path)[1]

    @classmethod
    def get_file_name(cls, file_path):
        """获取文件名（不含扩展名）"""
        return os.path.splitext(os.path.basename(file_path))[0]

    @classmethod
    def copy_file(cls, src_path, dst_path):
        """复制文件"""
        shutil.copy2(src_path, dst_path)

    @classmethod
    def move_file(cls, src_path, dst_path):
        """移动文件"""
        shutil.move(src_path, dst_path)
