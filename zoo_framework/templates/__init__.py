

worker_template = '''from zoo_framework.workers import BaseWorker


class {{worker_name.title()}}Worker(BaseWorker):
    def __init__(self):
        BaseWorker.__init__(self, {
            "is_loop": True,
            "delay_time": 10,
            "name": "{{worker_name}}_worker"
        })

    def _execute(self):
        pass

    def _destroy(self, result):
        pass

    def _on_error(self):
        pass

    def _on_done(self):
        pass'''

worker_mod_insert_template = """
\r\nfrom .{{worker_name}}_worker import {{worker_name.title()}}Worker
"""

main_template = """
from zoo_framework.core import Master


def main():
    master = Master(worker_count=5)
    master.run()


if __name__ == '__main__':
    main()
"""