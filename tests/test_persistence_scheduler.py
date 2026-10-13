"""Persistence Scheduler 测试

测试 PersistenceScheduler 的持久化功能
"""

import os
import tempfile

import pytest

import zoo_framework.core.persistence_scheduler as persistence_module
from zoo_framework.core.persistence_scheduler import (
    FileChecksumValidator,
    PersistenceScheduler,
    PicklePersistenceStrategy,
)


class TestFileChecksumValidator:
    """FileChecksumValidator 测试类"""

    def test_calculate_checksum(self):
        """测试计算校验和"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
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
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
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
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
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
                filepath=filepath,
                strategy=PicklePersistenceStrategy(),
                auto_save_interval=0,  # 禁用自动保存
            )

            data = {"key": "value", "number": 42}
            scheduler.update_data(data)
            scheduler.save(force=True)

            # 创建新的 scheduler 加载数据
            scheduler2 = PersistenceScheduler(
                filepath=filepath,
                strategy=PicklePersistenceStrategy(),
                auto_save_interval=0,
            )
            loaded = scheduler2.load()
            assert loaded == data

    def test_load_nonexistent_file(self):
        """测试加载不存在的文件"""
        scheduler = PersistenceScheduler(
            filepath="/nonexistent/path/file.pkl",
            auto_save_interval=0,
        )

        result = scheduler.load()
        assert result is None


class TestExplicitFailureNotification:
    """persistence: 落盘失败 MUST 显式化，MUST NOT 只留一条日志（issue #231）.

    缺陷：`stateMachine:picklePath` 的父目录不存在时，每次落盘都失败，但只记一条
    ERROR 日志并返回 False——调用方无从感知，持续失败被静默吞掉。
    """

    @staticmethod
    def _scheduler(tmp_path, name="states.pic"):
        return PersistenceScheduler(
            filepath=str(tmp_path / name),
            strategy=PicklePersistenceStrategy(),
            auto_save_interval=0,
        )

    def test_save_raises_when_parent_dir_missing(self, tmp_path):
        """Scenario: 目标目录不存在时落盘明确报错（而非返回 False）。"""
        missing = tmp_path / "missing-dir" / "states.pic"
        scheduler = PersistenceScheduler(
            filepath=str(missing), strategy=PicklePersistenceStrategy(), auto_save_interval=0
        )
        scheduler.update_data({"k": 1})

        with pytest.raises(persistence_module.PersistenceError) as exc:
            scheduler.save(force=True)

        assert str(missing.parent) in str(exc.value), "错误信息未指明不可用的目标目录"
        assert scheduler.is_dirty() is True, "保存失败后不应清掉脏标记（假装已落盘）"
        assert not missing.exists(), "报错路径不应留下半成品文件"

    def test_start_fails_fast_when_parent_dir_missing(self, tmp_path):
        """Scenario: 启动校验——目标目录不存在时启动当场失败。"""
        missing = tmp_path / "missing-dir" / "states.pic"
        scheduler = PersistenceScheduler(
            filepath=str(missing), strategy=PicklePersistenceStrategy(), auto_save_interval=0
        )

        with pytest.raises(persistence_module.PersistenceError):
            scheduler.start()

    def test_save_succeeds_when_directory_exists(self, tmp_path):
        """目标目录存在时落盘照常成功（修复 MUST NOT 影响正常路径）。"""
        scheduler = self._scheduler(tmp_path)
        scheduler.update_data({"k": 1})

        assert scheduler.save(force=True) is True
        assert scheduler.is_dirty() is False
        assert (tmp_path / "states.pic").exists()
