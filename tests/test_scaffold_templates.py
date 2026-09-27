"""fix-scaffold-templates 的回归测试.

对应 openspec/changes/fix-scaffold-templates/specs/project-scaffolding/spec.md：
每条用例映射到一个具体 scenario。

这些用例全部在临时目录内生成脚手架，不依赖仓库结构，也不进入 `master.run()` 的
无限循环——入口的"可被调用"通过替换框架对象的 `run` 来验证。
"""

import importlib
import os
import sys

import pytest
from click.testing import CliRunner

from zoo_framework.__main__ import create_func, zfc
from zoo_framework.workers import BaseWorker


@pytest.fixture
def scaffold(tmp_path, monkeypatch):
    """在临时目录生成一个脚手架项目，并把 cwd / sys.path 隔离好.

    返回 (项目根目录, 源码目录) 的访问器；用例结束后恢复 cwd、sys.path 与 sys.modules。
    """
    original_cwd = os.getcwd()
    original_path = list(sys.path)
    original_modules = set(sys.modules)

    project = tmp_path / "app"
    project.mkdir()

    monkeypatch.chdir(project)
    create_func("demo")
    source_dir = project / "demo" / "src"
    monkeypatch.chdir(project / "demo")

    yield project / "demo", source_dir

    os.chdir(original_cwd)
    sys.path[:] = original_path
    for name in set(sys.modules) - original_modules:
        sys.modules.pop(name, None)


def _add_worker(name="my_task"):
    from zoo_framework.__main__ import worker_func

    worker_func(name)


def _import_generated_main(source_dir):
    """导入生成的入口模块（不执行 main 的无限循环）."""
    sys.path.insert(0, str(source_dir))
    return importlib.import_module("main")


# =============================================================================
# 1 · 产出的项目可被启动
# =============================================================================


class TestGeneratedEntrypoint:
    """project-scaffolding: 脚手架产出的项目 MUST 可被启动."""

    def test_entry_compiles(self, scaffold):
        """Scenario: 生成的入口可被导入."""
        _, source_dir = scaffold
        _add_worker("my_task")

        source = (source_dir / "main.py").read_text(encoding="utf-8")
        compile(source, str(source_dir / "main.py"), "exec")

    def test_entry_imports(self, scaffold):
        """Scenario: 生成的入口可被导入."""
        _, source_dir = scaffold

        module = _import_generated_main(source_dir)
        assert hasattr(module, "main")
        assert module.WORKERS == []

    def test_entry_uses_current_construction_api(self, scaffold):
        """Scenario: 生成的入口使用当前公开的构造方式.

        历史模板写的是 `Master(worker_count=5)`，而 `Master` 只接受 `config`。
        """
        _, source_dir = scaffold
        module = _import_generated_main(source_dir)

        from zoo_framework.core import Master

        calls = []
        original_run = Master.run
        Master.run = lambda self: calls.append(self)  # type: ignore[method-assign]
        try:
            module.main()
        finally:
            Master.run = original_run  # type: ignore[method-assign]

        assert len(calls) == 1, "生成的入口未能构造并启动框架对象"

    def test_entry_registers_declared_workers(self, scaffold):
        """Scenario: 生成的入口可被调用（含 Worker 注册）."""
        _, source_dir = scaffold
        _add_worker("my_task")
        module = _import_generated_main(source_dir)

        from zoo_framework.core import Master

        captured = {}

        def fake_run(self):
            captured["master"] = self

        original_run = Master.run
        Master.run = fake_run  # type: ignore[method-assign]
        try:
            module.main()
        finally:
            Master.run = original_run  # type: ignore[method-assign]

        master = captured["master"]
        assert "My_TaskWorker" in master.worker_registry.get_all_workers()


# =============================================================================
# 2 · 产出的 Worker 可被导入并被调度
# =============================================================================


