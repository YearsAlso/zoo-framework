"""脚手架模板.

模板产出的代码 MUST 直接可用：引用当前真实存在的公开 API，不示范已经废弃或从未
接通的路径。历史上 `worker_template` 里的 `from zoo_framework import worker` 与
`@worker(count=1)` 就是反例——该名称在包根不存在，且 `@worker` 写入的注册表没有
任何消费者，即使导入成功 Worker 也不会被调度。

`conf` / `params` / `events` 三个模板分别对应框架的三个扩展点，它们示范的都是
**实测可用**的机制，契约见 `changes/fix-scaffold-cli-contract/design.md` 的 D6：
`@configure` 注册的函数被 Master 无参调用、`@params` 在导入时解析配置、
`@event` 的回调收到的是 `EventReactorReq` 而不是原始载荷。
"""

# 模板中用于定位插入点的标记，`zfc --worker` 依赖它们把新 Worker 接入入口
WORKER_IMPORT_MARKER = "# zfc:worker-imports"
WORKER_REGISTRATION_MARKER = "# zfc:worker-registrations"

worker_template = """from zoo_framework.workers import BaseWorker


class {{worker_name.title()}}Worker(BaseWorker):
    \"\"\"{{worker_name}} Worker.\"\"\"

    def __init__(self):
        BaseWorker.__init__(self, {
            "is_loop": True,
            "delay_time": 10,
            "name": "{{worker_name}}_worker",
        })

    def _execute(self):
        \"\"\"执行业务逻辑。\"\"\"

    def _destroy(self, result):
        \"\"\"Worker 被注销时调用（停机流程会触发）。\"\"\"

    def _on_error(self):
        \"\"\"执行抛异常时调用。\"\"\"

    def _on_done(self):
        \"\"\"单次执行结束时调用（无论成败）。\"\"\"
"""

conf_template = '''"""启动期配置钩子示例.

`@configure(topic=...)` 把函数注册进框架的配置注册表，`Master` 构造时会**无参**
调用注册表里的每个函数。注册发生在导入时，所以本模块必须在 `Master()` 之前被导入
——入口 `main.py` 已经这样做。

同一个 topic 只能注册一个函数，重复注册会静默覆盖，因此每个配置模块应使用各自的
topic。
"""

from zoo_framework.core.aop import configure

# 钩子执行后置为 True，可用于自检；不需要时连同下面的赋值一起删掉
executed = False


@configure(topic="demo_conf")
def demo_conf():
    """框架启动时执行.

    适合放启动期准备：初始化日志、校验环境变量、建立外部连接等。函数不接受参数，
    返回值会被忽略——需要传入什么，就从配置里读。
    """
    global executed
    executed = True
'''

params_template = '''"""配置项声明示例.

`@params` 在**导入时**把类属性替换成 `config.json` 里对应路径的值，路径形如
`a:b:c`，与配置文件的嵌套结构一一对应；取不到时退回 `ParamsPath` 声明的默认值。

本模块的 `demo:greeting` 对应入口同级的 `config.json` 中 `demo.greeting`。
"""

from zoo_framework.core import ParamsPath
from zoo_framework.core.aop import params


@params
class DemoParams:
    """与 `config.json` 的 `demo` 段对应."""

    GREETING = ParamsPath(value="demo:greeting", default="hello from default")
'''

events_template = '''"""事件反应器示例.

`@event(topic=..., channel=...)` 把函数注册为该通道上该主题的反应器，导入本模块
即完成注册。通道之间互相隔离：发到其它通道的同名主题不会触发本反应器。

回调收到的是 **EventReactorReq** 对象而不是原始载荷，载荷在 `req.content` 上。
"""

from zoo_framework.core.aop import event

# 收到的事件载荷，可用于自检；不需要时连同下面的追加一起删掉
received = []


@event(topic="demo_topic", channel="demo_channel")
def on_demo(req):
    """收到 demo_topic 事件时被调用.

    Args:
        req: 事件请求对象，`req.topic` / `req.content` / `req.reactor_name`
    """
    received.append(req.content)
'''

main_template = f"""from zoo_framework.core import Master

# 演示模块导入即生效，且导入时机有约束：
#   conf   —— 注册配置钩子，必须早于 Master()：钩子在 Master 构造时执行
#   params —— 解析 config.json，须在配置载入之后
#   events —— 注册事件反应器
import conf.demo_conf  # noqa: F401
{WORKER_IMPORT_MARKER}

WORKERS = [
    {WORKER_REGISTRATION_MARKER}
]


def main():
    master = Master()

    # 放在 Master() 之后：此时配置已载入、事件通道已就绪
    import events.demo_event  # noqa: F401
    import params.demo_params  # noqa: F401

    for name, worker_class in WORKERS:
        master.register_worker(name, worker_class)
    master.run()


if __name__ == '__main__':
    main()
"""
