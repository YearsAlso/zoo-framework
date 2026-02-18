"""工具类测试模块

测试工具类功能
"""

import os
import tempfile
import pytest

from zoo_framework.utils import LogUtils, FileUtils
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict


class TestLogUtils:
    """LogUtils 测试类"""

    def test_log_utils_methods(self):
        """测试 LogUtils 方法可以正常调用"""
        # 这些调用不应该抛出异常
        LogUtils.info("Test info message")
        LogUtils.error("Test error message")
        LogUtils.debug("Test debug message")


class TestFileUtils:
    """FileUtils 测试类"""

    def test_file_exists(self):
        """测试文件存在检查"""
        # 已存在的文件
        assert FileUtils.file_exists("pyproject.toml") is True

        # 不存在的文件
        assert FileUtils.file_exists("nonexistent_file_xyz.txt") is False

    def test_dir_exists(self):
        """测试目录存在检查"""
        assert FileUtils.dir_exists("zoo_framework") is True
        # dir_exists 只是检查路径是否存在，不区分文件和目录
        assert FileUtils.dir_exists("nonexistent_dir_xyz") is False

    def test_get_file_parent(self):
        """测试获取文件父目录"""
        parent = FileUtils.get_file_parent("zoo_framework/core/master.py")
        assert parent == "zoo_framework/core"

    def test_get_file_name(self):
        """测试获取文件名"""
        name = FileUtils.get_file_name("zoo_framework/core/master.py")
        assert name == "master.py"

    def test_mkdir(self):
        """测试创建目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "test_subdir")
            FileUtils.mkdir(test_dir)
            assert os.path.exists(test_dir)

    def test_dir_exists_and_create(self):
        """测试目录存在并创建"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = os.path.join(tmpdir, "nested", "dirs")
            result = FileUtils.dir_exists_and_create(test_dir)
            assert result is True
            assert os.path.exists(test_dir)

    def test_create_and_remove_file(self):
        """测试创建和删除文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")

            # 创建文件
            FileUtils.create_file(test_file)
            assert os.path.exists(test_file)

            # 删除文件
            FileUtils.file_remove(test_file)
            assert not os.path.exists(test_file)

    def test_copy_file(self):
        """测试复制文件"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            temp_path = f.name
            f.write("content to copy")

        try:
            dest_path = temp_path + ".copy"
            FileUtils.copy_file(temp_path, dest_path)

            assert os.path.exists(dest_path)

            os.unlink(dest_path)
        finally:
            os.unlink(temp_path)

    def test_get_file_size(self):
        """测试获取文件大小"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            temp_path = f.name
            f.write("12345")  # 5 bytes

        try:
            size = FileUtils.get_file_size(temp_path)
            assert size == 5
        finally:
            os.unlink(temp_path)

    def test_get_file_size_not_found(self):
        """测试获取不存在的文件大小"""
        with pytest.raises(Exception):
            FileUtils.get_file_size("nonexistent_file_xyz.txt")


class TestThreadSafeDict:
    """ThreadSafeDict 测试类"""

    def test_thread_safe_dict_init(self):
        """测试 ThreadSafeDict 初始化"""
        d = ThreadSafeDict()
        assert d is not None

    def test_thread_safe_dict_set_get(self):
        """测试 ThreadSafeDict 设置和获取"""
        d = ThreadSafeDict()
        d["key"] = "value"
        assert d["key"] == "value"

    def test_thread_safe_dict_get_method(self):
        """测试 ThreadSafeDict get 方法"""
        d = ThreadSafeDict()
        d["key"] = "value"
        assert d.get("key") == "value"

    def test_thread_safe_dict_keys(self):
        """测试 ThreadSafeDict 获取所有键"""
        d = ThreadSafeDict()
        d["key1"] = "value1"
        d["key2"] = "value2"

        keys = d.get_keys()
        assert "key1" in keys
        assert "key2" in keys

    def test_thread_safe_dict_delete(self):
        """测试 ThreadSafeDict 删除"""
        d = ThreadSafeDict()
        d["key"] = "value"
        del d["key"]

        assert d.get("key") is None

    def test_thread_safe_dict_contains(self):
        """测试 ThreadSafeDict contains"""
        d = ThreadSafeDict()
        d["key"] = "value"

        assert "key" in d
        assert "nonexistent" not in d

    def test_thread_safe_dict_has_key(self):
        """测试 ThreadSafeDict has_key"""
        d = ThreadSafeDict()
        d["key"] = "value"

        assert d.has_key("key") is True
        assert d.has_key("nonexistent") is False

    def test_thread_safe_dict_pop(self):
        """测试 ThreadSafeDict pop"""
        d = ThreadSafeDict()
        d["key"] = "value"

        value = d.pop("key")
        assert value == "value"
        assert d.get("key") is None

    def test_thread_safe_dict_values(self):
        """测试 ThreadSafeDict values"""
        d = ThreadSafeDict()
        d["key1"] = "value1"
        d["key2"] = "value2"

        values = d.values()
        assert "value1" in values
        assert "value2" in values

    def test_thread_safe_dict_items(self):
        """测试 ThreadSafeDict items"""
        d = ThreadSafeDict()
        d["key"] = "value"

        items = d.items()
        assert ("key", "value") in items
