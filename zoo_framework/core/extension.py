"""扩展包分发与信任语义（内核，纯语义、无 I/O）.

本模块回答的是「谁被允许进入运行时」：扩展包（extension package）作为第三方扩展、
主题、提示模板与示例的**唯一分发单位**，按**内置 / 用户级 / 项目级**三档被发现；
项目级条目**默认不受信任**，须显式信任方可加载，拒绝时**明确报错**而非静默跳过。

分层纪律：这里的信任与发现**语义**在内核；具体的来源适配器（本地路径 / 已安装发行物）
在插件层（``zoo_framework.plugin.sources``），内核不 import 任何具体来源。

本模块不持有任何模块级 / 类级可变容器（进程级共享载体须在
``zoo_framework.core.process_state.CARRIERS`` 登记），故对 ``tests`` 的载体扫描无新增负担。
"""

import fnmatch
import importlib
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Protocol

logger = logging.getLogger(__name__)

#: 允许的资源类型（按维护者裁定**不含**「技能」，技能是独立的一层语义）。
RESOURCE_KINDS: tuple[str, ...] = ("extensions", "themes", "prompts", "examples")


class ExtensionError(RuntimeError):
    """扩展包分发的基类错误。"""


class ExtensionManifestError(ExtensionError):
    """清单缺失必需字段或字段类型非法。"""


class ExtensionTrustError(ExtensionError):
    """项目级扩展包未受显式信任，拒绝加载。"""


class TrustTier(Enum):
    """扩展包来源档位。

    值自低到高：``BUILTIN`` < ``USER`` < ``PROJECT``；同名冲突时高档位优先。
    """

    BUILTIN = "builtin"
    USER = "user"
    PROJECT = "project"

    @property
    def precedence(self) -> int:
        """档位优先级，越大越高（项目级 > 用户级 > 内置）。"""
        if self is TrustTier.PROJECT:
            return 2
        if self is TrustTier.USER:
            return 1
        return 0


@dataclass(frozen=True)
class ResourceFilter:
    """某一类资源的加载过滤器。

    Attributes:
        includes: 包含 glob 模式；空元组表示该类**全不加载**；默认 ``("*",)`` 全部加载
        excludes: 排除 glob 模式（前缀 ``!`` 的声明解析而来），优先级高于 ``includes``
    """

    includes: tuple[str, ...] = ("*",)
    excludes: tuple[str, ...] = ()

    @classmethod
    def from_patterns(cls, patterns: Sequence[str]) -> "ResourceFilter":
        """从声明列表构造过滤器。

        ``[]`` 表示该类全不加载；``!glob`` 表示排除；其余为包含模式。若只给了排除
        模式而没有包含模式，等价于「全部包含，再排除这些」。

        Args:
            patterns: 资源类型下声明的模式列表。

        Returns:
            解析后的过滤器。

        Raises:
            ExtensionManifestError: 模式不是非空字符串，或排除模式缺少名称。
        """
        includes: list[str] = []
        excludes: list[str] = []
        for raw in patterns:
            if not isinstance(raw, str) or not raw:
                raise ExtensionManifestError(f"资源过滤模式非法：{raw!r}")
            if raw.startswith("!"):
                name = raw[1:]
                if not name:
                    raise ExtensionManifestError(f"排除模式缺少名称：{raw!r}")
                excludes.append(name)
            else:
                includes.append(raw)
        if not includes and not excludes:
            # 显式空列表：该类全不加载
            return cls(includes=(), excludes=())
        if not includes:
            includes = ["*"]
        return cls(includes=tuple(includes), excludes=tuple(excludes))

    def allows(self, name: str) -> bool:
        """判定某个资源名在该类下是否被加载。

        Args:
            name: 资源名。

        Returns:
            命中包含模式且未命中排除模式时为 ``True``。
        """
        if self.includes == () or not any(fnmatch.fnmatchcase(name, p) for p in self.includes):
            return False
        return not any(fnmatch.fnmatchcase(name, p) for p in self.excludes)

    def merged_with(self, extra: "ResourceFilter") -> "ResourceFilter":
        """把 ``extra`` 作为**增量**叠加到 ``self`` 之上。

        用于 ``autoload: false`` 的「过滤器增量」语义：包含项合并（基底为 ``*`` 时保持
        ``*``）、排除项合并；任一侧显式声明为空（``includes == ()``）则结果为空。

        Args:
            extra: 要叠加的过滤器。

        Returns:
            叠加后的新过滤器（不原地改写）。
        """
        if self.includes == () or extra.includes == ():
            return ResourceFilter(includes=(), excludes=())
        includes = self.includes
        if "*" not in self.includes:
            includes = tuple(dict.fromkeys((*self.includes, *extra.includes)))
        excludes = tuple(dict.fromkeys((*self.excludes, *extra.excludes)))
        return ResourceFilter(includes=includes, excludes=excludes)


