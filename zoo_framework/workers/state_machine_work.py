import copy
import pickle  # nosec B403 — 与 core/persistence_scheduler.py 同因：本框架的持久化格式就是 pickle，读的是自己写出的文件
import threading

from zoo_framework.statemachine.state_machine_manager import StateMachineManager
from zoo_framework.utils import FileUtils, LogUtils

from .base_worker import BaseWorker


class StateMachineWorker(BaseWorker):
    """状态机 Worker - 管理状态机持久化.

    特性：
    - 自动加载和保存状态机
    - 线程安全的状态机访问
    - 支持文件校验和备份
    """

    # 类级锁，保护文件访问
    _file_lock = threading.RLock()

    # 实例锁，保护状态机操作
    _instance_lock = threading.Lock()

    def __init__(self):
        # is_loop 由 BaseWorker 以属性形式暴露、以 _props 为唯一真源；
        # 此处 MUST NOT 再用实例属性遮蔽它（属性无 setter，赋值会直接抛 AttributeError）。
        BaseWorker.__init__(self, {"is_loop": True, "delay_time": 5, "name": "StateMachineWorker"})
        # 标记是否已加载
        self._loaded = False

    def _destroy(self, result):
        """销毁时保存状态."""
        self._save_state_machines()

    def _execute(self):
        """执行状态机持久化任务."""
        # 使用线程锁保护状态机操作
        with self._instance_lock:
            state_machine_manager = StateMachineManager()

            # 检查状态机是否已加载
            if not self._loaded:
                self._load_state_machines(state_machine_manager)
                self._loaded = True
            else:
                # 定期保存状态
                self._save_state_machines(state_machine_manager)

    def _load_state_machines(self, state_machine_manager):
        """加载状态机（线程安全）.

        Args:
            state_machine_manager: 状态机管理器实例
        """
        from zoo_framework.params import StateMachineParams

        # 使用文件锁保护文件读取
        with self._file_lock:
            if state_machine_manager.have_loaded():
                return

            if FileUtils.file_exists(StateMachineParams.PICKLE_PATH):
                try:
                    with open(StateMachineParams.PICKLE_PATH, "rb") as f:
                        # 校验文件完整性
                        file_content = f.read()
                        if not file_content:
                            LogUtils.warning("State machine file is empty, creating new")
                            state_machine_manager.load_state_machines()
                            return

                        # 重新定位到文件开头
                        f.seek(0)
                        unpickler = pickle.Unpickler(f)  # nosec B301 — 见文件头 import pickle 处的说明
                        state_machines = unpickler.load()

                        LogUtils.info(f"✅ State machines loaded: {len(state_machines)} states")
                        state_machine_manager.load_state_machines(state_machines)

                except (pickle.UnpicklingError, EOFError) as e:
                    LogUtils.error(f"❌ Failed to load state machines, file may be corrupted: {e}")
                    # 尝试从备份恢复
                    self._load_from_backup(state_machine_manager)
                except Exception as e:
                    LogUtils.error(f"❌ Unexpected error loading state machines: {e}")
                    state_machine_manager.load_state_machines()
            else:
                LogUtils.info("📝 No state machine file found, creating new")
                state_machine_manager.load_state_machines()

    def _save_state_machines(self, state_machine_manager=None):
        """保存状态机（线程安全）.

        Args:
            state_machine_manager: 状态机管理器实例，为 None 时自动获取
        """
        from zoo_framework.params import StateMachineParams

        if state_machine_manager is None:
            state_machine_manager = StateMachineManager()

        # 使用文件锁保护文件写入
        with self._file_lock:
            try:
                # 先创建备份
                self._create_backup(StateMachineParams.PICKLE_PATH)

                # 写入临时文件
                temp_path = StateMachineParams.PICKLE_PATH + ".tmp"
                state_machines = state_machine_manager.get_state_machines()

                # 深拷贝避免并发修改
                copy_value = copy.deepcopy(state_machines)

                with open(temp_path, "wb") as f:
                    pickle.dump(copy_value, f, protocol=pickle.HIGHEST_PROTOCOL)

                # 原子性替换文件
                import os

                if os.path.exists(StateMachineParams.PICKLE_PATH):
                    os.replace(temp_path, StateMachineParams.PICKLE_PATH)
                else:
                    os.rename(temp_path, StateMachineParams.PICKLE_PATH)

                LogUtils.debug("💾 State machines saved successfully")

            except Exception as e:
                LogUtils.error(f"❌ Failed to save state machines: {e}")
                # 尝试恢复备份
                self._restore_backup(StateMachineParams.PICKLE_PATH)

    def _create_backup(self, file_path: str):
        """创建文件备份.

        Args:
            file_path: 原文件路径
        """
        import os
        import shutil
        from datetime import datetime

        if not os.path.exists(file_path):
            return

        backup_dir = os.path.join(os.path.dirname(file_path), "backups")
        os.makedirs(backup_dir, exist_ok=True)

        # 时间戳精确到微秒：秒级精度下同一秒内的多次备份会相互覆盖。
        # 固定宽度的微秒后缀同时保证"字典序等于时间序"——取最新备份依赖该性质。
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_path = os.path.join(backup_dir, f"state_machine_{timestamp}.pkl")

        try:
            shutil.copy2(file_path, backup_path)
            LogUtils.debug(f"📦 Backup created: {backup_path}")

            # 清理旧备份（保留最近 5 个）
            self._cleanup_old_backups(backup_dir, keep=5)
        except Exception as e:
            LogUtils.warning(f"⚠️ Failed to create backup: {e}")

    def _load_from_backup(self, state_machine_manager):
        """从备份恢复状态机.

        Args:
            state_machine_manager: 状态机管理器实例
        """
        import glob
        import os

        from zoo_framework.params import StateMachineParams

        backup_dir = os.path.join(os.path.dirname(StateMachineParams.PICKLE_PATH), "backups")

        if not os.path.exists(backup_dir):
            LogUtils.warning("⚠️ No backup directory found, creating new state machines")
            state_machine_manager.load_state_machines()
            return

        # 查找最新的备份
        backup_files = glob.glob(os.path.join(backup_dir, "state_machine_*.pkl"))
        if not backup_files:
            LogUtils.warning("⚠️ No backup files found, creating new state machines")
            state_machine_manager.load_state_machines()
            return

        # 按时间排序
        backup_files.sort(reverse=True)
        latest_backup = backup_files[0]

        try:
            with open(latest_backup, "rb") as f:
                state_machines = pickle.load(f)  # nosec B301 — 见文件头 import pickle 处的说明
                LogUtils.info(f"✅ State machines restored from backup: {latest_backup}")
                state_machine_manager.load_state_machines(state_machines)
        except Exception as e:
            LogUtils.error(f"❌ Failed to restore from backup: {e}")
            state_machine_manager.load_state_machines()

    def _restore_backup(self, file_path: str):
        """恢复备份文件.

        Args:
            file_path: 原文件路径
        """
        import glob
        import os
        import shutil

        backup_dir = os.path.join(os.path.dirname(file_path), "backups")
        if not os.path.exists(backup_dir):
            return

        backup_files = glob.glob(os.path.join(backup_dir, "state_machine_*.pkl"))
        if not backup_files:
            return

        backup_files.sort(reverse=True)
        latest_backup = backup_files[0]

        try:
            shutil.copy2(latest_backup, file_path)
            LogUtils.info(f"✅ File restored from backup: {latest_backup}")
        except Exception as e:
            LogUtils.error(f"❌ Failed to restore backup: {e}")

    def _cleanup_old_backups(self, backup_dir: str, keep: int = 5):
        """清理旧备份文件.

        Args:
            backup_dir: 备份目录
            keep: 保留的备份数量
        """
        import glob
        import os

        backup_files = glob.glob(os.path.join(backup_dir, "state_machine_*.pkl"))

        if len(backup_files) <= keep:
            return

        # 按时间排序，删除旧的
        backup_files.sort(reverse=True)
        for old_file in backup_files[keep:]:
            try:
                os.remove(old_file)
                LogUtils.debug(f"🗑️ Old backup removed: {old_file}")
            except Exception as e:
                LogUtils.warning(f"⚠️ Failed to remove old backup: {e}")
