import contextlib
import json
import os

from zoo_framework.utils import FileUtils


class ParamsFactory:
    # 【已知欠债】类属性即进程级共享状态（`get_params` 实际读取的配置字典），须由测试单独
    # 替换（见 tests/test_config_resolution.py 的 fixture）。属容器外、未收编的载体；依据与
    # 判据见 specs/scoped-container 的「框架自身的进程级共享 MUST 被显式归类」。
    config_params: dict = {}

    # 配置载入世代（变更 aop-determinism / issue #51）：每次成功读入配置文件 +1。
    # @params 的解析发生在导入期（包根 `from . import params` 使这无法晚于任何显式
    # 载入），故"解析时配置还没读到"无法在导入现场拦——改在 Master 构造时核对：
    # 解析发生在旧世代、而本 Master 刚读到了非空配置 ⇒ 这些类被冻结在默认值，
    # 大声失败。从未有配置文件时世代永为 0，核对不触发——"全默认"是合法运行形态。
    _generation = 0

    def __init__(self, config_path="./config.json"):
        if not os.path.exists(config_path):
            return

        # 配置文件的读写 MUST 显式指定编码：默认编码随平台变化（Windows 中文环境为 GBK），
        # 会让同一份配置在不同平台上被解析成不同的值，且不抛异常。
        ParamsFactory.config_params = json.loads(FileUtils.read_text(config_path))
        ParamsFactory._generation += 1

        # 处理 exports
        self.load_exports()

    def load_exports(self):
        export_files = self.config_params.get("_exports")
        # 用 `isinstance` 而非 `type(x) != type([])`：后者不构成检查器可识别的类型收窄
        # （故基线此处一直报 union-attr），且会连带**拒绝 list 的子类**。
        # 配置来自 JSON，产出的是精确 list，两种写法在本场景等价。
        if not isinstance(export_files, list):
            return

        for export_file in export_files:
            self.load_export_file(export_file)

    def load_export_file(self, export_name):
        file_name = "./" + export_name + ".json"

        if not FileUtils.file_exists(file_name):
            return
        content = self.get_export_file(file_name)
        ParamsFactory.config_params[export_name] = content

    def get_export_file(self, file_name):
        """读取导出配置文件；读不到或解析失败时返回空字典."""
        content = {}
        # 读不到或解析不了都按"空配置"处理，调用方只关心能否取到内容
        with contextlib.suppress(Exception):
            content = json.loads(FileUtils.read_text(file_name))

        return content

    @classmethod
    def generation(cls) -> int:
        """当前配置载入世代（@params 解析时记录，Master 构造时核对，#51）."""
        return cls._generation

    @classmethod
    def get_params(cls, path, default_value=""):
        if path is None or path == "":
            return default_value
        path_split = path.split(":")
        value = cls.config_params
        for item in path_split:
            if value.get(item) is None:
                return default_value
            value = value[item]
        return value
