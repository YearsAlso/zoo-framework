"""bandit 统计持久化：可选 JSONL 快照（design D4）.

形状：``adaptive:statsPath`` 配置时，``BanditPolicy.snapshot()`` 全量快照以 JSON
对象落地（原子写 .tmp + os.replace，PersistenceScheduler 先例；MD5 完整性校验，
usedforsecurity=False，同 ``FileChecksumValidator`` 先例）；重启时经
``BanditPolicy.restore`` 回填为先验。

纪律：
- 默认路径空 = **不写任何文件**（spec「统计持久化默认关闭」；键有真实消费者，
  不是死键）
- 任何落盘/读盘错误 fail-open（spec「异常退路」）：记日志、按无先验处理，
  MUST NOT 把失败抛给决策层
- 全量快照而非增流：重启先验语义要求整表一致；增流会使截断半行成为常态
"""

import hashlib  # nosec B424 — md5 只做文件完整性校验（usedforsecurity=False），非安全用途
import json
import os
import threading

from zoo_framework.core.params_factory import ParamsFactory
from zoo_framework.utils import FileUtils, LogUtils

#: 快照文档的字段名与版本（结构演进时随手改 _DOC_VERSION）
_DOC_VERSION = 1
_FIELDS_VERSION = "version"
_FIELDS_CLASSES = "classes"
_FIELDS_CHECKSUM = "checksum"


def _md5_of(payload: str) -> str:
    """对字符串取 MD5 hex（仅供完整性校验，非安全用途——同 FileChecksumValidator）."""
    return hashlib.md5(payload.encode("utf-8"), usedforsecurity=False).hexdigest()  # nosec B324


def _serialize(snapshot: dict[str, dict[str, dict[str, float]]]) -> str:
    """把快照序列化为带自校验字段的单文档 JSON 文本."""
    body = json.dumps(
        {_FIELDS_VERSION: _DOC_VERSION, _FIELDS_CLASSES: snapshot},
        ensure_ascii=False,
    )
    checksum = _md5_of(body)
    return json.dumps(
        {
            _FIELDS_VERSION: _DOC_VERSION,
            _FIELDS_CLASSES: snapshot,
            _FIELDS_CHECKSUM: checksum,
        },
        ensure_ascii=False,
    )


class StatsStore:
    """bandit 统计的 JSONL 落盘与恢复（``adaptive:statsPath`` 的消费者）.

    Attributes:
        path: 落盘路径；空串 = 不持久化（全方法空操作）
    """

    def __init__(self, path: str):
        self.path = path or ""
        self._lock = threading.Lock()

    # ------------------------------------------------------------- 写侧

    def flush(self, snapshot: dict[str, dict[str, dict[str, float]]]) -> bool:
        """把整表快照原子写入（.tmp + os.replace）.

        Args:
            snapshot: ``BanditPolicy.snapshot()`` 形态：类目名 -> 臂名 -> {n, mean}

        Returns:
            是否成功；路径未配置恒 True（无事发生不算失败）；写失败 False（内存态
            不受影响，决策 sticking fail-open）
        """
        if not self.path:
            return True
        try:
            with self._lock:
                temp_path = self.path + ".tmp"
                FileUtils.write_text(temp_path, _serialize(snapshot))
                os.replace(temp_path, self.path)
            return True
        except Exception as e:
            LogUtils.error(
                f"bandit 统计落盘失败（保持内存态，不影响决策）: {e}", self.__class__.__name__
            )
            return False

    # ------------------------------------------------------------- 读侧

    def load(self) -> dict[str, dict[str, tuple[int, float]]] | None:
        """读取落盘快照.

        Returns:
            类目名 -> 臂名 -> (n, mean)；路径未配置/文件缺失/损坏返回 None
            （损坏 = 校验不匹配或结构不合法，一律当无先验，fail-open）
        """
        if not self.path:
            return None
        try:
            raw = FileUtils.read_text(self.path)
        except Exception:
            return None  # 文件不存在/不可读 = 无先验（正常路径，不以 error 噪音刷屏）
        try:
            doc = json.loads(raw)
            body = json.dumps(
                {k: doc[k] for k in (_FIELDS_VERSION, _FIELDS_CLASSES)},
                ensure_ascii=False,
            )
            if _md5_of(body) != doc.get(_FIELDS_CHECKSUM):
                LogUtils.error(
                    f"bandit 统计文件校验不匹配，按无先验处理: {self.path}",
                    self.__class__.__name__,
                )
                return None
            if doc.get(_FIELDS_VERSION) != _DOC_VERSION:
                LogUtils.error(
                    f"bandit 统计文件版本不识别（{_DOC_VERSION} 才支持），按无先验处理: {self.path}",
                    self.__class__.__name__,
                )
                return None
            classes = doc[_FIELDS_CLASSES]
            if not isinstance(classes, dict):
                raise TypeError("classes 不是映射")
            restored: dict[str, dict[str, tuple[int, float]]] = {}
            for class_name, arms in classes.items():
                if not isinstance(arms, dict):
                    raise TypeError("arms 不是映射")
                restored[class_name] = {
                    arm: (int(stat["n"]), float(stat["mean"])) for arm, stat in arms.items()
                }
            return restored
        except (KeyError, TypeError, ValueError, AttributeError, json.JSONDecodeError) as e:
            LogUtils.error(f"bandit 统计文件结构不合法，按无先验处理: {e}", self.__class__.__name__)
            return None


def get_stats_store(path: str | None = None) -> StatsStore:
    """进程级 StatsStore 访问入口.

    Args:
        path: 显式路径（测试注入用）；None 现查 ``adaptive:statsPath`` 配置
            （经 ParamsFactory，尊重运行期打桩；AdaptiveParams.STATS_PATH 在
            导入期已冻结为字面值，读它会漏掉配置）

    Returns:
        每次 new 的存储器（无内部共享状态，加锁只为同一实例的并发 flush）
    """
    if path is None:
        # 现查配置（同 DualArmWorker 构造期读 native:enabled 的形态）——
        # AdaptiveParams.STATS_PATH 已在导入期被 @params 冻结为字面值，
        # 直接读该属性会漏掉运行期才读到的 config.json
        path = ParamsFactory().get_params("adaptive:statsPath", default_value="")
    return StatsStore(path or "")
