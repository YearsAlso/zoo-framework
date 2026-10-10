import copy
import pickle  # nosec B403 — 与 core/persistence_scheduler.py 同因：本框架的持久化格式就是 pickle，读的是自己写出的文件
import threading

from zoo_framework.statemachine.state_machine_manager import StateMachineManager
from zoo_framework.utils import FileUtils, LogUtils

from .base_worker import BaseWorker


class StateMachineWorker(BaseWorker):
    """State machine Worker - manages state machine persistence.

    Features:
    - automatically loads and saves the state machine
    - thread-safe state machine access
    - file checksums and backups
    """

    # Class-level lock, protecting file access
    _file_lock = threading.RLock()

    # Instance-level lock, protecting state machine operations
    _instance_lock = threading.Lock()

    def __init__(self):
        # Tempo parameterization (change configurable-run-delay / #73): the
        # same family as EventWorker; the lazy import must precede the props
        # assembly, and this class is constructed by WorkerRegistry at
        # runtime, so the order holds.
        from zoo_framework.params import StateMachineParams

        # is_loop is exposed by BaseWorker as a property with _props as the
        # sole source of truth; here it MUST NOT be shadowed by an instance
        # attribute (the property has no setter, assignment raises
        # AttributeError directly).
        BaseWorker.__init__(
            self,
            {
                "is_loop": True,
                "delay_time": StateMachineParams.STATE_MACHINE_DELAY_TIME,
                "name": "StateMachineWorker",
            },
        )
        # Whether already loaded
        self._loaded = False

    def _destroy(self, result):
        """Save the state on destroy."""
        self._save_state_machines()

    def _execute(self):
        """Run the state machine persistence task."""
        # Use the thread lock to protect state machine operations
        with self._instance_lock:
            state_machine_manager = StateMachineManager()

            # Check whether the state machine is loaded
            if not self._loaded:
                self._load_state_machines(state_machine_manager)
                self._loaded = True
            else:
                # Save the state periodically
                self._save_state_machines(state_machine_manager)

    def _load_state_machines(self, state_machine_manager):
        """Load the state machine (thread-safe).

        Args:
            state_machine_manager: the state machine manager instance
        """
        from zoo_framework.params import StateMachineParams

        # Use the file lock to protect file reading
        with self._file_lock:
            if state_machine_manager.have_loaded():
                return

            if FileUtils.file_exists(StateMachineParams.PICKLE_PATH):
                try:
                    with open(StateMachineParams.PICKLE_PATH, "rb") as f:
                        # Validate the file integrity
                        file_content = f.read()
                        if not file_content:
                            LogUtils.warning("State machine file is empty, creating new")
                            state_machine_manager.load_state_machines()
                            return

                        # Seek back to the file start
                        f.seek(0)
                        unpickler = pickle.Unpickler(f)  # nosec B301 — 见文件头 import pickle 处的说明
                        state_machines = unpickler.load()

                        LogUtils.info(f"✅ State machines loaded: {len(state_machines)} states")
                        state_machine_manager.load_state_machines(state_machines)

                except (pickle.UnpicklingError, EOFError) as e:
                    LogUtils.error(f"❌ Failed to load state machines, file may be corrupted: {e}")
                    # Try restoring from a backup
                    self._load_from_backup(state_machine_manager)
                except Exception as e:
                    LogUtils.error(f"❌ Unexpected error loading state machines: {e}")
                    state_machine_manager.load_state_machines()
            else:
                LogUtils.info("📝 No state machine file found, creating new")
                state_machine_manager.load_state_machines()

    def _save_state_machines(self, state_machine_manager=None):
        """Save the state machine (thread-safe).

        Args:
            state_machine_manager: the state machine manager instance;
                auto-acquired when None
        """
        from zoo_framework.params import StateMachineParams

        if state_machine_manager is None:
            state_machine_manager = StateMachineManager()

        # Use the file lock to protect file writing
        with self._file_lock:
            try:
                # Create a backup first
                self._create_backup(StateMachineParams.PICKLE_PATH)

                # Write the temp file
                temp_path = StateMachineParams.PICKLE_PATH + ".tmp"
                state_machines = state_machine_manager.get_state_machines()

                # Deep-copy to avoid concurrent modification
                copy_value = copy.deepcopy(state_machines)

                with open(temp_path, "wb") as f:
                    pickle.dump(copy_value, f, protocol=pickle.HIGHEST_PROTOCOL)

                # Replace the file atomically
                import os

                if os.path.exists(StateMachineParams.PICKLE_PATH):
                    os.replace(temp_path, StateMachineParams.PICKLE_PATH)
                else:
                    os.rename(temp_path, StateMachineParams.PICKLE_PATH)

                LogUtils.debug("💾 State machines saved successfully")

            except Exception as e:
                LogUtils.error(f"❌ Failed to save state machines: {e}")
                # Try restoring the backup
                self._restore_backup(StateMachineParams.PICKLE_PATH)

    def _create_backup(self, file_path: str):
        """Create a file backup.

        Args:
            file_path: the original file path
        """
        import os
        import shutil
        from datetime import datetime

        if not os.path.exists(file_path):
            return

        backup_dir = os.path.join(os.path.dirname(file_path), "backups")
        os.makedirs(backup_dir, exist_ok=True)

        # Timestamps to microsecond precision: with second-level precision,
        # several backups within one second would overwrite each other. The
        # fixed-width microsecond suffix also makes lexicographic order
        # equal time order - taking the latest backup relies on that.
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_path = os.path.join(backup_dir, f"state_machine_{timestamp}.pkl")

        try:
            shutil.copy2(file_path, backup_path)
            LogUtils.debug(f"📦 Backup created: {backup_path}")

            # Clean up old backups (keep the last 5)
            self._cleanup_old_backups(backup_dir, keep=5)
        except Exception as e:
            LogUtils.warning(f"⚠️ Failed to create backup: {e}")

    def _load_from_backup(self, state_machine_manager):
        """Restore the state machine from a backup.

        Args:
            state_machine_manager: the state machine manager instance
        """
        import glob
        import os

        from zoo_framework.params import StateMachineParams

        backup_dir = os.path.join(os.path.dirname(StateMachineParams.PICKLE_PATH), "backups")

        if not os.path.exists(backup_dir):
            LogUtils.warning("⚠️ No backup directory found, creating new state machines")
            state_machine_manager.load_state_machines()
            return

        # Find the latest backup
        backup_files = glob.glob(os.path.join(backup_dir, "state_machine_*.pkl"))
        if not backup_files:
            LogUtils.warning("⚠️ No backup files found, creating new state machines")
            state_machine_manager.load_state_machines()
            return

        # Sort by time
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
        """Restore a backup file.

        Args:
            file_path: the original file path
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
        """Clean up old backup files.

        Args:
            backup_dir: the backup directory
            keep: how many backups to keep
        """
        import glob
        import os

        backup_files = glob.glob(os.path.join(backup_dir, "state_machine_*.pkl"))

        if len(backup_files) <= keep:
            return

        # Sort by time and delete the old ones
        backup_files.sort(reverse=True)
        for old_file in backup_files[keep:]:
            try:
                os.remove(old_file)
                LogUtils.debug(f"🗑️ Old backup removed: {old_file}")
            except Exception as e:
                LogUtils.warning(f"⚠️ Failed to remove old backup: {e}")
