"""双臂 Worker 基类：在自身生命周期内闭环「决策 → 计时 → 更新」.

形状（design D2）：子类声明 python 执行体与（可选）原生任务名两条**语义等价**
的臂。``_execute()`` 入口决策——决策/更新全部发生在 Worker 自身生命周期内，
``WorkerDispatchCore`` / 调度模型 / waiter **零感知**（spec「决策在 worker
内完成」）；结果照既有 ``BaseWorker.run()`` → ``WorkerResult`` → 单一结算收口
投递，本类不新增投递点。

奖励语义：实测执行时长（秒，越小越优）；决策臂 ≠ 实际臂时（native 臂不可用
被拒的路径不存在——显式拒绝语义保证），按**实际臂**记录（训练标签要贴脸）。

线程安全（design D6）：统计 key = **类名**（同名多实例共享统计，这正是
「逐类学习」语义）；实例无独立统计状态。
"""

import time

from zoo_framework.core.adaptive import (
    ARM_NATIVE,
    ARM_PYTHON,
    BanditPolicy,
    get_bandit_policy,
)
from zoo_framework.workers import BaseWorker

# 模块级不 import zoo_framework.params：本模块经 workers/__init__ 挂在 kernel 引导链
# （core.master ← workers ← ...），模块级导入既成环，又把参数解析提前到 config.json
# 读取之前、冻结在默认值。AdaptiveParams 一律在方法内 lazy import（既有先例：
# Master._create_waiter / base_waiter / StateMachineWorker）。

#: 子类 props 中声明原生任务名的键
_NATIVE_TASK_KEY = "native_task_name"


