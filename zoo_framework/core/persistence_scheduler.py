"""Persistence scheduler - decouples persistence logic.

P1 task: move the persistence logic out of StateMachineWorker into an
independent scheduler.
"""

import os
import pickle  # nosec B403 — 本框架的持久化格式就是 pickle，且读取的是自己写出的文件
import shutil
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from zoo_framework.utils import FileUtils, LogUtils


class PersistenceStrategy(ABC):
    """Persistence strategy base class.

    Defines the persistence interface, supporting different persistence
    implementations.
    """

    @abstractmethod
    def save(self, data: Any, filepath: str) -> bool:
        """Save the data."""
        pass

    @abstractmethod
    def load(self, filepath: str) -> Any | None:
        """Load the data."""
        pass

    @abstractmethod
    def validate(self, filepath: str) -> bool:
        """Validate the data integrity."""
        pass


class PicklePersistenceStrategy(PersistenceStrategy):
    """Pickle persistence strategy."""

    def save(self, data: Any, filepath: str) -> bool:
        """Save the data with Pickle."""
        try:
            # 写入临时文件
            temp_path = filepath + ".tmp"
            with open(temp_path, "wb") as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            # 原子性替换
            if os.path.exists(filepath):
                os.replace(temp_path, filepath)
            else:
                os.rename(temp_path, filepath)

            return True
        except Exception as e:
            LogUtils.error(f"❌ Pickle save failed: {e}")
            return False

    def load(self, filepath: str) -> Any | None:
        """Load the data with Pickle."""
        try:
            with open(filepath, "rb") as f:
                return pickle.load(f)  # nosec B301 — 见文件头的 pickle 说明
        except Exception as e:
            LogUtils.error(f"❌ Pickle load failed: {e}")
            return None

    def validate(self, filepath: str) -> bool:
        """Validate the Pickle file integrity."""
        try:
            with open(filepath, "rb") as f:
                content = f.read()
                if not content:
                    return False
                f.seek(0)
                pickle.load(f)  # nosec B301 — 见文件头的 pickle 说明
                return True
        except Exception:
            return False


class FileChecksumValidator:
    """File checksum validator.

    P1 task: implement the file checksum feature.
    """

    @staticmethod
    def calculate_checksum(filepath: str) -> str:
        """Compute the file checksum (MD5).

        Args:
            filepath: the file path

        Returns:
            The MD5 checksum string
        """
        import hashlib

        # 显式声明"非安全用途"：此处 md5 只做文件**完整性**校验（检测截断/损坏），
        # 不用于任何安全目的。`usedforsecurity=False` 正是这个语义的官方表达，
        # 比压制告警准确——bandit 的 B324 也据此放行。
        hash_md5 = hashlib.md5(usedforsecurity=False)
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    @staticmethod
    def verify_checksum(filepath: str, expected_checksum: str) -> bool:
        """Verify the file checksum.

        Args:
            filepath: the file path
            expected_checksum: the expected checksum

        Returns:
            Whether the verification passes
        """
        actual_checksum = FileChecksumValidator.calculate_checksum(filepath)
        return actual_checksum == expected_checksum

    @staticmethod
    def save_checksum(filepath: str, checksum: str) -> None:
        """Save the checksum to a file.

        Args:
            filepath: the original file path
            checksum: the checksum value
        """
        checksum_path = filepath + ".checksum"
        FileUtils.write_text(checksum_path, checksum)

    @staticmethod
    def load_checksum(filepath: str) -> Any | None:
        """Load the checksum from a file.

        Args:
            filepath: the original file path

        Returns:
            The checksum value, or None if it does not exist
        """
        checksum_path = filepath + ".checksum"
        if not os.path.exists(checksum_path):
            return None

        return FileUtils.read_text(checksum_path).strip()


