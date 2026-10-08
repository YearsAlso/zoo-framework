#!/usr/bin/env python3
"""发布版本计算：递增语义 + 跨分支下限（变更 fix-release-version-continuity / #82）.

为什么存在：release.yml 曾在 YAML 内嵌 bash 做版本递增，且**只按本分支声明计算**——
main 升到 0.9.0 后 dev 沿 0.8.x-beta 旧线连发 0.8.3b0/0.8.4b0（版本号永久占用）。
抽成仓内脚本有两个目的：

1. 版本计算单一来源，可被 pytest 直接覆盖（bash 内嵌逻辑没法测）；
2. **下限抬升**：dev 计算时传入 main 的当前声明作 floor，结果低于 floor 就以 floor
   为基数重新递增——即使 back-merge PR 被漏合，也不会再发出倒退版本。

用法（CI 的 calc_version step 调用，也可本地跑）::

    python scripts/next_version.py --current 0.8.4-beta --type patch --release beta --floor 0.9.0
    # -> 0.9.1-beta（候选 0.8.5-beta 低于 floor，抬到 main 线续算）

语义保持（与历史 bash 逐一对应，不改发布节奏）：
- dev：patch +1 且带 ``-beta``；main：minor +1、patch 归零、无后缀。
- 候选 >= floor 时保持候选（正常节奏下 dev 永远领先 main，floor 不介入）。
"""

from __future__ import annotations

import argparse
import sys

VersionLike = tuple[int, int, int]


def parse_release(version: str) -> VersionLike:
    """取 ``X.Y.Z`` 数字段，忽略 ``-beta`` 等预发布后缀."""
    core = version.split("-", 1)[0]
    parts = core.split(".")
    if len(parts) != 3:
        raise ValueError(f"版本号必须是 X.Y.Z[-suffix] 形态，收到 {version!r}")
    return int(parts[0]), int(parts[1]), int(parts[2])


def bump(current: str, version_type: str, release_type: str) -> str:
    """按分支语义递增一次版本号（不含下限逻辑）."""
    major, minor, patch = parse_release(current)
    if version_type == "minor":
        minor += 1
        patch = 0
        new = f"{major}.{minor}.{patch}"
    elif version_type == "patch":
        patch += 1
        new = f"{major}.{minor}.{patch}"
        if release_type == "beta":
            new += "-beta"
    else:
        raise ValueError(f"version_type 只能是 patch/minor，收到 {version_type!r}")
    return new


def less(left: str, right: str) -> bool:
    """按数字段比较两个版本号的先后（后缀不参与——与本仓递增语义一致）."""
    return parse_release(left) < parse_release(right)


def next_version(
    current: str, version_type: str, release_type: str, floor: str | None = None
) -> str:
    """算下一个版本；给定 floor 且候选低于 floor 时，以 floor 为基数重新递增.

    floor 取 main 分支的当前声明。候选等于或高于 floor 时保持候选：正常节奏下
    dev 声明始终领先 main 一个 beta，下限不介入；只有分叉（dev 落在 main 之后）
    才抬升，抬升结果沿 main 线续算。
    """
    candidate = bump(current, version_type, release_type)
    if floor is not None and less(candidate, floor):
        return bump(floor, version_type, release_type)
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__ or "")
    parser.add_argument("--current", required=True, help="本分支当前声明的版本号")
    parser.add_argument("--type", dest="version_type", required=True, choices=("patch", "minor"))
    parser.add_argument("--release", required=True, choices=("beta", "stable"))
    parser.add_argument("--floor", default=None, help="下限版本（main 当前声明）；不传则不校验")
    args = parser.parse_args(argv)
    print(next_version(args.current, args.version_type, args.release, args.floor))
    return 0


if __name__ == "__main__":
    sys.exit(main())
