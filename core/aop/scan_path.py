import importlib

from core.tools.path_tools import parse_path_expression


def scanModule(path, package=None):
    """
    :param path:
    :param package:
    :return:
    """
    def wrapper(cls):
        if path is None or len(path) == 0:
            raise Exception("ScanPath is must not null or empty")

        module_paths = []
        if str(path).count(".*"):
            # 获得路径下所有文件
            module_paths = parse_path_expression(path)

        for module_path in module_paths:
            importlib.import_module(module_path)

        return cls

    return wrapper
