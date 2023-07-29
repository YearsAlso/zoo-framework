from zoo_framework.core.aop import cage
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict


@cage
class EventChannelRegister:
    """
    事件通道注册器
    """
    _single = None
    _instance = None
    _provider_map = ThreadSafeDict()

    def register(self, provider_name, provider):
        self._provider_map[provider_name] = provider

    def unregister(self, provider_name):
        self._provider_map.pop(provider_name)

    def get_provider(self, provider_name):
        return self._provider_map.get(provider_name)
