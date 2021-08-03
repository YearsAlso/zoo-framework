from core.container.config_container import ConfigContainer
from core.container.factory.base_container_factory import BaseContainerFactory


class ConfigContainerFactory(BaseContainerFactory):
    container_cls = ConfigContainer
    config_params = {}

    def load_config(self, config: dict):
        for key, value in config.items():
            self.config_params[key] = value

    def add_container(cls, target_container_cls: type, target_container_name: str):
        super().add_container(target_container_cls, target_container_name)
