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
        LogUtils.info("Test with module", module="TestModule")

    def test_debug_logging(self):
        """测试 debug 级别日志"""
        LogUtils.debug("Test debug message")
        LogUtils.debug("Test with module", module="TestModule")

    def test_warning_logging(self):
        """测试 warning 级别日志"""
        LogUtils.warning("Test warning message")
        LogUtils.warning("Test with module", module="TestModule")

    def test_error_logging(self):
        """测试 error 级别日志"""
        LogUtils.error("Test error message")
        LogUtils.error("Test with module", module="TestModule")
        LogUtils.error("Test with exception", exception=ValueError("test"))

    def test_structured_log(self):
        """测试结构化日志"""
        LogUtils.structured_log(
            level="info",
            message="Test structured log",
            module="TestModule",
            extra={"key1": "value1", "key2": 123}
        )


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

    def test_read_file(self):
        """测试读取文件"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            temp_file = f.name
        
        try:
            content = FileUtils.read_file(temp_file)
            assert content == "test content"
        finally:
            os.unlink(temp_file)

    def test_write_file(self):
        """测试写入文件"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.txt")
            
            FileUtils.write_file(file_path, "test content")
            
            assert os.path.exists(file_path)
            with open(file_path, 'r') as f:
                assert f.read() == "test content"

    def test_ensure_dir(self):
        """测试确保目录存在"""
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = os.path.join(temp_dir, "nested", "dir")
            
            FileUtils.ensure_dir(dir_path)
            
            assert os.path.exists(dir_path)
            assert os.path.isdir(dir_path)

    def test_get_file_extension(self):
        """测试获取文件扩展名"""
        assert FileUtils.get_file_extension("test.txt") == ".txt"
        assert FileUtils.get_file_extension("test.json") == ".json"
        assert FileUtils.get_file_extension("test") == ""
        assert FileUtils.get_file_extension("test.tar.gz") == ".gz"

    def test_get_file_name_without_extension(self):
        """测试获取不带扩展名的文件名"""
        assert FileUtils.get_file_name_without_extension("test.txt") == "test"
        assert FileUtils.get_file_name_without_extension("/path/to/test.json") == "test"
        assert FileUtils.get_file_name_without_extension("test") == "test"