class BackupManager:
    """Backup manager.

    P1 task: implement file backup and rotation.
    """

    def __init__(self, backup_dir: str = "backups", max_backups: int = 5):
        self.backup_dir = backup_dir
        self.max_backups = max_backups

    def create_backup(self, filepath: str) -> str | None:
        """Create a file backup.

        Args:
            filepath: the original file path

        Returns:
            The backup file path, or None on failure
        """
        if not os.path.exists(filepath):
            return None

        # 创建备份目录
        file_dir = os.path.dirname(filepath)
        backup_dir = os.path.join(file_dir, self.backup_dir)
        os.makedirs(backup_dir, exist_ok=True)

        # 生成备份文件名
        # 时间戳精确到微秒：秒级精度下同一秒内的多次备份会相互覆盖。
        # 固定宽度的微秒后缀同时保证"字典序等于时间序"——取最新备份依赖该性质。
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = os.path.basename(filepath)
        backup_path = os.path.join(backup_dir, f"{filename}.{timestamp}.bak")

        try:
            shutil.copy2(filepath, backup_path)

            # 保存校验和
            checksum = FileChecksumValidator.calculate_checksum(filepath)
            FileChecksumValidator.save_checksum(backup_path, checksum)

            LogUtils.info(f"📦 Backup created: {backup_path}")

            # 清理旧备份
            self._cleanup_old_backups(backup_dir, filename)

            return backup_path
        except Exception as e:
            LogUtils.error(f"❌ Backup failed: {e}")
            return None

    def restore_backup(self, filepath: str) -> bool:
        """Restore the file from a backup.

        Args:
            filepath: the original file path

        Returns:
            Whether the restore succeeded
        """
        file_dir = os.path.dirname(filepath)
        backup_dir = os.path.join(file_dir, self.backup_dir)

        if not os.path.exists(backup_dir):
            LogUtils.warning("⚠️ Backup directory not found")
            return False

        filename = os.path.basename(filepath)
        backup_files = []

        # 查找备份文件
        for f in os.listdir(backup_dir):
            if f.startswith(filename) and f.endswith(".bak"):
                backup_files.append(os.path.join(backup_dir, f))

        if not backup_files:
            LogUtils.warning("⚠️ No backup files found")
            return False

        # 按时间排序，选择最新的
        backup_files.sort(reverse=True)
        latest_backup = backup_files[0]

        # 验证备份完整性
        expected_checksum = FileChecksumValidator.load_checksum(latest_backup)
        if expected_checksum:
            if not FileChecksumValidator.verify_checksum(latest_backup, expected_checksum):
                LogUtils.error("❌ Backup file corrupted")
                return False

        try:
            shutil.copy2(latest_backup, filepath)
            LogUtils.info(f"✅ Restored from backup: {latest_backup}")
            return True
        except Exception as e:
            LogUtils.error(f"❌ Restore failed: {e}")
            return False

    def _cleanup_old_backups(self, backup_dir: str, filename: str) -> None:
        """Clean up old backup files.

        Args:
            backup_dir: the backup directory
            filename: the original file name
        """
        backup_files = []

        for f in os.listdir(backup_dir):
            if f.startswith(filename) and f.endswith(".bak"):
                filepath = os.path.join(backup_dir, f)
                backup_files.append((filepath, os.path.getmtime(filepath)))

        # 按修改时间排序
        backup_files.sort(key=lambda x: x[1], reverse=True)

        # 删除旧备份
        for old_file, _ in backup_files[self.max_backups :]:
            try:
                os.remove(old_file)
                # 同时删除校验和文件
                checksum_file = old_file + ".checksum"
                if os.path.exists(checksum_file):
                    os.remove(checksum_file)
                LogUtils.debug(f"🗑️ Old backup removed: {old_file}")
            except Exception as e:
                LogUtils.warning(f"⚠️ Failed to remove old backup: {e}")


