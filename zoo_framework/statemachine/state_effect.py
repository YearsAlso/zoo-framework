class StateEffect(object):
    """
    状态节点的副作用
    """

    def __init__(self, state, effect):
        self.state = state
        self.effect = effect
        self.execute_count = 0
        self.always_execute = False

        # 响应的权值
        self.power = 0

    def set_always_execute(self, always_execute):
        self.always_execute = always_execute

    def execute(self, *args, **kwargs):
        self.execute_count += 1
        self.effect(*args, **kwargs)
        # 记录执行时的系统时间和负载情况，向调度器报告

    def __repr__(self) -> str:
        """
        :return: str
        """
        return "StateEffect(state=%s, effect=%s)" % (self.state, self.effect)

    def __eq__(self, other) -> bool:
        return (self.state == other.state and
                self.effect == other.effect)

    def __hash__(self) -> int:
        return hash((self.state, self.effect))

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)
