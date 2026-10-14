from zoo_framework.core import param
from zoo_framework.core.aop import params


@params
class TaskParams:
    # 任务队列的默认作用域名（add-task-layer）：仅当调用方以 ``TaskQueue()`` 无参构造时
    # 使用。键不存在时取默认值，行为与合入前一致——不新建队列、不改任何既有作用域。
    # 该键在 ``TaskQueue.__init__`` 中**运行期**读取（惰性导入），避免 ``@params`` 在首次
    # 导入时冻结默认值。
    QUEUE_SCOPE = param(value="task:queue:scope", default="zoo.tasks")
