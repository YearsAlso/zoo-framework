#!/usr/bin/env python3
"""从 ``CHANGELOG.md`` 抽取指定版本的条目段，供 release 正文生成.

用法::

    python scripts/notes_from_changelog.py 0.10.6-beta
    python scripts/notes_from_changelog.py v0.10.6-beta   # ``v`` 前缀被剥掉

行为约定（变更 changelog-backfill / #117 的 spec）：

* 找到 ``## [<版本>]`` 标题后，输出从该标题到下一个 ``## `` 标题（或文件同级结构
  结束）之间的全部内容，**原样**输出到 stdout（不含标题行以外的加工）；
* 找不到对应版本段时**非零退出**（stderr 给出原因）——刻意不静默输出空文本，
  让维护者先补 CHANGELOG，而不是让 release 正文悄悄变成"未整理"的提交列表；
* 只读 CHANGELOG.md，不做任何写入；不做网络访问。

这是 ``release.yml`` "Generate Changelog" 步骤的生成器；它的失败必须可见。
"""

from __future__ import annotations

import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"


def extract(version: str) -> str:
    """抽取 ``CHANGELOG.md`` 中 ``## [<version>]`` 段的正文（不含标题行）.

    Args:
        version: 版本号，允许带 ``v`` 前缀。

    Returns:
        该段的全部行（含末尾空行修剪）。找不到时抛 ``SystemExit``。

    Raises:
        SystemExit: CHANGELOG 缺失或版本段不存在（exit 1，信息进 stderr）。
    """
    version = version.removeprefix("v")
    try:
        lines = CHANGELOG.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        print(f"cannot read {CHANGELOG}: {e}", file=sys.stderr)
        raise SystemExit(1) from e

    header = f"## [{version}]"
    start = None
    for i, line in enumerate(lines):
        if line.startswith(header):
            # `## [0.9.1-beta]` 不应误匹配 `## [0.9.1-beta2]` 之类的更长版本名：
            # 要求标题行在 `]` 后只能跟日期后缀（" - YYYY-MM-DD"）或直接结束
            rest = line[len(header) :].strip()
            if rest == "" or rest.startswith("- "):
                start = i
            break
    if start is None:
        print(
            f"CHANGELOG.md 中没有 `## [{version}]` 段 —— 请先补写该版本的条目"
            f"（见 docs/RELEASE_PROCESS.md 的操作顺序），再重新发布。",
            file=sys.stderr,
        )
        raise SystemExit(1)

    out: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        out.append(line)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out)


def main(argv: list[str]) -> None:
    """CLI 入口.

    Args:
        argv: 命令行参数（不含脚本名），恰需一个版本号。
    """
    if len(argv) != 1:
        print("usage: notes_from_changelog.py <version>", file=sys.stderr)
        raise SystemExit(2)
    section = extract(argv[0])
    print(section)


if __name__ == "__main__":
    main(sys.argv[1:])