class DualArmWorker(BaseWorker):
    """以在线自学的路由决策在「原生/Python」双臂间选择执行体.

    Attributes:
        native_task_name: 子类 props 声明的原生任务名；None 表示纯 python 臂
            （恒定 python，不参与决策也不取锁）

    子类 MUST 实现 :meth:`_execute_python`（python 臂执行体）；声明了原生臂的，
    再提供 :meth:`_prepare_native_input`（到达 ``NativeAdapter.execute`` 的
    bytes 载荷；默认取 ``props["input"]``）。

    关闭语义（spec「关闭时零影响」）：``adaptive:enabled=false``（默认）时按
    纯 python 臂执行，不进入 bandit 分支、不取锁。

    显式拒绝语义（spec「原生臂不可用时显式拒绝」）：声明了原生臂但
    ``native:enabled=false`` 或扩展缺失/握手失败 → 构造期显式报错，MUST NOT
    有人一次静默的 python 臂执行。
    """

    def __init__(self, props: dict, policy: BanditPolicy | None = None):
        """Args:
            props: Worker 属性字典（含可选 ``native_task_name``）
            policy: 注入的决策器（测试用）；None 取进程级单例

        Raises:
            NotImplementedError: 子类未实现 ``_execute_python``
            RuntimeError: 声明了原生臂但原生执行未启用
            NativeInvalidInput: 原生扩展缺失 / 握手失败（复用 adapter 错误族）
        """
        super().__init__(props)
        # 「子类未覆写 _execute_python」判据：与基类自带定义做**函数身份比较**——
        # 在实例上 getattr 是绑定方法（`is not` 函数本体恒真，探测会失效），
        # 且要比较必须在 type(self) 上取，继承未覆写时与基类函数同一对象。
        if type(self)._execute_python is DualArmWorker._execute_python:
            raise NotImplementedError(
                f"{type(self).__name__} MUST 实现 _execute_python()——"
                "DualArmWorker 声明的 python 臂执行体由子类提供，不能猜"
            )

        self.native_task_name = (
            str(props[_NATIVE_TASK_KEY]) if props.get(_NATIVE_TASK_KEY) else None
        )
        self.policy = policy if policy is not None else get_bandit_policy()

        if self.native_task_name is not None:
            # 构造期显式拒绝（design D3）：两层都拦在构造期，才有「无一次静默
            # python 臂执行」的时点承诺。
            # 开关层：native:enabled 是框架侧开关，adapter.ensure_ready 只管扩展
            # 层（未安装/版本不匹配/能力不支持），不读这个键——开发期曾指望它统一
            # 拒绝，是计划里的一个错误，正确职责切分如上。
            from zoo_framework.core.params_factory import ParamsFactory
            from zoo_framework.params import NativeParams

            if not ParamsFactory().get_params(
                "native:enabled", default_value=NativeParams.NATIVE_ENABLED
            ):
                raise RuntimeError(
                    f"{type(self).__name__} 声明了原生臂 {self.native_task_name!r}，"
                    "但 native:enabled=false——原生任务执行未启用。请启用开关或去掉"
                    "原生臂声明；不许静默回退 python 臂"
                )
            # 扩展层：复用 NativeAdapter 的握手与「不静默回退」语义——ensure_ready
            # 会把「未安装」「版本不匹配」「能力不支持」挡在执行前。
            from zoo_framework.native import get_native_adapter

            get_native_adapter().ensure_ready()

    # ---------------------------------------------------------------- 执行

    def _execute_python(self):
        """Python 臂执行体——**子类 MUST 实现**，语义与原生臂等价."""
        raise NotImplementedError

    def _prepare_native_input(self) -> bytes:
        """原生臂输入载荷；默认取 ``props["input"]``（MUST 为 bytes）.

        Raises:
            NativeInvalidInput: 输入不是 bytes（adapter 边界转换时报）
        """
        payload = self._props.get("input", b"")
        return payload if isinstance(payload, bytes) else b""

    def _execute(self):
        """决策 → 计时执行对应臂 → 记录实测时长.

        Returns:
            所走臂执行体的返回值（进 WorkerResult.content）

        Raises:
            Exception: 执行体自身的异常照 BaseWorker 契约向上传播（决策层
                异常除外——那按 fail-open 落 python 臂）
        """
        # 关闭判定在决策之前：AdaptiveParams 属 params 包，必须 lazy import
        # （禁止模块级 import——会绕过配置读取时序并造成循环导入，见文件头）。
        from zoo_framework.params import AdaptiveParams

        if not AdaptiveParams.ADAPTIVE_ENABLED or self.native_task_name is None:
            # 关闭（默认）或无双臂：纯 python，零分支零锁（spec「关闭零影响」）
            return self._execute_timed(ARM_PYTHON)

        class_name = type(self).__name__
        try:
            arm = self.policy.decide(class_name)
        except Exception:
            arm = ARM_PYTHON

        if arm == ARM_NATIVE:
            return self._execute_timed(ARM_NATIVE, class_name)
        return self._execute_timed(ARM_PYTHON, class_name)

    def _execute_timed(self, arm: str, class_name: str | None = None):
        """执行指定臂 + 实测计时 + （启用时）把时长记入对应臂.

        Raises:
            Exception: 执行体异常原样向上传播；记录发生在 finally——执行失败
                也记一次实测时长（失败路径的时长同样是该臂的真实成本样本）
        """
        if arm == ARM_NATIVE:
            from zoo_framework.native import get_native_adapter

            adapter = get_native_adapter()
            start = time.perf_counter()
            try:
                payload = self._prepare_native_input()
                contract = adapter.contract(self.native_task_name)  # type: ignore[arg-type]
                raw = adapter.execute(self.native_task_name, payload)  # type: ignore[arg-type]
                return adapter.convert_output(raw, contract)
            finally:
                if class_name is not None:
                    self.policy.record(class_name, ARM_NATIVE, time.perf_counter() - start)
        start = time.perf_counter()
        try:
            return self._execute_python()
        finally:
            if class_name is not None:
                self.policy.record(class_name, ARM_PYTHON, time.perf_counter() - start)
