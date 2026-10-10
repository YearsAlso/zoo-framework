"""mkdocs 构建钩子：把仓库根的 .well-known/ 复制进站点产物（变更 governance-files / #120）.

为什么需要它——两条实测结论，不是推断：

1. **mkdocs 会忽略点开头的目录。** 把 ``.well-known/security.txt`` 放在 ``docs/``
   下，构建后 ``site/.well-known/`` **不会**产生（同目录下非点开头的文件正常发布），
   所以"在 ``docs/`` 里放一份副本"既不可达、又制造第二份会漂移的副本。
2. **GitHub 不 serve 仓库根的 ``.well-known/``。** 对三个确有该文件的仓库请求
   ``https://github.com/<owner>/<repo>/.well-known/security.txt`` 均返回 404，
   所以"放在根目录就自然可达"也不成立，可达性必须由我们自己的发布路径提供。

因此真源只有仓库根一份，复制发生在构建期。**源文件缺失时构建直接失败**：
"看起来成功但没有 security.txt"的站点比没有更糟——发布出去的是一个指向不存在
文件的 Canonical。

对应 ``openspec/changes/governance-files/design.md`` D1 与 ``ci-and-packaging``
规格中"文档站产物 MUST 发布 .well-known/security.txt"一条。
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

# 真源目录名，位于仓库根（markdown 里写作 .well-known/）
SOURCE_DIR_NAME = ".well-known"


def repository_root(config: dict[str, Any]) -> Path:
    """取仓库根目录.

    以 mkdocs 配置文件的位置为基准，而不是当前工作目录——``mkdocs build`` 可以在
    任意目录下被调用。
    """
    return Path(config["config_file_path"]).resolve().parent


def publish_well_known(config: dict[str, Any]) -> list[Path]:
    """把仓库根的 .well-known/ 复制到站点产物目录.

    Args:
        config: mkdocs 配置字典，需含 ``config_file_path`` 与 ``site_dir``。

    Returns:
        写入产物目录的文件路径列表（按文件名排序）。

    Raises:
        FileNotFoundError: 真源目录不存在或其中没有文件——此时构建必须失败，
            不允许产出一个缺少该文件的站点。
    """
    source = repository_root(config) / SOURCE_DIR_NAME
    files = sorted(p for p in source.iterdir() if p.is_file()) if source.is_dir() else []
    if not files:
        raise FileNotFoundError(
            f"未找到 {SOURCE_DIR_NAME}/ 下的真源文件（查找路径：{source}）："
            "文档站产物必须发布 .well-known/security.txt，构建中止"
        )
    target_dir = Path(config["site_dir"]) / SOURCE_DIR_NAME
    target_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for path in files:
        target = target_dir / path.name
        # 复制字节而非文本：产物要与真源逐字节一致（含行尾），便于机械校验比对
        shutil.copyfile(path, target)
        written.append(target)
    return written


def on_post_build(config: dict[str, Any]) -> None:
    """构建完成后的钩子入口：发布 .well-known/（见 mkdocs.yml 的 hooks 声明）."""
    publish_well_known(config)
