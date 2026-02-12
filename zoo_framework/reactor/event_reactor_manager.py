import uuid
from typing import Any, List, Optional

from .event_reactor import EventReactor
from .event_reactor_req import EventReactorReq, ChannelType, get_channel_manager
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict
from zoo_framework.core.aop import cage
from zoo_framework.utils import LogUtils


@cage
class EventReactorManager:
    """
    事件响应处理器
    
    P1 任务：支持事件通道隔离
    """
    reactor_map = ThreadSafeDict()

    # 自动重命名
    auto_rename = True

    def __init__(self):
        for key, value in self.reactor_map.items():
            from zoo_framework.params import EventParams
            value.set_event_timeout(EventParams.EVENT_JOIN_TIMEOUT)

    @classmethod
    def dispatch(
        cls, 
        topic, 
        content, 
        reactor_name="default",
        channel: str = ChannelType.DEFAULT.value
    ):
        """分发事件
        
        P1 任务：支持指定通道分发事件
        
        Args:
            topic: 事件主题
            content: 事件内容
            reactor_name: 响应器名称
            channel: 通道名称（P1 新增）
        """
        reactor = cls.get_reactor(reactor_name)
        
        # P1：创建带通道信息的事件请求
        event_req = EventReactorReq(
            topic=topic,
            content=content,
            reactor_name=reactor_name,
            channel=channel
        )
        
        # 验证通道权限
        if not cls._validate_channel(reactor_name, event_req):
            LogUtils.warning(f"⚠️ Reactor '{reactor_name}' cannot handle channel '{channel}'")
            return
        
        reactor.execute(topic, content)

    @classmethod
    def get_reactor(
        cls, 
        topic, 
        reactor_names: list[str] = None,
        channel: Optional[str] = None
    ) -> list[Any]:
        """获取事件处理器
        
        P1 任务：支持按通道过滤事件处理器
        
        Args:
            topic: 事件主题
            reactor_names: 响应器名称列表
            channel: 通道名称（P1 新增）
            
        Returns:
            响应器列表
        """
        result = cls.reactor_map.get(topic)
        
        if result is None:
            return []

        filter_result = []
        for reactor in result:
            # P1：按名称过滤
            if reactor_names is not None:
                if reactor.reactor_name not in reactor_names:
                    continue
            
            # P1：按通道过滤
            if channel is not None:
                if not cls._validate_channel(reactor.reactor_name, 
                    EventReactorReq(topic, None, reactor.reactor_name, channel)):
                    continue
            
            filter_result.append(reactor)

        return filter_result

    @classmethod
    def _validate_channel(cls, reactor_name: str, event_req: EventReactorReq) -> bool:
        """验证响应器是否可以处理该通道的事件
        
        P1 任务：通道隔离验证
        
        Args:
            reactor_name: 响应器名称
            event_req: 事件请求
            
        Returns:
            是否可以处理
        """
        channel_manager = get_channel_manager()
        return channel_manager.can_handle_event(reactor_name, event_req)

    @classmethod
    def register_reactor_channels(
        cls, 
        reactor_name: str, 
        channels: List[str]
    ) -> None:
        """注册响应器监听的通道
        
        P1 任务：支持通道隔离配置
        
        Args:
            reactor_name: 响应器名称
            channels: 监听的通道列表
        """
        channel_manager = get_channel_manager()
        channel_manager.register_reactor_channels(reactor_name, channels)
        LogUtils.info(f"✅ Reactor '{reactor_name}' registered to channels: {channels}")

    @classmethod
    def get_reactor_name_list(cls):
        """
        获取事件处理器名称列表
        """
        return cls.reactor_map.get_keys()

    @classmethod
    def auto_rename_reactor(cls, reactor: EventReactor):
        """
        自动重命名事件处理器
        """
        reactor.reactor_name = reactor.reactor_name + "_" + uuid.uuid4().__str__()

    @classmethod
    def bind_topic_reactor(cls, topic: str, reactor: EventReactor) -> bool:
        """
        注册事件处理器
        这个方法可以被重写，以实现不同的事件注册方式，比如设置重试机制等
        """
        # 如果自动重命名，则自动重命名
        if cls.reactor_map.get(topic) is None:
            cls.reactor_map[topic] = []

        # 如果名称已经存在，则不注册

        # 寻找是否已经存在
        if reactor in cls.reactor_map[topic]:
            # 判断重命名策略
            if cls.auto_rename is False:
                return False
            cls.auto_rename_reactor(reactor)
            cls.reactor_map[topic].append(reactor)
            return True

        cls.reactor_map[topic].append(reactor)
        return True

    @classmethod
    def dispatch_by_channel(
        cls,
        topic: str,
        content: Any,
        channel: str = ChannelType.DEFAULT.value
    ) -> None:
        """按通道分发事件
        
        P1 任务：支持按通道广播事件
        
        Args:
            topic: 事件主题
            content: 事件内容
            channel: 目标通道
        """
        channel_manager = get_channel_manager()
        
        # 获取该通道下所有的响应器
        all_reactors = []
        for reactor_name in cls.get_reactor_name_list():
            if channel_manager.can_handle_event(
                reactor_name,
                EventReactorReq(topic, content, reactor_name, channel)
            ):
                reactors = cls.get_reactor(topic, [reactor_name], channel)
                all_reactors.extend(reactors)
        
        # 执行所有匹配的响应器
        for reactor in all_reactors:
            try:
                reactor.execute(topic, content)
            except Exception as e:
                LogUtils.error(f"❌ Reactor '{reactor.reactor_name}' execution failed: {e}")
