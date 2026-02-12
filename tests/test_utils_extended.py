"""Utils 模块测试

测试 LogUtils 和其他工具函数
"""

import pytest
import os
import tempfile
from zoo_framework.utils import LogUtils, FileUtils


class TestLogUtils:
    """LogUtils 测试类"""

    def test_info_logging(self):
        """测试 info 级别日志"""
        # 主要测试不抛出异常
        LogUtils.info("Test info message")

    def test_debug_logging(self):
        """测试 debug 级别日志"""
        LogUtils.debug("Test debug message")

    def test_warning_logging(self):
        """测试 warning 级别日志"""
        LogUtils.warning("Test warning message")

    def test_error_logging(self):
        """测试 error 级别日志"""
        LogUtils.error("Test error message")


class TestFileUtils:
    """FileUtils 测试类"""

    def test_file_exists_true(self):
        """测试文件存在检查 - 存在"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_file = f.name
        
        try:
            assert FileUtils.file_exists(temp_file) is True
        finally:
            os.unlink(temp_file)

    def test_file_exists_false(self):
        """测试文件存在检查 - 不存在"""
        assert FileUtils.file_exists("/nonexistent/file/path.txt") is False

    def test_dir_exists(self):
        """测试目录存在检查"""
        with tempfile.TemporaryDirectory() as temp_dir:
            assert FileUtils.dir_exists(temp_dir) is True
        
        assert FileUtils.dir_exists("/nonexistent/dir") is False

    def test_create_file(self):
        """测试创建文件"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.txt")
            
            FileUtils.create_file(file_path)
            
            assert os.path.exists(file_path)

    def test_mkdir(self):
        """测试创建目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = os.path.join(temp_dir, "newdir")
            
            FileUtils.mkdir(dir_path)
            
            assert os.path.exists(dir_path)
            assert os.path.isdir(dir_path)

    def test_get_file_name(self):
        """测试获取文件名"""
        assert FileUtils.get_file_name("/path/to/file.txt") == "file.txt"
        assert FileUtils.get_file_name("file.txt") == "file.txt"

    def test_get_file_parent(self):
        """测试获取父目录"""
        assert FileUtils.get_file_parent("/path/to/file.txt") == "/path/to"