@dataclass(frozen=True)
class ExtensionManifest:
    """扩展包清单。

    Attributes:
        name: 包名；同名跨档位冲突时按档位取舍。
        version: 版本号。
        entry: 入口模块（可导入路径）；导入它即触发注册。空串表示纯数据包。
        resources: 每类资源的过滤器；未声明的类默认全部加载。
        autoload: 是否自动加载；``False`` 时在同名冲突中退化为过滤器增量。
    """

    name: str
    version: str = "0.0.0"
    entry: str = ""
    resources: Mapping[str, ResourceFilter] = field(default_factory=dict)
    autoload: bool = True

    def filter_for(self, kind: str) -> ResourceFilter:
        """取某类资源的过滤器，未声明时默认全部加载。"""
        return self.resources.get(kind, ResourceFilter())

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any], *, origin: str = "") -> "ExtensionManifest":
        """从映射（如解析后的 JSON）构造清单。

        Args:
            data: 清单映射。
            origin: 来源出处，仅用于错误信息。

        Returns:
            解析后的清单。

        Raises:
            ExtensionManifestError: 缺少合法 ``name``，或字段类型非法，或含未知资源类型。
        """
        where = f"（来源：{origin}）" if origin else ""
        if not isinstance(data, Mapping):
            raise ExtensionManifestError(f"清单必须是对象{where}")

        name = data.get("name")
        if not isinstance(name, str) or not name:
            raise ExtensionManifestError(f"清单缺少合法名称 name{where}")

        version = data.get("version", "0.0.0")
        if not isinstance(version, str):
            raise ExtensionManifestError(f"清单 version 必须是字符串{where}")

        entry = data.get("entry", "")
        if not isinstance(entry, str):
            raise ExtensionManifestError(f"清单 entry 必须是字符串{where}")

        autoload = data.get("autoload", True)
        if not isinstance(autoload, bool):
            raise ExtensionManifestError(f"清单 autoload 必须是布尔{where}")

        raw_resources = data.get("resources", {})
        if not isinstance(raw_resources, Mapping):
            raise ExtensionManifestError(f"清单 resources 必须是对象{where}")
        resources: dict[str, ResourceFilter] = {}
        for kind, patterns in raw_resources.items():
            if kind not in RESOURCE_KINDS:
                raise ExtensionManifestError(
                    f"未知资源类型 {kind!r}{where}；合法值：{RESOURCE_KINDS}"
                )
            if not isinstance(patterns, (list, tuple)):
                raise ExtensionManifestError(f"资源类型 {kind!r} 的模式必须是列表{where}")
            resources[kind] = ResourceFilter.from_patterns(list(patterns))

        return cls(
            name=name,
            version=version,
            entry=entry,
            resources=resources,
            autoload=autoload,
        )


@dataclass(frozen=True)
class ExtensionPackage:
    """一个已被发现（尚未判定信任）的扩展包。

    Attributes:
        manifest: 清单。
        tier: 来源档位。
        origin: 来源出处（人类可读，如目录路径或发行物名），用于错误信息。
        trusted: 是否受信任；由 :class:`ExtensionLoader` 统一判定。
    """

    manifest: ExtensionManifest
    tier: TrustTier
    origin: str
    trusted: bool = False

    @property
    def name(self) -> str:
        """包名（取自清单）。"""
        return self.manifest.name

    def filter_for(self, kind: str) -> ResourceFilter:
        """取某类资源的过滤器。"""
        return self.manifest.filter_for(kind)


class ExtensionSource(Protocol):
    """扩展包来源协议：只负责**发现**并标注档位，不判定信任。"""

    def discover(self) -> list[ExtensionPackage]:
        """发现该来源下的全部扩展包。"""
        ...