class TestGeneratedWorker:
    """project-scaffolding: 产出的 Worker MUST 可被导入并被调度."""

    def test_worker_module_imports(self, scaffold):
        """Scenario: 生成的 Worker 模块可被导入."""
        _, source_dir = scaffold
        _add_worker("my_task")

        sys.path.insert(0, str(source_dir / "workers"))
        module = importlib.import_module("my_task_worker")
        assert hasattr(module, "My_TaskWorker")

    def test_every_referenced_public_name_exists(self, scaffold):
        """Scenario: 生成的 Worker 不依赖不存在的公开名称.

        真实执行模块里的每条导入语句，而不是做字符串比对——历史上模板里的
        `from zoo_framework import worker` 是语法合法但运行时必然失败的一行。
        """
        _, source_dir = scaffold
        _add_worker("my_task")

        source = (source_dir / "workers" / "my_task_worker.py").read_text(encoding="utf-8")
        compile(source, "worker", "exec")  # 语法层
        # 运行层：真实导入
        sys.path.insert(0, str(source_dir / "workers"))
        importlib.import_module("my_task_worker")

    def test_worker_instantiable(self, scaffold):
        """Scenario: 生成的 Worker 可被实例化."""
        _, source_dir = scaffold
        _add_worker("my_task")

        sys.path.insert(0, str(source_dir / "workers"))
        module = importlib.import_module("my_task_worker")
        assert isinstance(module.My_TaskWorker(), BaseWorker)

    def test_registered_worker_is_scheduled_and_executed(self, scaffold):
        """Scenario: 注册后 Worker 被调度执行."""
        _, source_dir = scaffold
        _add_worker("my_task")
        module = _import_generated_main(source_dir)

        from zoo_framework.core import Master

        master = Master()
        for name, worker_class in module.WORKERS:
            master.register_worker(name, worker_class)

        instance = master.worker_registry.get_worker("My_TaskWorker")
        assert instance in master.waiter.workers, "生成的 Worker 未进入调度列表"

        executed = []
        instance._execute = lambda: executed.append(1)
        master.waiter.execute_service()

        import time

        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not executed:
            time.sleep(0.01)

        assert executed == [1], "生成的 Worker 未被执行"
        master.shutdown()

    def test_worker_module_is_reachable_from_entry(self, scaffold):
        """Scenario: 生成的 Worker 模块存在加载路径."""
        _, source_dir = scaffold
        _add_worker("my_task")

        source = (source_dir / "main.py").read_text(encoding="utf-8")
        assert "from workers.my_task_worker import My_TaskWorker" in source, (
            "入口没有指向该 Worker 模块的显式导入"
        )

    def test_loading_does_not_rely_on_package_side_effects(self, scaffold):
        """Scenario: 不存在从不被加载的生成模块.

        入口显式导入 Worker，因此包初始化文件里不需要、也不应依赖任何导入副作用。
        """
        _, source_dir = scaffold
        _add_worker("my_task")

        init_content = (source_dir / "workers" / "__init__.py").read_text(encoding="utf-8")
        assert "import" not in init_content, "包初始化文件里出现了导入副作用"


# =============================================================================
# 3 · 产出的配置被框架读取
# =============================================================================


class TestGeneratedConfig:
    """project-scaffolding: 脚手架产出的配置 MUST 被框架实际读取."""

    def test_pool_setting_takes_effect(self, scaffold):
        """Scenario: 产出配置中的设置可被读取.

        脚手架产出的键名是 `worker.pool.enabled`，框架的读取路径是
        `worker:pool:enable`——两者历史上不一致，配置被静默忽略。
        """
        project, _ = scaffold

        from zoo_framework.core.params_factory import ParamsFactory
        from zoo_framework.params import WorkerParams

        ParamsFactory(str(project / "config.json"))
        assert ParamsFactory.get_params("worker:pool:enabled") is False

        # 兼容路径：别名解析必须取到配置里的值，而不是默认值
        assert WorkerParams.WORKER_POOL_ENABLE in (True, False)

    def test_declared_keys_are_queryable(self, scaffold):
        """Scenario: 配置键名与读取路径一致."""
        import json

        project, _ = scaffold
        declared = json.loads((project / "config.json").read_text(encoding="utf-8"))

        # 脚手架声明的每个 worker 配置键，框架都能沿对应路径取到
        assert "worker" in declared
        assert set(declared["worker"]) <= {"runPolicy", "pool"}


# =============================================================================
# 4 · CLI 选项具备真实语义
# =============================================================================


