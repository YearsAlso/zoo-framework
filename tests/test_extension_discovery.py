"""扩展包分发与信任语义测试（变更 add-plugin-distribution / issue #247）。

断言纪律：本用例集中「未受信任时不被加载」这类否定式断言，**必须先证明该包确实
被发现过**——否则「没做」与「做对了」不可区分。导入与否用真实模块的导入副作用
（写 marker 文件）判定，不用 mock 的引用捕获断言。
"""

import ast
import json
import re
import sys
import tomllib
from importlib.metadata import EntryPoint
from pathlib import Path

import pytest

import zoo_framework
from zoo_framework.core.extension import (
    ExtensionLoader,
    ExtensionManifest,
    ExtensionManifestError,
    ExtensionPackage,
    ExtensionTrustError,
    ResourceFilter,
    TrustTier,
    resolve_conflicts,
)
from zoo_framework.plugin import load_extensions
from zoo_framework.plugin.sources import (
    ENTRY_POINT_GROUP,
    InstalledDistributionSource,
    LocalPathSource,
)

# 本变更新增的模块（相对仓库根）
_NEW_MODULES = (
    "zoo_framework/core/extension.py",
    "zoo_framework/plugin/sources.py",
    "zoo_framework/params/extension_params.py",
)

# 改动前 [project].dependencies 的发行物名（本变更 MUST NOT 新增）
_RUNTIME_DEPS_BASELINE = {"click", "pyyaml", "python-dotenv"}


@pytest.fixture(autouse=True)
def _isolate_imports():
    """隔离导入副作用：用例结束后移除本用例新引入 sys.modules 的模块。"""
    before = set(sys.modules)
    yield
    for name in set(sys.modules) - before:
        sys.modules.pop(name, None)


def _make_package(
    root: Path,
    package_dir_name: str,
    *,
    module: str,
    marker: Path,
    manifest_name: str | None = None,
    resources: dict | None = None,
    autoload: bool = True,
    module_root: Path | None = None,
) -> Path:
    """在 ``root/<package_dir_name>`` 下写一个扩展包：清单 + 可导入入口模块。

    入口模块被 import 时会写出 ``marker`` 文件——用它判定「是否被加载」。
    入口模块目录落在 ``module_root``（默认同 ``root``）下；若无须导入，两者都行，
    若须导入，须把 ``module_root`` 放进 ``sys.path``。
    """
    package_dir = root / package_dir_name
    package_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict = {
        "name": manifest_name or package_dir_name,
        "version": "1.0.0",
        "entry": module,
        "autoload": autoload,
    }
    if resources is not None:
        manifest["resources"] = resources
    (package_dir / "zoo-extension.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )

    module_dir = (module_root or root) / module
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "__init__.py").write_text(
        "from pathlib import Path\n"
        f"Path({marker.as_posix()!r}).write_text('imported', encoding='utf-8')\n",
        encoding="utf-8",
    )
    return package_dir


def _package(name: str, tier: TrustTier, *, autoload: bool = True, resources=None):
    """构造一个用例内的扩展包（供纯粹的取舍/过滤器用例使用）。"""
    manifest = ExtensionManifest(name=name, autoload=autoload, resources=resources or {})
    return ExtensionPackage(manifest=manifest, tier=tier, origin=f"{tier.value}:{name}")


class TestLocalPathSource:
    """本地路径来源的发现语义。"""

    def test_discovers_package_with_manifest(self, tmp_path):
        root = tmp_path / "user"
        marker = tmp_path / "marker.txt"
        _make_package(root, "pkg-a", module="ext_a", marker=marker)

        found = LocalPathSource({TrustTier.USER: [root]}).discover()

        assert [p.name for p in found] == ["pkg-a"]
        assert found[0].tier is TrustTier.USER
        assert found[0].trusted is False
        assert found[0].origin

    def test_ignores_directory_without_manifest(self, tmp_path):
        root = tmp_path / "user"
        (root / "plain-dir").mkdir(parents=True)
        (root / "plain-dir" / "notes.txt").write_text("x", encoding="utf-8")

        assert LocalPathSource({TrustTier.USER: [root]}).discover() == []

    def test_missing_root_is_skipped(self, tmp_path):
        assert LocalPathSource({TrustTier.PROJECT: [tmp_path / "nope"]}).discover() == []

    def test_malformed_manifest_fails_loudly(self, tmp_path):
        root = tmp_path / "user"
        package_dir = root / "bad"
        package_dir.mkdir(parents=True)
        (package_dir / "zoo-extension.json").write_text("{ not json", encoding="utf-8")

        with pytest.raises(ExtensionManifestError):
            LocalPathSource({TrustTier.USER: [root]}).discover()

    def test_manifest_missing_name_fails_loudly(self, tmp_path):
        root = tmp_path / "user"
        package_dir = root / "bad"
        package_dir.mkdir(parents=True)
        (package_dir / "zoo-extension.json").write_text(
            json.dumps({"version": "1.0.0"}), encoding="utf-8"
        )

        with pytest.raises(ExtensionManifestError):
            LocalPathSource({TrustTier.USER: [root]}).discover()


