from zoo_framework.threads import BaseThread

class {{thread_name.title()Thread}}(BaseThread):
    def __init__(self):
        BaseThread.__init__(self, {
            "is_loop": True,
            "delay_time": 10,
            "name": "{{thread_name}}_thread"
        })

    # 执行方法
    def _execute(self):
        pass

    # 释放方法
    def _destroy(self):
        pass

    # 错误处理方法
    def _on_error(self):
        pass

    # 最后执行方法
    def _on_done(self):
        pass