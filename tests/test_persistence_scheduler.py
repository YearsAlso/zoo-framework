"""Persistence Scheduler 测试

测试 PersistenceScheduler 的持久化功能
"""

import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock

from zoo_framework.core.persistence_scheduler import (
    PersistenceScheduler,
    FileChecksumValidator,
)


class TestFileChecksumValidator:
    """FileChecksumValidator 测试类"""

    def test_calculate_checksum(self):
        """测试计算校验和"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            temp_file = f.name
        
        try:
            checksum = FileChecksumValidator.calculate_checksum(temp_file)
            assert checksum is not None
            assert len(checksum) == 32  # MD5 是 32 位十六进制
        finally:
            os.unlink(temp_file)

    def test_verify_checksum_valid(self):
        """测试校验和验证 - 有效"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            temp_file = f.name
        
        try:
            checksum = FileChecksumValidator.calculate_checksum(temp_file)
            is_valid = FileChecksumValidator.verify_checksum(temp_file, checksum)
            assert is_valid is True
        finally:
            os.unlink(temp_file)

    def test_verify_checksum_invalid(self):
        """测试校验和验证 - 无效"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            temp_file = f.name
        
        try:
            is_valid = FileChecksumValidator.verify_checksum(temp_file, "invalid_checksum")
            assert is_valid is False
        finally:
            os.unlink(temp_file)


class TestPersistenceScheduler:
    """PersistenceScheduler 测试类"""

    def test_pickle_strategy(self):
        """测试 Pickle 持久化策略"""
        with tempfile.TemporaryDirectory() as temp_dir:
            filepath = os.path.join(temp_dir, "test.pkl")
            scheduler = PersistenceScheduler(
                strategy="pickle",
                filepath=filepath
            )
            
            data = {"key": "value", "number": 42}
            scheduler.save(data)
            
            loaded = scheduler.load()
            assert loaded == data

    def test_json_strategy(self):
        """测试 JSON 持久化策略"""
        with tempfile.TemporaryDirectory() as temp_dir:
            filepath = os.path.join(temp_dir, "test.json")
            scheduler = PersistenceScheduler(
                strategy="json",
                filepath=filepath
            )
            
            data = {"key": "value", "number": 42}
            scheduler.save(data)
            
            loaded = scheduler.load()
            assert loaded == data

    def test_invalid_strategy(self):
        """测试无效的持久化策略"""
        with tempfile.TemporaryDirectory() as temp_dir:
            filepath = os.path.join(temp_dir, "test.txt")
            with pytest.raises(ValueError):
                PersistenceScheduler(strategy="invalid", filepath=filepath)

    def test_load_nonexistent_file(self):
        """测试加载不存在的文件"""
        scheduler = PersistenceScheduler(
            strategy="json",
            filepath="/nonexistent/path/file.json"
        )
        
        result = scheduler.load()
        assert result is None