class TestInstalledDistributionSource:
    """已安装发行物来源的发现语义。"""

    def test_discovers_package_via_entry_point(self, tmp_path, monkeypatch):
        package_dir = tmp_path / "ext_dist_pkg"
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (package_dir / "zoo-extension.json").write_text(
            json.dumps({"name": "ext-dist", "version": "2.0.0", "entry": ""}),
            encoding="utf-8",
        )
        monkeypatch.syspath_prepend(str(tmp_path))

        entry_point = EntryPoint(
            name="ext-dist",
            value="ext_dist_pkg:zoo-extension.json",
            group=ENTRY_POINT_GROUP,
        )
        monkeypatch.setattr(
            "zoo_framework.plugin.sources.importlib.metadata.entry_points",
            lambda **kwargs: [entry_point] if kwargs.get("group") == ENTRY_POINT_GROUP else [],
        )

        found = InstalledDistributionSource().discover()

        assert [p.name for p in found] == ["ext-dist"]
        assert found[0].tier is TrustTier.USER
        assert found[0].origin == "distribution:ext-dist"


class TestTrustGate:
    """项目级信任门禁：拒绝须明确、原子。"""

    def _build_roots(self, tmp_path):
        project_root = tmp_path / "project"
        user_root = tmp_path / "user"
        project_marker = tmp_path / "project.marker"
        user_marker = tmp_path / "user.marker"
        _make_package(
            project_root, "pkg-proj", module="ext_proj", marker=project_marker, module_root=tmp_path
        )
        _make_package(
            user_root, "pkg-user", module="ext_user", marker=user_marker, module_root=tmp_path
        )
        return project_root, user_root, project_marker, user_marker

    def _loader(self, project_root, user_root, *, project_trusted):
        return ExtensionLoader(
            [LocalPathSource({TrustTier.USER: [user_root], TrustTier.PROJECT: [project_root]})],
            project_trusted=project_trusted,
        )

    def test_untrusted_project_is_rejected_loudly_and_atomically(self, tmp_path, monkeypatch):
        project_root, user_root, project_marker, user_marker = self._build_roots(tmp_path)
        monkeypatch.syspath_prepend(str(tmp_path))
        loader = self._loader(project_root, user_root, project_trusted=False)

        # 先证明「确实发现了它」——否则「没导入」与「没看见」不可区分
        discovered = loader.discover()
        by_name = {p.name: p for p in discovered}
        assert set(by_name) == {"pkg-proj", "pkg-user"}
        assert by_name["pkg-proj"].trusted is False
        assert by_name["pkg-user"].trusted is True

        with pytest.raises(ExtensionTrustError) as excinfo:
            loader.load()

        message = str(excinfo.value)
        assert "pkg-proj" in message
        assert "project_trusted" in message
        assert "plugin:trustProject" in message

        # 原子拒绝：项目级**与**用户级的入口模块都未被导入
        assert not project_marker.exists()
        assert not user_marker.exists()
        assert "ext_proj" not in sys.modules
        assert "ext_user" not in sys.modules

    def test_project_package_loads_when_trusted_by_flag(self, tmp_path, monkeypatch):
        project_root, user_root, project_marker, user_marker = self._build_roots(tmp_path)
        monkeypatch.syspath_prepend(str(tmp_path))
        loader = self._loader(project_root, user_root, project_trusted=True)

        loaded = loader.load()

        assert {p.name for p in loaded} == {"pkg-proj", "pkg-user"}
        assert project_marker.exists()
        assert user_marker.exists()

    def test_user_package_loads_without_explicit_trust(self, tmp_path, monkeypatch):
        _project_root, user_root, _pm, user_marker = self._build_roots(tmp_path)
        monkeypatch.syspath_prepend(str(tmp_path))
        loader = ExtensionLoader(
            [LocalPathSource({TrustTier.USER: [user_root]})], project_trusted=False
        )

        loaded = loader.load()

        assert {p.name for p in loaded} == {"pkg-user"}
        assert user_marker.exists()

    def test_trust_by_config_key(self, tmp_path, monkeypatch):
        from zoo_framework.params import ExtensionParams

        project_root = tmp_path / "project"
        marker = tmp_path / "project.marker"
        _make_package(
            project_root, "pkg-proj", module="ext_cfg", marker=marker, module_root=tmp_path
        )
        monkeypatch.syspath_prepend(str(tmp_path))

        # 默认不受信：拒绝
        monkeypatch.setattr(ExtensionParams, "TRUST_PROJECT", False)
        with pytest.raises(ExtensionTrustError):
            load_extensions(project_paths=[project_root])
        assert not marker.exists()

        # 配置键置真：加载
        monkeypatch.setattr(ExtensionParams, "TRUST_PROJECT", True)
        loaded = load_extensions(project_paths=[project_root])
        assert [p.name for p in loaded] == ["pkg-proj"]
        assert marker.exists()


