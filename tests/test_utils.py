"""工具类测试模块

测试工具类功能
"""

import os
import tempfile
import threading

import pytest

from zoo_framework.utils import FileUtils, LogUtils
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict


class TestThreadSafeDictLockScope:
    """align-execution-primitives D3: 锁每实例持有、为 threading 级."""

    def test_lock_is_per_instance_rlock(self):
        """Scenario: 锁为 threading 级且按实例持有."""
        d1 = ThreadSafeDict()
        d2 = ThreadSafeDict()

        assert isinstance(d1._lock, type(threading.RLock()))
        assert d1._lock is not d2._lock, "两个实例仍共享同一把锁"

    def test_two_instances_do_not_serialize(self):
        """Scenario: 两个实例互不阻塞（一个实例锁内的慢操作不拖累另一个）."""
        d1 = ThreadSafeDict()
        d2 = ThreadSafeDict()

        holder_entered = threading.Event()
        holder_release = threading.Event()

        def _holder():
            with d1._lock:
                holder_entered.set()
                holder_release.wait(5)
            d1["after"] = 1

        thread = threading.Thread(target=_holder)
        thread.start()
        try:
            assert holder_entered.wait(5), "慢操作未能进入 d1 锁内"

            d2_written = threading.Event()

            def _writer():
                d2["k"] = "v"
                d2_written.set()

            writer = threading.Thread(target=_writer)
            writer.start()
            # 模块级共享锁时代：这里会被 d1 的慢操作阻塞到释放为止
            assert d2_written.wait(2), "d2 被 d1 锁内操作阻塞，锁仍为进程级共享"
            writer.join(2)
            assert d2["k"] == "v"
        finally:
            holder_release.set()
            thread.join(2)

    def test_concurrent_updates_same_instance_not_lost(self):
        """Scenario: 同一实例并发读写不丢更新."""
        d = ThreadSafeDict()
        errors: list[BaseException] = []

        def _bump(prefix: str) -> None:
            try:
                for i in range(200):
                    d[f"{prefix}-{i}"] = i
            except BaseException as exc:  # 收集给主线程断言
                errors.append(exc)

        threads = [threading.Thread(target=_bump, args=(f"t{n}",)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)

        assert not errors
        assert len(d) == 800

    def test_pickle_round_trip_excludes_lock(self):
        """实例持锁后状态机持久化（pickle）不得回归：锁不序列化，载入时重建."""
        import pickle

        d = ThreadSafeDict({"k": 1})
        restored = pickle.loads(pickle.dumps(d))

        assert restored.get("k") == 1
        assert isinstance(restored._lock, type(threading.RLock()))
        assert restored._lock is not d._lock


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
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
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
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            temp_path = f.name
            f.write("12345")  # 5 bytes

        try:
            size = FileUtils.get_file_size(temp_path)
            assert size == 5
        finally:
            os.unlink(temp_path)

    def test_get_file_size_not_found(self):
        """测试获取不存在的文件大小"""
        # 内核确实抛裸 Exception（file_utils.get_file_size 的现状）；收窄到具体类型
        # 属公共行为变更，不在本变更范围。
        with pytest.raises(Exception):  # noqa: B017
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
