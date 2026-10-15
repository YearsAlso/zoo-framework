"""扩展包来源适配器（插件层，含 I/O）.

来源只负责**发现**扩展包并标注档位；信任判定由内核的
:class:`zoo_framework.core.extension.ExtensionLoader` 统一完成——来源不判定信任。

两种来源均**只依赖标准库**：

- :class:`LocalPathSource`：扫某个档位根目录下含清单文件的子目录；
- :class:`InstalledDistributionSource`：经入口点组定位已安装发行物里的清单。

本模块不持有任何模块级 / 类级可变容器。
"""

import importlib
import importlib.metadata
import importlib.resources
import json
from collections.abc import Mapping, Sequence
from importlib.metadata import EntryPoint
from pathlib import Path

from zoo_framework.core.extension import (
    ExtensionManifest,
    ExtensionManifestError,
    ExtensionPackage,
    TrustTier,
)

#: 清单文件名。
MANIFEST_FILENAME = "zoo-extension.json"

#: 已安装发行物声明扩展包的入口点组名。
ENTRY_POINT_GROUP = "zoo_framework.extensions"


class LocalPathSource:
    """本地路径来源：扫描每个档位根目录下含清单文件的子目录。

    Args:
        roots: 档位 → 该档位的根目录列表。目录不存在时该项被跳过（不报错）。
    """

    def __init__(self, roots: Mapping[TrustTier, Sequence[str | Path]]) -> None:
        self._roots = roots

    def discover(self) -> list[ExtensionPackage]:
        """发现全部根目录下的扩展包。"""
        found: list[ExtensionPackage] = []
        for tier, paths in self._roots.items():
            for raw_root in paths:
                root = Path(str(raw_root)).expanduser()
                if not root.is_dir():
                    continue
                for child in sorted(root.iterdir(), key=lambda p: p.name):
                    manifest_path = child / MANIFEST_FILENAME
                    if not child.is_dir() or not manifest_path.is_file():
                        continue
                    found.append(_load_local_package(tier, child, manifest_path))
        return found


class InstalledDistributionSource:
    """已安装发行物来源：经入口点组定位清单。

    发行物在其元数据里声明入口点组（默认 ``zoo_framework.extensions``），
    值的形如 ``"<可导入包>:<相对清单路径>"``；相对清单路径缺省为清单文件名。

    Args:
        group: 入口点组名。
        tier: 该来源发现的包的档位；已安装发行物默认为用户级。
    """

    def __init__(
        self,
        group: str = ENTRY_POINT_GROUP,
        tier: TrustTier = TrustTier.USER,
    ) -> None:
        self._group = group
        self._tier = tier

    def discover(self) -> list[ExtensionPackage]:
        """发现全部经入口点组声明的扩展包。"""
        found: list[ExtensionPackage] = []
        for entry_point in importlib.metadata.entry_points(group=self._group):
            found.append(_load_installed_package(self._tier, entry_point))
        return found


def _load_local_package(
    tier: TrustTier,
    package_dir: Path,
    manifest_path: Path,
) -> ExtensionPackage:
    """读取本地目录下的清单并构造条目。"""
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ExtensionManifestError(f"清单无法解析：{manifest_path}（{exc}）") from exc
    manifest = ExtensionManifest.from_mapping(data, origin=str(manifest_path))
    return ExtensionPackage(
        manifest=manifest,
        tier=tier,
        origin=str(package_dir),
        trusted=False,
    )


def _load_installed_package(tier: TrustTier, entry_point: EntryPoint) -> ExtensionPackage:
    """读取某个入口点指向的清单并构造条目。"""
    module_name, _, relative = entry_point.value.partition(":")
    relative = relative or MANIFEST_FILENAME
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise ExtensionManifestError(f"扩展入口模块无法导入：{module_name}（{exc}）") from exc
    resource = importlib.resources.files(module).joinpath(relative)
    try:
        raw = resource.read_text(encoding="utf-8")
    except OSError as exc:
        raise ExtensionManifestError(
            f"入口点清单不可读：{entry_point.name} -> {relative}（{exc}）"
        ) from exc
    data = json.loads(raw)
    manifest = ExtensionManifest.from_mapping(data, origin=f"{entry_point.name}:{relative}")
    return ExtensionPackage(
        manifest=manifest,
        tier=tier,
        origin=f"distribution:{entry_point.name}",
        trusted=False,
    )
