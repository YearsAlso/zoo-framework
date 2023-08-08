import time


class EventNode(object):
    """
    事件节点
    """

    # 事件主题
    topic: str
    # 事件参数
    content: str
    # 响应次数
    retry_times: int
    # 响应机制，1.先抢到的先响应; 2.者优先级高的先响应; 3.全部响应; 4.指定响应者响应
    response_mechanism: int = 3
    # 制定响应者名称
    reactor_name: str = None
    # 是否响应完成
    is_response: bool = False
    # 执行优先级
    priority: int = 0
    # 事件通道名称
    channel_name: str = "default"
    # 超时时间
    timeout: int = 0
    # 超时响应
    timeout_response: callable = None
    # 创建时间
    create_time: int = time.time()
    # 失败响应
    fail_response: callable = None

    def __init__(self, topic: str, content: str, channel_name: str = "default", priority: int = 0):
        self.topic = topic
        self.content = content
        self.retry_times = 0
        self.priority = priority
        self.channel_name = channel_name

    def __repr__(self) -> str:
        """
        :return: str
        """
        return "EventNode(topic=%s, content=%s)" % (self.topic, self.content)

    def __eq__(self, other) -> bool:
        return (self.topic == other.topic and
                self.content == other.content)

    def __hash__(self) -> int:
        return hash((self.topic, self.content))

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)

    def __index__(self):
        # 根据优先级和创建时间计算优先级
        # TODO: 优先级计算公式待优化
        return self.priority + self.create_time % 100000

    def set_fail_response(self, fail_response: callable):
        """
        设置失败响应
        """
        self.fail_response = fail_response

    def set_reactor_name(self, reactor_name: str):
        """
        设置响应者名称
        """
        self.reactor_name = reactor_name

    def set_response_mechanism(self, response_mechanism: int, reactor_name: str = None):
        """
        设置响应机制
        """
        self.response_mechanism = response_mechanism
        if response_mechanism == 4:
            if reactor_name is None:
                raise ValueError("响应机制为4时，响应者名称不能为空")
            self.reactor_name = reactor_name

    def get_topic(self) -> str:
        """
        获取事件主题
        """
        return self.topic

    def get_content(self) -> str:
        """
        获取事件参数
        """
        return self.content

    def set_timeout(self, timeout: int, timeout_response: callable = None):
        """
        设置超时时间
        """
        self.timeout = timeout
        self.timeout_response = timeout_response

    def is_expire(self):
        """
        是否过期
        """
        if self.timeout is None or self.timeout == 0:
            return False

        return 0 < self.timeout < (time.time() - self.create_time)

    def expire_callback(self):
        """
        过期回调
        """
        if self.timeout_response is not None:
            self.timeout_response(self)

    def get_retry_times(self):
        """
        获取重试次数
        """
        return self.retry_times
