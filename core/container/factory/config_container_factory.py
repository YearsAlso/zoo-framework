from core.container.config_container import ConfigContainer
from core.container.factory.base_container_factory import BaseContainerFactory


class ConfigContainerFactory(BaseContainerFactory):
    container_cls = ConfigContainer