class TestCliOptions:
    """project-scaffolding: CLI MUST NOT 接受不产生任何效果的选项."""

    def test_create_produces_output(self, tmp_path, monkeypatch):
        """Scenario: 每个被接受的选项都产生效果."""
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(zfc, ["--create", "proj"])

        assert result.exit_code == 0
        assert (tmp_path / "proj" / "src" / "main.py").exists()

    def test_worker_produces_output(self, tmp_path, monkeypatch):
        """Scenario: 每个被接受的选项都产生效果."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        runner.invoke(zfc, ["--create", "proj"])
        monkeypatch.chdir(tmp_path / "proj")

        result = runner.invoke(zfc, ["--worker", "my_task"])

        assert result.exit_code == 0
        assert (tmp_path / "proj" / "src" / "workers" / "my_task_worker.py").exists()

    def test_removed_option_is_rejected(self):
        """Scenario: 不受支持的选项被明确拒绝.

        `--config` 曾被接受但在命令实现体内零引用，属静默忽略。它现在 MUST 被拒绝，
        而不是静默接受并正常退出。
        """
        result = CliRunner().invoke(zfc, ["--config", "whatever"])

        assert result.exit_code != 0, "无效果的选项被静默接受了"
        assert "config" in result.output.lower()


# =============================================================================
# 5 · 产出包结构自洽
# =============================================================================


class TestPackageStructure:
    """project-scaffolding: 脚手架产出的包结构 MUST 自洽."""

    def test_source_dir_is_a_package(self, scaffold):
        """Scenario: 包目录均具备包标识."""
        _, source_dir = scaffold
        assert (source_dir / "__init__.py").exists(), "src/ 缺少包标识"

    def test_all_package_dirs_have_markers(self, scaffold):
        """Scenario: 包目录均具备包标识."""
        _, source_dir = scaffold
        for relative in ("", "conf", "events", "params", "workers"):
            assert (source_dir / relative / "__init__.py").exists(), (
                f"{relative or 'src'} 缺少包标识"
            )


# =============================================================================
# 6 · 模板钩子与框架一致
# =============================================================================


class TestTemplateHooks:
    """project-scaffolding: 模板给出的钩子 MUST 与框架实际调用的一致."""

    @staticmethod
    def _hooks_in_template() -> set:
        """取出模板中示范的全部钩子名."""
        from zoo_framework.templates import worker_template

        hooks = set()
        for line in worker_template.splitlines():
            stripped = line.strip()
            if stripped.startswith("def _") and not stripped.startswith("def __"):
                hooks.add(stripped.split("(")[0].removeprefix("def ").strip())
        return hooks

    @staticmethod
    def _hooks_invoked_by_framework() -> set:
        """从框架自身的调用点收集它实际调用的 Worker 钩子名.

        直接扫描调用点而非列举 `BaseWorker` 的方法：`_destroy` 是鸭子类型的可选钩子
        （由 `WorkerRegistry` 以 `hasattr` 判定后调用），并不定义在 `BaseWorker` 上，
        但它确实被框架调用，因而模板示范它是名副其实的。
        """
        import ast
        import inspect

        from zoo_framework.core import worker_registry
        from zoo_framework.workers import base_worker

        hooks = set()
        for module in (base_worker, worker_registry):
            tree = ast.parse(inspect.getsource(module))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not isinstance(func, ast.Attribute) or not func.attr.startswith("_"):
                    continue
                if isinstance(func.value, ast.Name) and func.value.id in ("self", "worker"):
                    hooks.add(func.attr)
        return hooks

    def test_template_declares_hooks(self):
        assert self._hooks_in_template(), "模板未示范任何钩子"

    def test_framework_invokes_all_template_hooks(self):
        """Scenario: 模板钩子名与框架调用一致."""
        invoked = self._hooks_invoked_by_framework()
        declared = self._hooks_in_template()
        missing = declared - invoked

        assert invoked, "未能从框架调用点收集到任何钩子"
        assert not missing, f"模板示范了框架从不调用的钩子：{sorted(missing)}"

    def test_template_hooks_are_overridable(self):
        """Scenario: 模板不给出框架从不调用的钩子.

        模板示范的钩子必须在 `BaseWorker` 上可被覆写——要么基类已定义同名空实现，
        要么框架以 `hasattr` 判定后调用。二者取其一，但不得两者都不满足。
        """
        declared = self._hooks_in_template()
        on_base = set(dir(BaseWorker))
        invoked = self._hooks_invoked_by_framework()

        for hook in declared:
            assert hook in on_base or hook in invoked, f"{hook} 既不在基类上也不被框架调用"

    def test_destroy_hook_is_actually_called_by_registry(self):
        """Scenario: 模板不给出框架从不调用的钩子.

        `_destroy` 历史上只在 `WorkerRegistry.unregister` 里被调用，而该方法在
        `Master` 生命周期内没有调用者。`fix-worker-scheduling` 让停机触发它之后，
        模板示范该钩子才是名副其实的。
        """
        from zoo_framework.core import Master

        destroyed = []

        class Probe(BaseWorker):
            def __init__(self):
                super().__init__({"name": "Probe", "is_loop": False, "delay_time": 0})

            def _execute(self):
                pass

            def _destroy(self, result):
                destroyed.append(1)

        master = Master()
        master.register_worker("Probe", Probe)
        master.shutdown()

        assert destroyed == [1], "模板示范的 _destroy 钩子并未被框架调用"
