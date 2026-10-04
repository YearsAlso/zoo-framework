"""约束：不得再用"装饰器替换类"提供单例（scoped-container 第 5.3 步）.

``@cage`` 已删除，但它留下的教训需要一个**可执行的**约束，否则同一模式会继续蔓延——
而它每次蔓延都可能再制造一次 P0（``@cage`` 摧毁类型契约那一次已经造成过）。

本文件用一条与其实现无关的不变式来兜住：**模块级用 ``class`` 语句声明的名字，在模块
上必须仍是类**。任何"把类换成工厂函数/代理/实例"的装饰器都会违反它，无论那个装饰器
叫什么名字。
"""

import ast
from pathlib import Path

import pytest

import zoo_framework

# 排除 params/：import 它们会触发 @params 的解析并**永久冻结**该参数类的取值
# （见 design D8），一个只为静态检查而做的导入不该产生这种副作用。@params 也不属于本
# 反模式——它改的是类属性，不是类的身份。
EXCLUDED_PACKAGES = {"params", "__pycache__"}


def _framework_modules() -> list:
    """框架内所有可安全导入的模块名（排序后，便于失败时定位）."""
    root = Path(zoo_framework.__file__).parent
    modules = []
    for path in sorted(root.rglob("*.py")):
        parts = path.relative_to(root).parts
        if any(part in EXCLUDED_PACKAGES for part in parts):
            continue
        stem = list(parts[:-1] if path.name == "__init__.py" else [*parts[:-1], path.stem])
        if not stem:
            continue
        modules.append(".".join(["zoo_framework", *stem]))
    return modules


def _module_level_class_names(path: Path) -> list:
    """文件中声明的类名（含被装饰器包裹的）.

    取自 AST 而非运行期目录：我们关心的正是"源码里写了 ``class X``，但模块上 ``X``
    已经不是类"这种不一致。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]


def _module_path(module_name: str) -> Path:
    root = Path(zoo_framework.__file__).parent
    relative = module_name.split(".")[1:]
    candidate = root.joinpath(*relative)
    if candidate.with_suffix(".py").exists():
        return candidate.with_suffix(".py")
    return candidate / "__init__.py"


def _find_class_replacements(module, path: Path) -> list:
    """找出"源码里声明为 class、但模块上已不是类"的名字.

    Returns:
        形如 ``["Foo → function"]`` 的说明列表；无违规时为空
    """
    offenders = []
    for name in _module_level_class_names(path):
        exposed = getattr(module, name, None)
        # 取不到说明该名字是函数内的局部类，不在本不变式的范围内
        if exposed is not None and not isinstance(exposed, type):
            offenders.append(f"{name} → {type(exposed).__name__}")
    return offenders


class TestNoDecoratorReplacesClasses:
    """模块级声明的类，在模块上必须仍是类."""

    @pytest.mark.parametrize("module_name", _framework_modules())
    def test_declared_classes_are_still_classes(self, module_name):
        import importlib

        module = importlib.import_module(module_name)
        offenders = _find_class_replacements(module, _module_path(module_name))

        assert not offenders, (
            f"{module_name} 里有类被装饰器换掉了（不再是类）：{offenders}；"
            f"这会让 issubclass / isinstance 失效，正是 @cage 被删除的原因"
        )

    def test_the_scan_actually_covers_the_framework(self):
        """前提检查：扫描确实覆盖到了模块，否则上面的参数化是空转."""
        modules = _framework_modules()
        assert len(modules) > 20, f"只扫到 {len(modules)} 个模块，覆盖不足"

    def test_the_invariant_catches_a_replacement(self, tmp_path):
        """鉴别力检查：构造一个"类被装饰器换成函数"的模块，不变式必须报出来.

        用临时模块验证检查本身有效，而不是只验证"当前恰好没违规"。
        """
        import importlib.util

        probe = tmp_path / "poisoned_probe.py"
        probe.write_text(
            "def replace_with_factory(cls):\n"
            "    return lambda: cls()\n"
            "\n"
            "@replace_with_factory\n"
            "class Replaced:\n"
            "    pass\n"
            "\n"
            "class Intact:\n"
            "    pass\n",
            encoding="utf-8",
        )
        spec = importlib.util.spec_from_file_location("poisoned_probe", probe)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        offenders = _find_class_replacements(module, probe)

        assert offenders == ["Replaced → function"], offenders
        assert not isinstance(module.Replaced, type), "前提：探针里的类确实被替换了"
        assert isinstance(module.Intact, type), "前提：未装饰的类应不受影响"


class TestCageIsGone:
    """``@cage`` 不得被重新引入."""

    def test_cage_is_not_exported(self):
        from zoo_framework.core import aop

        assert not hasattr(aop, "cage"), "@cage 又被导出了"
        assert "cage" not in aop.__all__

    def test_cage_is_not_in_the_core_namespace(self):
        import zoo_framework.core as core

        assert not hasattr(core, "cage")
        assert "cage" not in core.__all__

    def test_cage_module_is_gone(self):
        with pytest.raises(ImportError):
            import zoo_framework.core.aop.cage  # noqa: F401

    def test_process_scoped_is_the_replacement(self):
        """替换品必须在，且不改变类的身份——否则这条约束只是"删了个东西"."""
        from zoo_framework.core.container import ThreadSafety, process_scoped

        @process_scoped(thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
        class Probe:
            pass

        assert isinstance(Probe, type)
