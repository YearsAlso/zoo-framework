"""原生任务 Worker：复用既有 Worker 生命周期，``_execute()`` 内委托执行契约.

形状（design D2）：继承 :class:`~zoo_framework.workers.BaseWorker`；结果交既有
hooks 与 :class:`~zoo_framework.workers.WorkerResult`，随后走**既有单一结算收口**
（``run_and_settle → settle``）——本类不新增投递点，适配器也不投递。

适配器依赖注入（默认取模块级单例 ``get_native_adapter()``），使生命周期与结算
契约的测试可以驱动 fake adapter 而不需要真实 Rust 扩展。
"""

from zoo_framework.workers import BaseWorker

from .adapter import get_native_adapter


class NativeTaskWorker(BaseWorker):
    """以既有 Worker 形态执行一个原生任务.

    Attributes:
        task_name: 要执行的原生任务名（MUST 已在扩展侧注册）
        adapter: 注入的原生适配器；缺省为进程级单例

    ``props`` 里除 BaseWorker 的既有键外，本类读取：

    - ``task_name``（必需；缺省时报错而不是猜）

    结果语义：``_execute()`` 返回转换后的 Python 值，跑进 ``BaseWorker.run()``
    统一包成 :class:`~zoo_framework.workers.WorkerResult`（含 worker 名），
    运行标识（run_id / session_id）由结算点盖章——本类不碰身份字段。
    """

    def __init__(self, props: dict, adapter=None):
        """Args:
            props: Worker 属性字典（含 ``task_name``）
            adapter: 可选注入的原生适配器；None 取模块级单例

        Raises:
            ValueError: props 未声明 ``task_name``
        """
        super().__init__(props)
        task_name = props.get("task_name")
        if not task_name:
            raise ValueError(
                "NativeTaskWorker 需要显式 task_name（原生任务按显式名称注册，"
                "不能把任意 callable 当作原生任务）"
            )
        self.task_name = str(task_name)
        self.adapter = adapter if adapter is not None else get_native_adapter()

    def _execute(self):
        """委托执行契约：边界转换输入 → 扩展执行（体内释放 GIL）→ 转换输出.

        Returns:
            转换后的输出值（进 WorkerResult.content）

        Raises:
            NativeInvalidInput: 契约读取失败 / 输入格式或尺寸不满足
            NativeTaskFailed / NativePanic: 扩展侧受控错误或 panic
        """
        contract = self.adapter.contract(self.task_name)
        payload = self.adapter.prepare_input(self._props.get("input"), contract)
        raw_output = self.adapter.execute(self.task_name, payload)
        return self.adapter.convert_output(raw_output, contract)
