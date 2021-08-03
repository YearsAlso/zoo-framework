from core.container.factory.base_container_factory import BaseContainerFactory
from core.container.params_container import ParamsContainer


class ParamsContainerFactory(BaseContainerFactory):
    container_cls = ParamsContainer
