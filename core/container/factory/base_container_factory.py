from core.container.base_container import BaseContainer


class BaseContainerFactory(object):
    containers: dict = {}
    container_cls: type = BaseContainer
    cls_strict: bool = False

    @classmethod
    def get_container(cls, target_container_name):
        return cls.containers.get(target_container_name)

    @classmethod
    def add_container(cls, target_container_cls: type, target_container_name: str):
        if target_container_cls is None:
            raise Exception("container_cls is None")

        if target_container_name is None or len(target_container_name) <= 0:
            target_container_name = target_container_cls.__name__

        if cls.cls_strict:
            if target_container_name != cls.container_cls:
                raise Exception(
                    "ContainerFactory strict mode is 'True' that means is target container's type must equal attribute: container_cls")

        if cls.containers.get(target_container_name) is not None:
            target_container_name += "_" + str(len(cls.containers))


        cls.containers[target_container_name] = target_container_cls
