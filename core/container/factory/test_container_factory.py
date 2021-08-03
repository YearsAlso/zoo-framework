from core.container.factory.base_container_factory import BaseContainerFactory
from core.container.test_container import TestContainer


class TestContainerFactory(BaseContainerFactory):
    container_cls = TestContainer
