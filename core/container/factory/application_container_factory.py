from core.container.application_container import ApplicationContainer
from core.container.factory.base_container_factory import BaseContainerFactory


class ApplicationContainerFactory(BaseContainerFactory):
    container_cls = ApplicationContainer
