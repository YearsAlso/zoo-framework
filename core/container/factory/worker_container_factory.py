from core.container.factory.base_container_factory import BaseContainerFactory
from core.container.worker_container import WorkerContainer


class WorkerContainerFactory(BaseContainerFactory):
    container_cls = WorkerContainer
