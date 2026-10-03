from zoo_framework.core import event
from zoo_framework.utils import LogUtils


class DemoEvent:
    @staticmethod
    @event("change_test_number")
    def on_change_test_number(data):
        LogUtils.debug("Test", f"on_get_test:{data}")
