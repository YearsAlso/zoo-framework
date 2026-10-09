"""ε-greedy 两臂统计与决策.

形状（design D1）：每个任务类对称的两条臂（native / python），各持
``(n, mean)`` 增量统计；决策 O(1)（ε 概率随机，否则选均值更优臂——均值相
等时固定选 python 臂，可复现）；更新 O(1)（增量均值 ``1/(n+1)`` 衰减，对旧
样本自然衰退，负载漂移可跟随）。

奖励语义（design D2）：**实测执行时长**（秒，越小越优）——决策与观测在
``DualArmWorker`` 同一生命周期内完成，无需跨处配对。

线程安全（design D6）：单 ``threading.Lock`` 保护读-改-写；临界区 O(1) 乘加。
不用 ThreadSafeDict（multiprocessing.Lock 已被 bench 证伪）。
"""

import random
import threading

#: 两臂的固定名称（决策空间就是这两条；发现第三臂即配置错误）
ARM_NATIVE = "native"
ARM_PYTHON = "python"
#: 均值相等（含双双无样本）时的固定选择：python 臂——保守侧，可复现
_DEFAULT_ARM = ARM_PYTHON


class EpsilonGreedy:
    """一个任务类的两臂 ε-greedy 统计.

    Attributes:
        epsilon: 探索率（0–1）；0 表示纯利用
    """

    def __init__(self, epsilon: float = 0.05):
        """Args:
        epsilon: 探索率；0 ≤ ε < 1，越界值被夹取
        """
        self.epsilon = min(max(float(epsilon), 0.0), 0.999999)
        self._lock = threading.Lock()
        self._stats: dict[str, tuple[int, float]] = {ARM_NATIVE: (0, 0.0), ARM_PYTHON: (0, 0.0)}

    # ---------------------------------------------------------------- 决策

    def decide(self, rng: random.Random | None = None) -> str:
        """ε-greedy 决策：ε 概率随机臂，否则当前均值更优臂.

        Args:
            rng: 随机源（测试注入固定种子用）；None 则新建

        Returns:
            臂名（ARM_NATIVE / ARM_PYTHON）
        """
        with self._lock:
            native_stats, python_stats = self._stats[ARM_NATIVE], self._stats[ARM_PYTHON]
            best = self._best_arm(native_stats, python_stats)

        if rng is None:
            rng = random.Random()  # nosec B311 — ε-greedy 调度探索，非加密用途
        if rng.random() < self.epsilon:
            return ARM_NATIVE if rng.random() < 0.5 else ARM_PYTHON
        return best

    @staticmethod
    def _best_arm(native_stats: tuple[int, float], python_stats: tuple[int, float]) -> str:
        """选均值更优臂；双方都有样本时严格更小者胜，无样本或相等退 python."""
        native_n, native_mean = native_stats
        python_n, python_mean = python_stats
        if native_n == 0 and python_n == 0:
            return _DEFAULT_ARM
        if native_n == 0:
            return ARM_PYTHON
        if python_n == 0:
            return ARM_NATIVE
        if native_mean < python_mean:
            return ARM_NATIVE
        if python_mean < native_mean:
            return ARM_PYTHON
        return _DEFAULT_ARM

    # ---------------------------------------------------------------- 更新

    def record(self, arm: str, duration: float) -> None:
        """以一次实测时长增量更新对应臂的均值.

        Args:
            arm: 臂名（必须属于两臂）；非法臂名大声报错（KeyError）
            duration: 本次实测执行时长（秒，越小越优）

        Raises:
            KeyError: 臂名不属于本决策空间的两臂
        """
        with self._lock:
            n, mean = self._stats[arm]
            # 增量均值：mean += (x - mean) / (n+1)，与全量均值数学等价
            self._stats[arm] = (n + 1, mean + (duration - mean) / (n + 1))

    def restore(self, stats: dict[str, tuple[int, float]]) -> None:
        """整臂回填统计（重启先验；设计 D4）.

        Args:
            stats: 臂名 -> (n, mean)。只回填两臂键族之内的条目（多余的忽略——
                落盘文件可能来自臂名族不同的旧版本），非法键不报错
        """
        with self._lock:
            for arm, (n, mean) in stats.items():
                if arm in self._stats:
                    self._stats[arm] = (int(n), float(mean))

    def snapshot_stats(self) -> dict[str, tuple[int, float]]:
        """两臂统计（restore 的对称形态；snapshot 的紧凑版，测试断言用）."""
        with self._lock:
            return dict(self._stats)

    # ---------------------------------------------------------------- 视图

    def snapshot(self) -> dict[str, dict[str, float]]:
        """统计快照（持久化与测试断言用）；返回新 dict，与内部态解耦."""
        with self._lock:
            return {arm: {"n": float(n), "mean": mean} for arm, (n, mean) in self._stats.items()}
