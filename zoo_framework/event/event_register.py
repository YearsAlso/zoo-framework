from zoo_framework.core.container import ThreadSafety, process_scoped


# 声明为"仅限单线程"而不是"实例自身保证"：本类的 event_list 是**裸 list**，既没有
# 锁也不是不可变的（清点时记为 F1）。本模块目前仅被 event/__init__.py 再导出、框架内
# 无调用点，故这条声明是如实而非限制。
@process_scoped(thread_safety=ThreadSafety.SINGLE_THREAD)
class EventRegister:
    """事件注册器."""

    def __init__(self):
        self.event_list = []

    def register(self, event):
        self.event_list.append(event)

    def unregister(self, event):
        self.event_list.remove(event)

    def get_event(self, event_name):
        for event in self.event_list:
            if event.name == event_name:
                return event
        return None

    def get_event_list(self):
        return self.event_list

    def get_event_name_list(self):
        event_name_list = []
        for event in self.event_list:
            event_name_list.append(event.name)
        return event_name_list

    def get_event_by_index(self, index):
        return self.event_list[index]

    def get_event_by_name(self, event_name):
        for event in self.event_list:
            if event.name == event_name:
                return event
        return None

    def get_event_index(self, event_name):
        for index, event in enumerate(self.event_list):
            if event.name == event_name:
                return index
        return None

    def get_event_name_by_index(self, index):
        return self.event_list[index].name

    def get_event_index_by_name(self, event_name):
        for index, event in enumerate(self.event_list):
            if event.name == event_name:
                return index
        return None

    def get_event_count(self):
        return len(self.event_list)

    def get_event_name_count(self):
        return len(self.get_event_name_list())

    def get_event_index_count(self):
        return len(self.get_event_index_list())

    def get_event_index_list(self):
        event_index_list = []
        for index, _event in enumerate(self.event_list):
            event_index_list.append(index)
        return event_index_list

    def get_event_name_index_list(self):
        event_name_index_list = []
        for index, event in enumerate(self.event_list):
            event_name_index_list.append((event.name, index))
        return event_name_index_list

    def get_event_index_by_name_index(self, event_name_index):
        for index, event in enumerate(self.event_list):
            if event.name == event_name_index[0] and index == event_name_index[1]:
                return index
        return None

    def get_event_name_by_index_index(self, event_index_index):
        for index, event in enumerate(self.event_list):
            if index == event_index_index[1] and event.name == event_index_index[0]:
                return event.name
        return None
