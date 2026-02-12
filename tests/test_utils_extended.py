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

    def test_create_file(self):
        """测试创建文件"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.txt")
            
            FileUtils.create_file(file_path, "test content")
            
            assert os.path.exists(file_path)
            with open(file_path, 'r') as f:
                assert f.read() == "test content"