def resolve_conflicts(packages: Iterable[ExtensionPackage]) -> list[ExtensionPackage]:
    """按档位对同名扩展包做取舍（替换 / 增量 / 无基底三规则）。

    规则：

    - 档位高者整体**替换**低档位者；
    - 高档位条目 ``autoload`` 为 ``False`` 时**不替换**，而是把自身过滤器作为
      **增量**叠加到低档位条目之上；
    - 若无任何 ``autoload`` 为真的条目可作基底，则该包**不被自动加载**。

    Args:
        packages: 全部已发现条目（可含同名跨档位）。

    Returns:
        取舍后的条目列表，按包名排序。
    """
    by_name: dict[str, list[ExtensionPackage]] = {}
    for pkg in packages:
        by_name.setdefault(pkg.name, []).append(pkg)

    resolved: list[ExtensionPackage] = []
    for name in sorted(by_name):
        entries = sorted(by_name[name], key=lambda p: p.tier.precedence, reverse=True)
        increments: list[ExtensionPackage] = []
        base: ExtensionPackage | None = None
        for entry in entries:
            if entry.manifest.autoload:
                base = entry
                break
            # autoload 为 False 的高档位条目：暂存为增量，继续找基底
            increments.append(entry)
        if base is None:
            # 无基底：整包不自动加载
            continue
        for increment in increments:
            base = _apply_increment(base, increment)
        resolved.append(base)
    return resolved


def _apply_increment(base: ExtensionPackage, increment: ExtensionPackage) -> ExtensionPackage:
    """把 ``increment`` 的资源过滤器叠加到 ``base`` 上，返回新条目（不原地改写）。"""
    merged: dict[str, ResourceFilter] = dict(base.manifest.resources)
    for kind, filt in increment.manifest.resources.items():
        merged[kind] = base.manifest.filter_for(kind).merged_with(filt)
    new_manifest = replace(base.manifest, resources=merged)
    return replace(base, manifest=new_manifest)


def _trust_message(untrusted: Sequence[ExtensionPackage]) -> str:
    """构造明确、可操作的信任错误文本。"""
    lines = [f"拒绝加载 {len(untrusted)} 个未受信任的项目级扩展包："]
    lines.extend(
        f"  - {pkg.name}（档位：{pkg.tier.value}，来源：{pkg.origin}）" for pkg in untrusted
    )
    lines.append(
        "显式信任方式：调用时传 project_trusted=True，"
        "或在 config.json 设 plugin:trustProject=true。"
    )
    return "\n".join(lines)


class ExtensionLoader:
    """扩展包加载器：汇总来源 → 同名取舍 → 信任门禁 → 导入入口模块。

    Args:
        sources: 扩展包来源列表。
        project_trusted: 是否显式信任项目级扩展包；内置与用户级恒可信。
    """

    def __init__(
        self,
        sources: Sequence[ExtensionSource],
        *,
        project_trusted: bool = False,
    ) -> None:
        self._sources = list(sources)
        self._project_trusted = bool(project_trusted)

    @property
    def project_trusted(self) -> bool:
        """项目级扩展包是否受显式信任。"""
        return self._project_trusted

    def is_trusted(self, tier: TrustTier) -> bool:
        """判定某档位是否受信任。"""
        if tier is TrustTier.PROJECT:
            return self._project_trusted
        return True

    def discover(self) -> list[ExtensionPackage]:
        """发现全部来源、取舍同名、并标注信任状态。"""
        raw: list[ExtensionPackage] = []
        for source in self._sources:
            raw.extend(source.discover())
        resolved = resolve_conflicts(raw)
        return [replace(pkg, trusted=self.is_trusted(pkg.tier)) for pkg in resolved]

    def load(self) -> list[ExtensionPackage]:
        """加载全部已发现且受信任的扩展包。

        信任校验**原子**：只要存在未受信任的项目级包，就在导入任何包之前抛出
        :class:`ExtensionTrustError`（不静默跳过，也不先导入受信者）。

        Returns:
            已加载的扩展包列表。

        Raises:
            ExtensionTrustError: 存在未受信任的项目级扩展包。
        """
        packages = self.discover()
        untrusted = [pkg for pkg in packages if not pkg.trusted]
        if untrusted:
            raise ExtensionTrustError(_trust_message(untrusted))

        for pkg in packages:
            entry = pkg.manifest.entry
            if entry:
                importlib.import_module(entry)
                logger.info(f"📦 扩展包 '{pkg.name}' 已加载（来源：{pkg.origin}）")
        return packages
