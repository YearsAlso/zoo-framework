"""脚手架模板.

模板产出的代码 MUST 直接可用：引用当前真实存在的公开 API，不示范已经废弃或从未
接通的路径。历史上 `worker_template` 里的 `from zoo_framework import worker` 与
`@worker(count=1)` 就是反例——该名称在包根不存在，且 `@worker` 写入的注册表没有
任何消费者，即使导入成功 Worker 也不会被调度。
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

main_template = f"""from zoo_framework.core import Master

{WORKER_IMPORT_MARKER}

WORKERS = [
    {WORKER_REGISTRATION_MARKER}
]


def main():
    master = Master()
    for name, worker_class in WORKERS:
        master.register_worker(name, worker_class)
    master.run()


if __name__ == '__main__':
    main()
"""
