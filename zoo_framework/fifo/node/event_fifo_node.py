class EventFIFONode(object):
    """
    事件队列节点
    """

    def __init__(self, value: dict):
        self.topic = value['topic']
        self.content = value['content']
        # 事件提供者名称,用于指定单个事件响应器处理事件
        self.reactor_name = value['reactor_name']
        # 响应次数
        self.response_count = 0
        # 事件提供者名称,用于指定单个事件响应器处理事件
        self.provider_name = value['provider_name']
        # 失败次数
        self.fail_count = 0
        # 失败后的处理方式
        self.fail_method = value['fail_method']
        # 事件成功后的处理方式
        self.success_method = value['success_method']
        # 事件失败后的处理方式
        self.fail_method = value['fail_method']
