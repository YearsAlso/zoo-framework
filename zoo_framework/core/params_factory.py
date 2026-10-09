import contextlib
import json
import os

from zoo_framework.utils import FileUtils


class ParamsFactory:
    # [Known debt] the class attribute is process-level shared state (the
    # config dict actually read by `get_params`), to be replaced separately
    # by tests (see the fixture in tests/test_config_resolution.py). A
    # carrier outside the container, not yet absorbed; rationale and
    # criteria in specs/scoped-container's "process-level sharing created by
    # the framework itself MUST be explicitly classified".
    config_params: dict = {}

    # The config-loading generation (aop-determinism / issue #51): +1 per
    # successful config load.
    # @params resolution happens at import time (the package root's
    # `from . import params` prevents it from being later than any explicit
    # load), so "the config had not been read at resolution time" cannot be
    # caught on the spot - the check happens at Master construction instead:
    # resolved in an older generation while this Master just read a non-empty
    # config => those classes were frozen at defaults, fail loudly. Without a
    # config file the generation stays 0 forever and the check never fires -
    # "all defaults" is a legitimate run shape.
    _generation = 0

    def __init__(self, config_path="./config.json"):
        if not os.path.exists(config_path):
            return

        # Reads and writes of the config MUST use an explicit encoding: the
        # default varies by platform (GBK on Windows in a Chinese locale),
        # which would parse the same config differently per platform, with
        # no exception raised.
        ParamsFactory.config_params = json.loads(FileUtils.read_text(config_path))
        ParamsFactory._generation += 1

        # Process the _exports
        self.load_exports()

    def load_exports(self):
        export_files = self.config_params.get("_exports")
        # Use `isinstance` rather than `type(x) != type([])`: the latter is
        # not a type narrowing the checker recognizes (so the baseline kept
        # reporting union-attr here) and would additionally **reject list
        # subclasses**. Config comes from JSON, producing an exact list;
        # both forms are equivalent in this scenario.
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
        """Read an exported config file; return an empty dict on missing or broken parse."""
        content = {}
        # Both unreadable and unparseable count as "empty config"; callers
        # only care whether content is obtainable
        with contextlib.suppress(Exception):
            content = json.loads(FileUtils.read_text(file_name))

        return content

    @classmethod
    def generation(cls) -> int:
        """The current config-loading generation (recorded when @params
        resolves, checked at Master construction, #51).
        """
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
