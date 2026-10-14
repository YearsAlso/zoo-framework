import binascii
import copy
import os
import pickle  # nosec B403 — 与 core/persistence_scheduler.py 同因：本框架的持久化格式就是 pickle，读的是自己写出的文件
import threading

from zoo_framework.core.persistence_scheduler import (
    PersistenceError,
    PicklePersistenceStrategy,
)
from zoo_framework.statemachine.state_machine_manager import StateMachineManager
from zoo_framework.utils import FileUtils, LogUtils

from .base_worker import BaseWorker

# 增量持久化目录内的 manifest 文件名（内容为「作用域名 -> 文件名」的映射）。
_MANIFEST_NAME = "manifest.pkl"


def _scope_file_name(scope: str) -> str:
    """把作用域名映射为文件安全且可逆的文件名。

    作用域名可能含路径分隔符或其它文件系统敏感字符，故先 UTF-8 编码再十六进制化
    （结果只含 ``[0-9a-f]``），既安全又可逆、且无碰撞。

    Args:
        scope: 作用域名

    Returns:
        形如 ``<hex>.pkl`` 的文件名
    """
    return binascii.hexlify(scope.encode("utf-8")).decode("ascii") + ".pkl"


class StateMachineWorker(BaseWorker):
    """State machine Worker - manages state machine persistence.

    Features:
    - automatically loads and saves the state machine
    - thread-safe state machine access
    - file checksums and backups

    落盘方式由 `stateMachine:incrementalSave` 在**运行期**选择：关闭时整表落盘
    （现状），开启时 `stateMachine:picklePath` 解释为目录、每拍只写脏作用域
    （add-state-query-index-and-incremental-persistence 原语 3）。
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
                # 先按 TTL 淘汰过期作用域，再落盘（原语 3）
                self._evict_expired_scopes(state_machine_manager)
                self._save_state_machines(state_machine_manager)

    def _evict_expired_scopes(self, state_machine_manager):
        """按配置的 TTL 淘汰过期作用域，并在增量模式下清理其持久化文件（原语 3）。

        Args:
            state_machine_manager: the state machine manager instance
        """
        from zoo_framework.params import StateMachineParams

        expired = state_machine_manager.evict_expired_scopes(StateMachineParams.SCOPE_TTL_SECONDS)
        if expired and StateMachineParams.INCREMENTAL_SAVE:
            self._remove_scope_files(expired, StateMachineParams.PICKLE_PATH)

    def _load_state_machines(self, state_machine_manager):
        """Load the state machine (thread-safe).

        按 `stateMachine:incrementalSave` 在运行期决定读盘方式：关闭时读整表文件
        （现状），开启时读增量目录（必要时把既有整表文件迁移为目录布局）。

        Args:
            state_machine_manager: the state machine manager instance
        """
        from zoo_framework.params import StateMachineParams

        # Use the file lock to protect file reading
        with self._file_lock:
            if state_machine_manager.have_loaded():
                return

            path = StateMachineParams.PICKLE_PATH
            if StateMachineParams.INCREMENTAL_SAVE:
                self._load_incremental(state_machine_manager, path)
            else:
                self._load_whole_table(state_machine_manager, path)

    def _load_whole_table(self, state_machine_manager, path):
        """按整表 pickle 文件恢复状态（现状路径）。

        Args:
            state_machine_manager: the state machine manager instance
            path: 整表文件路径
        """
        with self._file_lock:
            if state_machine_manager.have_loaded():
                return

            if FileUtils.file_exists(path):
                try:
                    with open(path, "rb") as f:
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

    def _load_incremental(self, state_machine_manager, path):
        """按增量目录恢复状态；撞上既有整表文件时先迁移（原语 3 / D2）。

        迁移步骤：读入旧整表 -> 原文件改名 ``<原名>.migrated.bak`` 留档 -> 以目录
        布局整体写出。数据不删、不静默误读。启动恢复以 manifest 为准、孤儿文件忽略。

        Args:
            state_machine_manager: the state machine manager instance
            path: `stateMachine:picklePath`（增量模式下解释为目录）

        Raises:
            PersistenceError: 旧整表文件留档（改名）失败——此时不建目录，避免覆盖原文件
        """
        if os.path.isdir(path):
            self._load_from_manifest(state_machine_manager, path)
            return

        if os.path.isfile(path):
            LogUtils.info("🔁 Migrating legacy whole-table state file to incremental layout")
            self._load_whole_table(state_machine_manager, path)
            migrated = path + ".migrated.bak"
            try:
                os.replace(path, migrated)
            except OSError as e:
                raise PersistenceError(
                    "迁移旧整表状态文件失败（无法留档到 "
                    f"{migrated}，配置键 stateMachine:picklePath -> {path}）: {e}"
                ) from e
            LogUtils.info(f"📦 Legacy state file archived as {migrated}")
            # 迁移即全量落盘一次：全部标记为脏，再以目录布局写出
            state_machine_manager.mark_all_dirty()
            self._save_incremental(state_machine_manager, path)
            return

        LogUtils.info("📝 No state machine directory/file found, creating new")
        state_machine_manager.load_state_machines()

    def _load_from_manifest(self, state_machine_manager, directory):
        """从增量目录的 manifest 恢复各作用域（孤儿文件忽略）。

        Args:
            state_machine_manager: the state machine manager instance
            directory: 增量目录
        """
        strategy = PicklePersistenceStrategy()
        manifest = self._read_manifest(strategy, os.path.join(directory, _MANIFEST_NAME))
        if not manifest:
            LogUtils.warning("⚠️ 增量目录无有效 manifest，按空状态恢复")
            state_machine_manager.load_state_machines()
            return

        data: dict = {}
        for scope, filename in manifest.items():
            scope_obj = strategy.load(os.path.join(directory, filename))
            if scope_obj is not None:
                data[scope] = scope_obj

        LogUtils.info(f"✅ Incremental state machines loaded: {len(data)} scopes")
        state_machine_manager.load_state_machines(data)

    def _save_state_machines(self, state_machine_manager=None):
        """Save the state machine (thread-safe).

        按 `stateMachine:incrementalSave` 在运行期决定落盘方式：关闭时整表落盘
        （现状），开启时只写脏作用域。

        Args:
            state_machine_manager: the state machine manager instance;
                auto-acquired when None
        """
        from zoo_framework.params import StateMachineParams

        if state_machine_manager is None:
            state_machine_manager = StateMachineManager()

        # Use the file lock to protect file writing
        with self._file_lock:
            if StateMachineParams.INCREMENTAL_SAVE:
                self._save_incremental(state_machine_manager, StateMachineParams.PICKLE_PATH)
            else:
                self._save_whole_table(state_machine_manager, StateMachineParams.PICKLE_PATH)

    def _save_whole_table(self, state_machine_manager, path):
        """整表落盘（现状路径）：先备份、写 ``.tmp``、原子替换。

        Args:
            state_machine_manager: the state machine manager instance
            path: 整表文件路径
        """
        with self._file_lock:
            try:
                # Create a backup first
                self._create_backup(path)

                # Write the temp file
                temp_path = path + ".tmp"
                state_machines = state_machine_manager.get_state_machines()

                # Deep-copy to avoid concurrent modification
                copy_value = copy.deepcopy(state_machines)

                with open(temp_path, "wb") as f:
                    pickle.dump(copy_value, f, protocol=pickle.HIGHEST_PROTOCOL)

                # Replace the file atomically
                if os.path.exists(path):
                    os.replace(temp_path, path)
                else:
                    os.rename(temp_path, path)

                LogUtils.debug("💾 State machines saved successfully")

            except Exception as e:
                LogUtils.error(f"❌ Failed to save state machines: {e}")
                # Try restoring the backup
                self._restore_backup(path)

    def _save_incremental(self, state_machine_manager, directory):
        """增量落盘：只写脏作用域的文件，再原子替换 manifest（原语 3 / D2）。

        布局：``directory`` 内含 ``manifest.pkl``（作用域名 -> 文件名）与每作用域一个
        文件；**未修改的作用域不会被重写**。写入顺序为「先写（脏）scope 文件、后原子
        替换 manifest」，启动恢复以 manifest 为准、孤儿文件忽略。被移除 / 淘汰的作用域
        会清理其文件与 manifest 条目。

        Args:
            state_machine_manager: the state machine manager instance
            directory: `stateMachine:picklePath`（增量模式下解释为目录）

        Raises:
            PersistenceError: 目录不可创建，或任一文件 / manifest 写入失败。失败时脏
                标记保持为真，调用方可于下一拍重试（沿用既有原子写 + 显式失败语义）。
        """
        dirty = state_machine_manager.get_dirty_scopes()
        if not dirty:
            return

        strategy = PicklePersistenceStrategy()
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as e:
            raise PersistenceError(
                f"无法创建增量持久化目录 {directory}（配置键 stateMachine:picklePath）: {e}"
            ) from e

        manifest_path = os.path.join(directory, _MANIFEST_NAME)
        manifest = self._read_manifest(strategy, manifest_path)
        state_machines = state_machine_manager.get_state_machines()
        handled: set[str] = set()

        for scope in dirty:
            scope_obj = state_machines.get(scope)
            if scope_obj is None:
                # 作用域已被删除 / 淘汰：清掉其文件与 manifest 条目
                filename = manifest.pop(scope, None)
                if filename is not None:
                    self._remove_file_quietly(os.path.join(directory, filename))
                handled.add(scope)
                continue

            filename = manifest.get(scope) or _scope_file_name(scope)
            filepath = os.path.join(directory, filename)
            if not strategy.save(copy.deepcopy(scope_obj), filepath):
                raise PersistenceError(
                    f"增量落盘失败: {filepath}（配置键 stateMachine:picklePath -> {directory}）；"
                    "失败原因见前一条日志，脏标记保留以便重试"
                )
            manifest[scope] = filename
            handled.add(scope)

        if not strategy.save(manifest, manifest_path):
            raise PersistenceError(
                f"增量 manifest 落盘失败: {manifest_path}（配置键 stateMachine:picklePath -> {directory}）"
            )

        # 仅清除本轮已处理的脏标记：落盘中途失败时其余仍待重试
        state_machine_manager.clear_dirty_scopes(handled)
        LogUtils.debug(f"💾 Incremental state saved: {len(handled)} scopes")

    def _read_manifest(self, strategy, manifest_path) -> dict:
        """读取 manifest；缺失 / 损坏时返回空映射。

        Args:
            strategy: 持久化策略
            manifest_path: manifest 文件路径

        Returns:
            作用域名 -> 文件名的映射；无有效 manifest 时为空 dict
        """
        if not os.path.isfile(manifest_path):
            return {}
        manifest = strategy.load(manifest_path)
        if isinstance(manifest, dict):
            return dict(manifest)
        return {}

    def _remove_scope_files(self, scopes, directory) -> None:
        """删除被淘汰作用域的持久化文件并同步 manifest（增量模式）。

        Args:
            scopes: 被移除的作用域名列表
            directory: 增量目录
        """
        manifest_path = os.path.join(directory, _MANIFEST_NAME)
        if not os.path.isfile(manifest_path):
            return

        strategy = PicklePersistenceStrategy()
        manifest = self._read_manifest(strategy, manifest_path)
        changed = False
        for scope in scopes:
            filename = manifest.pop(scope, None)
            if filename is None:
                continue
            changed = True
            self._remove_file_quietly(os.path.join(directory, filename))

        if changed:
            strategy.save(manifest, manifest_path)

    def _remove_file_quietly(self, path: str) -> None:
        """删除单个持久化文件；失败只记警告（淘汰路径不应因清理失败而中断）。

        Args:
            path: 待删除文件路径
        """
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError as e:
            LogUtils.warning(
                f"⚠️ Failed to remove evicted state file {path}: {e}", self.__class__.__name__
            )

    def _create_backup(self, file_path: str):
        """Create a file backup.

        Args:
            file_path: the original file path
        """
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
            import shutil

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