class PersistenceScheduler:
    """Persistence scheduler.

    P1 task: decouple the persistence logic; the scheduler decides when to
    persist.

    Responsibilities:
    - manage the persistence timing
    - perform data save and load
    - handle backup and restore
    - validate the data integrity
    """

    def __init__(
        self,
        filepath: str,
        strategy: PersistenceStrategy | None = None,
        auto_save_interval: int = 60,  # 自动保存间隔（秒）
        enable_backup: bool = True,
        max_backups: int = 5,
    ):
        self.filepath = filepath
        self.strategy = strategy or PicklePersistenceStrategy()
        self.auto_save_interval = auto_save_interval
        self.enable_backup = enable_backup

        self._backup_manager = BackupManager(max_backups=max_backups) if enable_backup else None
        self._file_lock = threading.RLock()
        self._data: Any | None = None
        self._dirty = False  # 数据是否被修改
        # 标注为 float：初值 0 会让 mypy 把它推断成 int，而实际赋值来自
        # datetime.timestamp()（float）。
        self._last_save_time: float = 0
        self._running = False
        self._scheduler_thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the persistence scheduler."""
        if self._running:
            return

        self._running = True
        if self.auto_save_interval > 0:
            self._scheduler_thread = threading.Thread(target=self._scheduler_loop)
            self._scheduler_thread.daemon = True
            self._scheduler_thread.start()

        LogUtils.info("✅ Persistence scheduler started")

    def stop(self) -> None:
        """Stop the persistence scheduler."""
        self._running = False

        # 最后保存一次
        if self._dirty:
            self.save(force=True)

        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)

        LogUtils.info("🛑 Persistence scheduler stopped")

    def _scheduler_loop(self) -> None:
        """Scheduling loop."""
        import time

        while self._running:
            try:
                time.sleep(self.auto_save_interval)
                if self._dirty:
                    self.save()
            except Exception as e:
                LogUtils.error(f"❌ Scheduler error: {e}")

    def load(self) -> Any | None:
        """Load the data.

        Returns:
            The loaded data, or None if the file is missing or corrupted
        """
        with self._file_lock:
            if not FileUtils.file_exists(self.filepath):
                LogUtils.info("📝 No persistence file found")
                return None

            # 验证文件完整性
            if not self.strategy.validate(self.filepath):
                LogUtils.error("❌ Persistence file corrupted, trying backup")
                if self._backup_manager:
                    if self._backup_manager.restore_backup(self.filepath):
                        LogUtils.info("✅ Restored from backup")
                    else:
                        return None
                else:
                    return None

            # 加载数据
            data = self.strategy.load(self.filepath)
            if data is not None:
                self._data = data
                LogUtils.info("✅ Data loaded successfully")

            return data

    def save(self, force: bool = False) -> bool:
        """Save the data.

        Args:
            force: whether to force the save (ignore the dirty flag)

        Returns:
            Whether the save succeeded
        """
        with self._file_lock:
            if not force and not self._dirty:
                return True

            if self._data is None:
                return False

            # 创建备份
            if self.enable_backup and self._backup_manager:
                self._backup_manager.create_backup(self.filepath)

            # 保存数据
            success = self.strategy.save(self._data, self.filepath)

            if success:
                self._dirty = False
                self._last_save_time = datetime.now().timestamp()

                # 保存校验和
                checksum = FileChecksumValidator.calculate_checksum(self.filepath)
                FileChecksumValidator.save_checksum(self.filepath, checksum)

                LogUtils.debug("💾 Data saved successfully")
            else:
                LogUtils.error("❌ Failed to save data")

            return success

    def mark_dirty(self) -> None:
        """Mark the data as modified."""
        self._dirty = True

    def update_data(self, data: Any, auto_save: bool = False) -> None:
        """Update the data.

        Args:
            data: the new data
            auto_save: whether to save immediately
        """
        self._data = data
        self._dirty = True

        if auto_save:
            self.save()

    def get_data(self) -> Any | None:
        """Get the current data."""
        return self._data

    def is_dirty(self) -> bool:
        """Check whether the data was modified."""
        return self._dirty


# 导出公共 API
__all__ = [
    "BackupManager",
    "FileChecksumValidator",
    "PersistenceScheduler",
    "PersistenceStrategy",
    "PicklePersistenceStrategy",
]
