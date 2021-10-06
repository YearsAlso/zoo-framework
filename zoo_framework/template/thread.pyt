from zoo_framework.threads import BaseThread

class {{cls_name}}(BaseThread):
    def __init__(self):
        BaseThread.__init__(self, {
            "is_loop": True,
            "delay_time": 10,
            "name": "{{cls_name}}"
        })