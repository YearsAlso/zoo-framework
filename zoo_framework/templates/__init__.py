

thread_template = '''from zoo_framework.threads import BaseThread


class {{thread_name.title()}}Thread(BaseThread):
    def __init__(self):
        BaseThread.__init__(self, {
            "is_loop": True,
            "delay_time": 10,
            "name": "{{thread_name}}_thread"
        })

    def _execute(self):
        pass

    def _destroy(self, result):
        pass

    def _on_error(self):
        pass

    def _on_done(self):
        pass'''

thread_mod_insert_template = """
\r\nfrom .{{thread_name}}_thread import {{thread_name.title()}}Thread
"""

main_template = """
from zoo_framework.core import Master


def main():
    master = Master(worker_count=5)
    master.run()


if __name__ == '__main__':
    main()
"""