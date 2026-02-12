"""Persistence Scheduler 测试

测试 PersistenceScheduler 的持久化功能
"""

import pytest
import os
import tempfile
import json
from unittest.mock import patch, MagicMock

from zoo_framework.core.persistence_scheduler import (
    PersistenceScheduler,
    FileChecksumValidator,
    BackupManager,
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

    def test_verify_checksum_file_not_found(self):
        """测试校验和验证 - 文件不存在"""
        is_valid = FileChecksumValidator.verify_checksum("/nonexistent/file", "checksum")
        assert is_valid is False


class TestBackupManager:
    """BackupManager 测试类"""

    def test_create_backup(self):
        """测试创建备份"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            temp_file = f.name
        
        try:
            backup_path = BackupManager.create_backup(temp_file)
            assert backup_path is not None
            assert os.path.exists(backup_path)
            
            # 清理备份文件
            if os.path.exists(backup_path):
                os.unlink(backup_path)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_cleanup_old_backups(self):
        """测试清理旧备份"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建一些模拟的备份文件
            for i in range(7):
                backup_file = os.path.join(temp_dir, f"test.backup.{i}.json")
                with open(backup_file, 'w') as f:
                    f.write("{}")
            
            BackupManager.cleanup_old_backups(temp_dir, "test", keep_count=5)
            
            # 应该剩下 5 个
            backups = [f for f in os.listdir(temp_dir) if f.startswith("test.backup")]
            assert len(backups) <= 5


class TestPersistenceScheduler:
    """PersistenceScheduler 测试类"""

    def test_pickle_strategy(self):
        """测试 Pickle 持久化策略"""
        with tempfile.TemporaryDirectory() as temp_dir:
            scheduler = PersistenceScheduler(
                strategy="pickle",
                file_path=os.path.join(temp_dir, "test.pkl")
            )
            
            data = {"key": "value", "number": 42}
            scheduler.save(data)
            
            loaded = scheduler.load()
            assert loaded == data

    def test_json_strategy(self):
        """测试 JSON 持久化策略"""
        with tempfile.TemporaryDirectory() as temp_dir:
            scheduler = PersistenceScheduler(
                strategy="json",
                file_path=os.path.join(temp_dir, "test.json")
            )
            
            data = {"key": "value", "number": 42}
            scheduler.save(data)
            
            loaded = scheduler.load()
            assert loaded == data

    def test_invalid_strategy(self):
        """测试无效的持久化策略"""
        with pytest.raises(ValueError):
            PersistenceScheduler(strategy="invalid")

    def test_load_nonexistent_file(self):
        """测试加载不存在的文件"""
        scheduler = PersistenceScheduler(
            strategy="json",
            file_path="/nonexistent/path/file.json"
        )
        
        result = scheduler.load()
        assert result is None
