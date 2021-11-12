from zoo_framework.threads import BaseWorker

class {{thread_name.title()}}Worker(BaseWorker):
    def __init__(self):
        BaseWorker.__init__(self, {
            "is_loop": True,
            "delay_time": 10,
            "name": "{{thread_name}}_worker"
        })

    def _execute(self):
        pass

    def _destroy(self,result):
        pass

    def _on_error(self):
        pass

    def _on_done(self):
        pass