class TestConflictResolution:
    """同名多来源取舍：替换 / 增量 / 无基底。"""

    def test_project_replaces_user(self):
        user = _package("x", TrustTier.USER)
        project = _package("x", TrustTier.PROJECT)

        resolved = resolve_conflicts([user, project])

        assert len(resolved) == 1
        assert resolved[0].tier is TrustTier.PROJECT

    def test_autoload_false_degrades_to_filter_increment(self):
        user = _package(
            "x", TrustTier.USER, resources={"themes": ResourceFilter.from_patterns(["*"])}
        )
        project = _package(
            "x",
            TrustTier.PROJECT,
            autoload=False,
            resources={"themes": ResourceFilter.from_patterns(["!dark"])},
        )

        resolved = resolve_conflicts([user, project])

        assert len(resolved) == 1
        # 基底未被替换
        assert resolved[0].tier is TrustTier.USER
        # 增量排除生效
        assert resolved[0].filter_for("themes").allows("light") is True
        assert resolved[0].filter_for("themes").allows("dark") is False

    def test_autoload_false_without_base_is_not_autoloaded(self):
        project = _package("x", TrustTier.PROJECT, autoload=False)

        assert resolve_conflicts([project]) == []

    def test_higher_tier_wins_over_builtin(self):
        builtin = _package("x", TrustTier.BUILTIN)
        user = _package("x", TrustTier.USER)

        resolved = resolve_conflicts([builtin, user])

        assert len(resolved) == 1
        assert resolved[0].tier is TrustTier.USER


class TestResourceFilter:
    """逐类资源过滤语义。"""

    def test_empty_list_loads_none(self):
        filt = ResourceFilter.from_patterns([])

        assert filt.allows("anything") is False

    def test_exclude_pattern(self):
        filt = ResourceFilter.from_patterns(["*", "!broken.*"])

        assert filt.allows("good") is True
        assert filt.allows("broken.x") is False

    def test_undeclared_kind_defaults_to_all(self):
        manifest = ExtensionManifest(name="x")

        assert manifest.filter_for("prompts").allows("p") is True

    def test_only_excludes_implies_include_all(self):
        filt = ResourceFilter.from_patterns(["!secret.*"])

        assert filt.allows("public") is True
        assert filt.allows("secret.key") is False


class TestZeroPackages:
    """零扩展包时行为不变。"""

    def test_no_sources_discovers_and_loads_nothing(self):
        loader = ExtensionLoader([], project_trusted=False)

        assert loader.discover() == []
        assert loader.load() == []

    def test_empty_source_root_is_noop(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        loader = ExtensionLoader([LocalPathSource({TrustTier.PROJECT: [empty]})])

        assert loader.discover() == []
        assert loader.load() == []

    def test_load_extensions_without_paths_is_noop(self):
        assert load_extensions() == []


class TestNoNewDependency:
    """零新依赖：新增模块只用标准库 / 框架自身。"""

    def _repo_root(self) -> Path:
        return Path(zoo_framework.__file__).resolve().parent.parent

    def test_new_modules_import_only_stdlib_or_framework(self):
        repo_root = self._repo_root()
        assert sys.stdlib_module_names, "标准库名单不可用"
        for rel in _NEW_MODULES:
            tree = ast.parse((repo_root / rel).read_text(encoding="utf-8"))
            for node in tree.body:
                roots: list[str] = []
                if isinstance(node, ast.Import):
                    roots = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and not node.level:
                    roots = [(node.module or "").split(".")[0]]
                for root in roots:
                    assert root in sys.stdlib_module_names or root == "zoo_framework", (
                        f"{rel} 引入了非标准库/非框架依赖：{root}"
                    )

    def test_runtime_dependencies_unchanged(self):
        pyproject = (self._repo_root() / "pyproject.toml").read_text(encoding="utf-8")
        data = tomllib.loads(pyproject)
        names = {
            re.match(r"[A-Za-z0-9._-]+", dep).group(0).lower()
            for dep in data["project"]["dependencies"]
        }
        # 只允许「不新增」：新增第三方运行依赖会红，移除不会
        assert names <= _RUNTIME_DEPS_BASELINE, f"新增了运行依赖：{names - _RUNTIME_DEPS_BASELINE}"
