"""mkdocs 构建钩子：把仓库根的真源文件复制进站点产物.

当前清单两项（见 ``COPY_MANIFEST``）：``.well-known/``（变更 governance-files / #120）
与 ``llms.txt``（变更 agent-discoverability / #122）。

为什么需要它——两条实测结论，不是推断：

1. **mkdocs 会忽略点开头的目录。** 把 ``.well-known/security.txt`` 放在 ``docs/``
   下，构建后 ``site/.well-known/`` **不会**产生（同目录下非点开头的文件正常发布），
   所以"在 ``docs/`` 里放一份副本"既不可达、又制造第二份会漂移的副本。
2. **GitHub 不 serve 仓库根的 ``.well-known/``。** 对三个确有该文件的仓库请求
   ``https://github.com/<owner>/<repo>/.well-known/security.txt`` 均返回 404，
   所以"放在根目录就自然可达"也不成立，可达性必须由我们自己的发布路径提供。

``llms.txt`` 同理：llms.txt 约定把该文件放在**站点根**，只放在仓库里取不到那个 URL，
发现性的目的即落空。它与 ``.well-known/`` 是同一形态（真源唯一 + 构建期复制），
因此复用同一条发布路径，而不是另写一套。

因此真源只有仓库根一份，复制发生在构建期。**清单里任一项的源缺失时构建直接失败**：
"看起来成功但没有 security.txt / llms.txt"的站点比没有更糟——发布出去的是一个指向
不存在文件的 Canonical（security.txt），或一个取不到检索入口的站点（llms.txt）。

对应 ``openspec/changes/governance-files/design.md`` D1、
``openspec/changes/agent-discoverability/design.md`` D4，以及 ``ci-and-packaging``
规格中"文档站产物 MUST 发布 .well-known/security.txt 与仓库根 llms.txt"两条。
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

# 真源目录名，位于仓库根（markdown 里写作 .well-known/）
SOURCE_DIR_NAME = ".well-known"

# llms.txt 的文件名，同样位于仓库根（llms.txt 约定的位置是站点根，见模块 docstring）
LLMS_TXT_NAME = "llms.txt"

# 复制清单：每一项是 (仓库根下的名称, 是否为目录, 该项为何必须发布)。
# 逐项取自仓库根的**唯一手写真源**，复制到站点产物中的同名位置；
# 任一项的源缺失即构建失败——静默跳过正是本模块要消除的失败模式。
COPY_MANIFEST: tuple[tuple[str, bool, str], ...] = (
    (SOURCE_DIR_NAME, True, "文档站产物必须发布 .well-known/security.txt"),
    (LLMS_TXT_NAME, False, "文档站产物必须发布 llms.txt（llms.txt 约定的位置是站点根）"),
)


def repository_root(config: dict[str, Any]) -> Path:
    """取仓库根目录.

    以 mkdocs 配置文件的位置为基准，而不是当前工作目录——``mkdocs build`` 可以在
    任意目录下被调用。
    """
    return Path(config["config_file_path"]).resolve().parent


def _source_files(root: Path, name: str, is_dir: bool) -> list[Path]:
    """列出某一项在仓库根下的真源文件（目录项取其下所有文件，按名排序）."""
    source = root / name
    if is_dir:
        return sorted(p for p in source.iterdir() if p.is_file()) if source.is_dir() else []
    return [source] if source.is_file() else []


def _publish_entry(config: dict[str, Any], name: str, is_dir: bool, reason: str) -> list[Path]:
    """把仓库根下的单项真源复制到站点产物目录.

    Args:
        config: mkdocs 配置字典，需含 ``config_file_path`` 与 ``site_dir``。
        name: 仓库根下的真源名称（目录或文件）。
        is_dir: 真源是否为目录。
        reason: 该项为何必须发布，用于失败信息。

    Returns:
        写入产物目录的文件路径列表。

    Raises:
        FileNotFoundError: 真源不存在或其中没有文件——此时构建必须失败，
            不允许产出一个缺少该文件的站点。
    """
    root = repository_root(config)
    source = root / name
    files = _source_files(root, name, is_dir)
    if not files:
        raise FileNotFoundError(f"未找到真源 {name}（查找路径：{source}）：{reason}，构建中止")
    target_dir = Path(config["site_dir"]) / (name if is_dir else "")
    target_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for path in files:
        target = target_dir / path.name
        # 复制字节而非文本：产物要与真源逐字节一致（含行尾），便于机械校验比对
        shutil.copyfile(path, target)
        written.append(target)
    return written


def publish_manifest(config: dict[str, Any]) -> list[Path]:
    """按 ``COPY_MANIFEST`` 逐项把仓库根真源复制到站点产物目录.

    Args:
        config: mkdocs 配置字典，需含 ``config_file_path`` 与 ``site_dir``。

    Returns:
        写入产物目录的文件路径列表（清单顺序，目录项内按文件名排序）。

    Raises:
        FileNotFoundError: 清单中任一项的真源缺失——构建必须失败。
    """
    written: list[Path] = []
    for name, is_dir, reason in COPY_MANIFEST:
        written.extend(_publish_entry(config, name, is_dir, reason))
    return written


def publish_well_known(config: dict[str, Any]) -> list[Path]:
    """仅发布 ``.well-known/`` 一项（保留 #120 建立的名称与语义）.

    清单里的其余项由 :func:`publish_manifest` 负责；本函数保留是为了不改变
    ``.well-known/`` 既有的公开行为（"目录缺失即失败"是已归档规格里的一条要求）。

    Args:
        config: mkdocs 配置字典，需含 ``config_file_path`` 与 ``site_dir``。

    Returns:
        写入产物目录的文件路径列表（按文件名排序）。

    Raises:
        FileNotFoundError: 真源目录不存在或其中没有文件。
    """
    name, is_dir, reason = next(item for item in COPY_MANIFEST if item[0] == SOURCE_DIR_NAME)
    return _publish_entry(config, name, is_dir, reason)


def on_post_build(config: dict[str, Any]) -> None:
    """构建完成后的钩子入口：按清单发布真源文件（见 mkdocs.yml 的 hooks 声明）."""
    publish_manifest(config)
