"""贡献者入口的机械校验（变更 ``contributor-ramp``，issue #123）.

为什么存在：本变更把 542 行的 ``CONTRIBUTING.md`` 拆成"一页纸入口 + 完整维护者规范"，
并新增可上手任务清单与贡献者名单。这类改动最可能以**静默退化**的方式失败 —— 入口又长回去、
免流程那段被挪到读者看不到的位置、"搬丢"某个章节、响应天数在某处悄悄多出第二个数 ——
而这些都不会让任何既有测试变红。所以这里把验收口径写成 CI 能拦住的断言，做法与
``test_doc_consistency`` / ``test_governance_consistency`` / ``test_agent_discoverability``
一致：**一份手写真源 + 机械测试**。

覆盖 ``contributor-experience`` 规格的全部 15 个 Scenario：入口行数 / 五类内容 / 链向完整规范 /
免流程声明的位置 / 门槛的分类表述 / PR 模板"不适用" / 章节零丢失 / 分支模型一致 /
站点指南改指针 / 清单条目要素 / 阻塞标注分组 / 名单收录方式 / 响应承诺同源 /
流程资产不移动 / 建议标注未生效。

**口径（消歧）**：入口的"≤100 行"按**文件总计**理解，中英两半各 ≤60 行 —— 若按"每半 100 行"
理解等于没减负（design D9 与规格的 Scenario 都取前者）。

**两套双语锚点约定**（本变更同时落在两侧，混用会造出死链）：仓库根的中英双语文件
（``CONTRIBUTING.md`` / ``CONTRIBUTORS.md`` / ``MAINTAINERS.md``…）靠 ``<a name="english"></a>``
这类 HTML 锚点，语言导航行写 ``[English](#english) | [中文](#中文)``；``docs/`` 内的双语页
（``CONTRIBUTING_MAINTAINER.md``…）靠 attr_list 的 ``{#en}`` / ``{#zh}``，导航行写 ``(#en)``/``(#zh)``。
GitHub 不解析 attr_list，根级文件里写 ``{#en}`` 会被当标题正文渲染，``[English](#en)`` 反而点不动。

**刻意不做的一件事**：``good first issue`` 标签只存在于 GitHub 侧，本文件不伪造"标签已打"的断言
（离线 CI 证明不了它，那样的断言是空断言）。实测结果记在 ``design.md`` D7 与
``docs/GOOD_FIRST_ISSUES.md`` 的快照说明里。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"

ENTRY = REPO_ROOT / "CONTRIBUTING.md"
MAINTAINER_SPEC = DOCS / "CONTRIBUTING_MAINTAINER.md"
POINTER_PAGE = DOCS / "contributing" / "contributing.md"
GOOD_FIRST = DOCS / "GOOD_FIRST_ISSUES.md"
BACKLOG = DOCS / "contributing" / "maintainer-backlog.md"
CONTRIBUTORS = REPO_ROOT / "CONTRIBUTORS.md"
MAINTAINERS = REPO_ROOT / "MAINTAINERS.md"
PR_TEMPLATE = REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
MKDOCS_YML = REPO_ROOT / "mkdocs.yml"
PYPROJECT = REPO_ROOT / "pyproject.toml"

ENTRY_MAX_LINES = 100
HALF_MAX_LINES = 60
FREE_PASS_WINDOW = 20  # 免流程声明的可见窗口（行）

# 两种双语写法（位置决定用哪一套，见模块 docstring）
ROOT_HEADINGS = {"en": "## 🇬🇧 English", "zh": "## 🇨🇳 中文"}
ROOT_NAV = "[English](#english) | [中文](#中文)"
SPEC_HEADINGS = {"en": "## 🇬🇧 English {#en}", "zh": "## 🇨🇳 中文 {#zh}"}

# 语言无关的"免流程声明"：必须由一个否定式动词 + OpenSpec 提案构成，
# 允许加粗、允许换一种说法（`need **no**` / `do not need` / `不需要`）。
FREE_PASS = {
    "en": r"(?:need(?:s|ed)?\s+\*{0,2}no\*{0,2}|do(?:es)?\s+not\s+need|without)"
    r"\s+(?:an?\s+)?OpenSpec\s+proposal",
    "zh": r"(?:不需要|无需|不用)\*{0,2}\s*OpenSpec\s*提案",
}

# "一律必须走流程"式的绝对表述。用词边界而不是裸子串——"Small changes" 里就含
# "all changes"，裸匹配会假红。
_ABSOLUTE_FLOW_PATTERNS = (
    r"一律",
    r"(?:所有|全部|一切)(?:的)?改动.{0,8}(?:必须|都|均)",
    r"(?:改动|变更)(?:一律|一概).{0,8}(?:必须|要走|需)",
    r"\ball changes\b[^.]{0,60}\b(?:must|shall|require)",
    r"\bevery change\b[^.]{0,60}\b(?:must|shall|require)",
    r"\bany change\b[^.]{0,60}\b(?:must|shall|require)",
    r"\bno change\b[^.]{0,40}\bwithout\b",
)

# 与免流程通道配套的分类表述：需要提案的那一类改动，必须被如此命名（中英各一种写法）
_CATEGORICAL_SCOPE = ("externally observable", "外部可观察行为")

# 入口每一半必须齐备的五类内容，每类给出**可执行的具体做法**（命令 / 链接 / 模板）
_FIVE_CLASSES = {
    "en": {
        "建环境": (r"pip install -e", r"uv sync"),
        "跑测试": (r"\bpytest\b",),
        "提 PR": (r"PULL_REQUEST_TEMPLATE\.md", r"git checkout"),
        "免流程": (FREE_PASS["en"],),
        "提问": (r"github\.com/YearsAlso/zoo-framework/issues", r"7 days"),
    },
    "zh": {
        "建环境": (r"pip install -e", r"uv sync"),
        "跑测试": (r"\bpytest\b",),
        "提 PR": (r"PULL_REQUEST_TEMPLATE\.md", r"git checkout"),
        "免流程": (FREE_PASS["zh"],),
        "提问": (r"github\.com/YearsAlso/zoo-framework/issues", r"7 天内"),
    },
}

# 搬移前的 12 个英文 / 12 个中文三级标题（防"搬丢了"的手写真源）。
# 这是逐段保留的证据：删掉任何一个章节，下面的断言即红。
ORIGINAL_SECTIONS = {
    "en": (
        "Before you write code",
        "Development setup",
        "Branch strategy",
        "Commit messages",
        "Quality gates",
        "Tests",
        "Spec-driven changes",
        "Documentation contributions",
        "Pull requests",
        "Good first issues",
        "Reporting bugs and proposing features",
        "Code of Conduct",
    ),
    "zh": (
        "动手写代码之前",
        "开发环境搭建",
        "分支规范",
        "提交信息规范",
        "质量门禁",
        "测试规范",
        "规范先行的改动（OpenSpec）",
        "文档贡献",
        "PR 流程",
        "Good First Issue",
        "报告 Bug 与提出需求",
        "行为准则",
    ),
}

# 本变更新增的两个小节（流程资产说明 / 门禁放宽建议），按语言各一份
NEW_SECTIONS = {
    "en": (
        "Gates we are considering adjusting (nothing here is in effect)",
        "Process assets: why they stay where they are",
    ),
    "zh": (
        "建议调整的门禁（尚未生效）",
        "流程资产：为什么留在原处",
    ),
}

_LINK_RE = re.compile(r"\]\(([^)]+)\)")
_ISSUE_LINK_RE = re.compile(r"https://github\.com/YearsAlso/zoo-framework/issues/(\d+)")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _lines(path: Path) -> list[str]:
    return _read(path).splitlines()


def _links(text: str) -> list[str]:
    return [m.group(1).strip() for m in _LINK_RE.finditer(text)]


def _links_outside_docs(text: str, base: Path) -> list[str]:
    """返回 ``base`` 所在页面里跨出 ``docs_dir`` 的相对链接.

    ``docs/`` 下的相对路径是**相对站点**解析的；指向 docs 之外的文件时站点上不存在，
    非 strict ``mkdocs build`` 会给一条链接告警（见 mkdocs.yml 末尾注释）。跨出去的
    必须写绝对 GitHub URL。``base`` 是该页面所在目录。
    """
    offenders: list[str] = []
    for target in _links(text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path = target.split("#", 1)[0]
        if not path:
            continue
        if DOCS not in (base / path).resolve().parents:
            offenders.append(target)
    return offenders


def _section(text: str, heading: str) -> str:
    """取某个三级标题到下一个三级标题之间的内容.

    ``"\\n### "`` 不会匹配 ``"\\n#### "``（第四个字符是 ``#`` 不是空格），
    因此四级标题不会截断小节。
    """
    start = text.find(heading)
    assert start != -1, f"找不到小节标题 {heading!r}——文档结构变了，请同步本断言"
    body = text[start + len(heading) :]
    end = body.find("\n### ")
    return body if end == -1 else body[:end]


def _half(lang: str, headings: dict[str, str] | None = None, path: Path = ENTRY) -> list[str]:
    """取某个双语文件的一"半"（含语言标题行，到下一个二级标题或文件末为止）."""
    headings = headings or ROOT_HEADINGS
    lines = _lines(path)
    heading = headings[lang]
    starts = [i for i, line in enumerate(lines) if line.strip() == heading]
    assert len(starts) == 1, (
        f"{path.name} 里 {heading!r} 出现 {len(starts)} 次（应为 1 次）——请检查双语结构"
    )
    start = starts[0]
    rest = lines[start + 1 :]
    end = next((i for i, line in enumerate(rest) if line.startswith("## ")), len(rest))
    return lines[start : start + 1 + end]


def _h2_section(text: str, prefix: str) -> str:
    """取某个二级标题到下一个二级标题之间的内容（清单页的分组用的是二级标题）."""
    chunk = next(
        (part for part in re.split(r"^## ", text, flags=re.MULTILINE) if part.startswith(prefix)),
        None,
    )
    assert chunk is not None, f"找不到二级小节 {prefix!r}——文档结构变了，请同步本断言"
    return "## " + chunk


def _table_rows(text: str) -> list[list[str]]:
    """取出 markdown 表格的所有数据行（表头与分隔行被过滤掉）."""
    rows: list[list[str]] = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or set(cells[0]) <= {"-", ":", " "}:
            continue
        rows.append(cells)
    return rows


# ================================================================
# 1. 入口规模、结构与五类内容（规格 Scenario：入口行数 / 五类内容齐备 / 链向完整规范）
# ================================================================


def test_entry_is_a_one_page_document() -> None:
    """① 根 ``CONTRIBUTING.md`` 总计 ≤100 行，中英两半各 ≤60 行.

    牙齿：在入口任意位置加一行让总数变 101 即红；把某半撑到 61 行即红
    ——"一页纸"是规格里的硬数字，不是形容词。
    """
    total = len(_lines(ENTRY))
    assert total <= ENTRY_MAX_LINES, (
        f"根 CONTRIBUTING.md 共 {total} 行，超过上限 {ENTRY_MAX_LINES} 行"
        "——入口是给「只想提一个小改动」的人看的；多出来的内容应进 docs/CONTRIBUTING_MAINTAINER.md"
    )
    for lang in ROOT_HEADINGS:
        half = _half(lang)
        assert len(half) <= HALF_MAX_LINES, (
            f"入口的 {lang} 半共 {len(half)} 行，超过单半上限 {HALF_MAX_LINES} 行"
        )


def test_entry_language_switch_uses_the_root_anchor_convention() -> None:
    """根级文件的语言导航行必须与 ``<a name=…>`` 锚点同形，且不得使用 ``{#…}``.

    牙齿：把导航行改回 ``[English](#en) | [中文](#zh)`` 即红（GitHub 上点不动）；
    给标题加 ``{#en}`` 也即红（GitHub 不解析 attr_list，会把 ``{#en}`` 当标题正文渲染）。
    """
    text = _read(ENTRY)
    assert ROOT_NAV in text, f"根 CONTRIBUTING.md 的语言导航行不是 {ROOT_NAV!r}"
    anchors = {target for target in _links(text) if target.startswith("#")}
    assert "#english" in anchors and "#中文" in anchors, (
        f"语言导航的锚点必须与 <a name=…> 同形，实际锚点：{sorted(anchors)}"
    )
    assert '<a name="english"></a>' in text and '<a name="中文"></a>' in text, (
        "缺少 <a name=…></a> 锚点——GitHub 上这两个语言链接会点不动"
    )
    braces = [line for line in text.splitlines() if line.startswith("## ") and "{" in line]
    assert not braces, f"根级文件的标题不得写 attr_list 的 {{#…}}：{braces}"


def _pyproject_floor() -> str:
    match = re.search(r'requires-python\s*=\s*"([^"]+)"', _read(PYPROJECT))
    assert match, "pyproject.toml 里找不到 requires-python"
    floor = re.search(r">=\s*(\d+\.\d+)", match.group(1))
    assert floor, f"无法解析 requires-python：{match.group(1)!r}"
    return floor.group(1)


def _class_failures(lang: str) -> list[str]:
    """列出该半缺失的五类内容（按语言取证据，避免一半靠另一半蒙混过关）."""
    half = "\n".join(_half(lang))
    return [
        label
        for label, patterns in _FIVE_CLASSES[lang].items()
        if not all(re.search(p, half, re.IGNORECASE) for p in patterns)
    ]


def test_entry_half_covers_the_five_content_classes_en() -> None:
    """② 英文半必须齐备五类内容，且每类给出可执行的具体做法.

    牙齿：删掉任何一条命令 / 链接（例如把 ``pip install -e ".[dev]"`` 去掉）即红。
    """
    missing = _class_failures("en")
    assert not missing, f"入口英文半缺少这些内容：{missing}"


def test_entry_half_covers_the_five_content_classes_zh() -> None:
    """② 中文半必须齐备五类内容（与英文半各自独立核验）.

    牙齿：只给英文半补内容、中文半漏掉某一类即红。
    """
    missing = _class_failures("zh")
    assert not missing, f"入口中文半缺少这些内容：{missing}"


def test_entry_python_floor_matches_pyproject() -> None:
    """入口声称的 Python 门槛必须与 pyproject 一致（与 development.md 同一做法）.

    牙齿：pyproject 升到 3.14 而入口仍写 3.13 即红。
    """
    floor = _pyproject_floor()
    for lang in ROOT_HEADINGS:
        assert floor in "\n".join(_half(lang)), (
            f"入口的 {lang} 半未写明 Python 门槛 {floor}（pyproject 要求 {floor}）"
        )


def test_every_half_points_at_the_complete_spec() -> None:
    """③ 每半都含指向完整维护者规范的链接，且目标文件真实存在（规格 Scenario）.

    牙齿：删掉任一半的维护者规范链接即红；把目标文件改名而不改链接即红。
    """
    assert MAINTAINER_SPEC.is_file(), f"完整维护者规范不存在：{MAINTAINER_SPEC}"
    for lang in ROOT_HEADINGS:
        half = "\n".join(_half(lang))
        assert "docs/CONTRIBUTING_MAINTAINER.md" in half, (
            f"入口的 {lang} 半没有指向 docs/CONTRIBUTING_MAINTAINER.md 的链接"
        )


# ================================================================
# 2. 免流程通道与门槛表述（规格 Scenario：免流程声明位置 / 门槛不矛盾 / PR 模板）
# ================================================================


def test_free_pass_notice_is_within_the_first_screen_en() -> None:
    """④ 免流程声明必须落在英文半的前 20 行内（读者不必翻过语言切换）。

    牙齿：把那段引用块挪到文件末尾即红；删掉「need **no** OpenSpec proposal」这句即红。
    """
    window = "\n".join(_half("en")[:FREE_PASS_WINDOW])
    assert re.search(FREE_PASS["en"], window), (
        f'英文半的前 {FREE_PASS_WINDOW} 行里没有免流程声明（"…need no OpenSpec proposal…"）'
    )


def test_free_pass_notice_is_within_the_first_screen_zh() -> None:
    """④ 免流程声明必须落在中文半的前 20 行内.

    牙齿：把中文半那段引用块删掉即红。
    """
    window = "\n".join(_half("zh")[:FREE_PASS_WINDOW])
    assert re.search(FREE_PASS["zh"], window), (
        f'中文半的前 {FREE_PASS_WINDOW} 行里没有免流程声明（"…不需要 OpenSpec 提案…"）'
    )


def test_no_absolute_open_flow_wording() -> None:
    """⑤ 入口与完整规范都不得出现"一律必须走流程"式的绝对表述.

    牙齿：在任一文件里写回「所有改动都必须走 OpenSpec 提案」即红。
    """
    bad = []
    for path in (ENTRY, MAINTAINER_SPEC):
        for line_no, line in enumerate(_lines(path), 1):
            for pattern in _ABSOLUTE_FLOW_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    bad.append(f"    {path.relative_to(REPO_ROOT)}:{line_no}: {line.strip()[:70]}")
                    break
    assert not bad, "出现了与免流程通道矛盾的绝对表述：\n" + "\n".join(bad)


def test_categorical_scope_is_named_in_both_files() -> None:
    """⑤ 免流程的反面（需要提案的那一类）必须被点名为"外部可观察行为、兼容性或数据格式".

    只写"重要改动要写提案"不够——门槛必须是可判断的分类。中英两半都要有。

    牙齿：删掉入口或完整规范里的"外部可观察行为"这一句即红。
    """
    for path in (ENTRY, MAINTAINER_SPEC):
        text = _read(path)
        missing = [term for term in _CATEGORICAL_SCOPE if term not in text]
        assert not missing, (
            f"{path.relative_to(REPO_ROOT)} 未写明需要提案的改动范围（缺少这些分类表述：{missing}）"
        )


def test_pr_template_allows_not_applicable() -> None:
    """⑤ PR 模板的 OpenSpec 条目必须允许标注"不适用"，而不是只能勾"已提交".

    牙齿：删掉那条"不适用"即红——只剩"已提交"时，改错别字的人会被迫勾一个假选项。
    """
    template = _read(PR_TEMPLATE)
    openspec_entries = [
        line
        for line in template.splitlines()
        if "openspec/" in line and line.strip().startswith("- [")
    ]
    assert openspec_entries, "PR 模板里找不到 openspec/ 相关的勾选项——结构变了，请同步本断言"
    assert any("不适用" in line for line in openspec_entries), (
        f"PR 模板的 openspec/ 勾选项里没有「不适用」这一允许项：{openspec_entries}"
    )


# ================================================================
# 3. 完整规范的零丢失与链接卫生（规格 Scenario：原规范章节无丢失 / 分支模型一致）
# ================================================================


def test_maintainer_spec_keeps_every_section_heading() -> None:
    """⑥ 搬移前的 12 个英文 + 12 个中文三级标题必须全部可定位，另含本变更新增的 2 节.

    这是"内容零丢失"的机械证据：搬移时漏掉任何一节即红。

    牙齿：从 docs/CONTRIBUTING_MAINTAINER.md 删掉任一 ``### …`` 章节标题即红。
    """
    text = _read(MAINTAINER_SPEC)
    missing = [
        f"### {title}"
        for lang in ORIGINAL_SECTIONS
        for title in ORIGINAL_SECTIONS[lang]
        if f"### {title}" not in text
    ]
    assert not missing, f"完整维护者规范丢掉了这些章节：{missing}"

    missing_new = [
        f"### {title}"
        for lang in NEW_SECTIONS
        for title in NEW_SECTIONS[lang]
        if f"### {title}" not in text
    ]
    assert not missing_new, f"完整维护者规范缺少本变更新增的小节：{missing_new}"


def test_maintainer_spec_uses_ascii_anchors_only() -> None:
    """⑦ 完整规范里不得有中文锚点链接，且语言标题必须带 ``{#en}`` / ``{#zh}``.

    ``docs/`` 内的页面由 mkdocs 渲染，而 mkdocs 的 slugify 会把中文剥成空锚点
    （同 tests/test_doc_consistency.py::test_no_cjk_anchor_links 的理由）。

    牙齿：把 ``{#zh}`` 改回 ``#中文``（写成 ``[中文](#中文)``）即红。
    """
    text = _read(MAINTAINER_SPEC)
    cjk = re.compile(r"[㐀-鿿]")
    bad = [
        target
        for target in _links(text)
        if "#" in target and not target.startswith("http") and cjk.search(target.split("#", 1)[1])
    ]
    assert not bad, f"完整规范里有指向中文锚点的链接（站点上点不动）：{bad}"

    for lang in SPEC_HEADINGS:
        assert SPEC_HEADINGS[lang] in text, (
            f"完整规范缺少语言标题 {SPEC_HEADINGS[lang]!r}——锚点缺失会让语言导航失效"
        )


def test_maintainer_spec_relative_links_stay_inside_docs() -> None:
    """⑦ 完整规范里的相对链接必须落在 docs/ 内；跨出 docs_dir 的必须写绝对 URL.

    理由（mkdocs.yml 末尾注释）：``docs/`` 下按仓库相对路径写、又指向 docs 之外的文件，
    在站点上不存在，构建会给链接告警；写绝对的 GitHub URL 才是既有做法。

    牙齿：把 ``](BRANCHING.md)`` 改成 ``](../CONTRIBUTING.md)`` 即红——那恰好会把
    文档站唯一的死链复制一份（该死链是 GFI-2 的交付物，见 docs/GOOD_FIRST_ISSUES.md）。
    """
    offenders = _links_outside_docs(_read(MAINTAINER_SPEC), MAINTAINER_SPEC.parent)
    assert not offenders, (
        f"完整规范里有跨出 docs/ 的相对链接（站点上会 404）：{offenders}\n"
        "修法：改写为 https://github.com/YearsAlso/zoo-framework/blob/dev/<path>"
    )


def test_changed_docs_pages_never_link_outside_the_site() -> None:
    """⑦′ 本变更改过的**每一个**站点页面都不得有跨出 docs_dir 的相对链接.

    上一条只守完整规范一篇；本变更新增的 ``docs/GOOD_FIRST_ISSUES.md`` 一度正是踩了这个坑——
    它写了 ``](../CONTRIBUTING.md)``，站点上不存在，把文档站唯一的死链复制成了两条。
    ``docs/BRANCHING.md`` 的那条是 GFI-2 的交付物（本变更**不碰**），故这里不纳入扫描。

    牙齿：把 ``docs/GOOD_FIRST_ISSUES.md`` 里那行绝对 URL 改回 ``](../CONTRIBUTING.md)``
    即红——这正是开发期真实发生过的一次回归。
    """
    pages = (
        MAINTAINER_SPEC,
        GOOD_FIRST,
        POINTER_PAGE,
        BACKLOG,
        DOCS / "contributing" / "README.md",
    )
    offenders: list[str] = []
    for page in pages:
        for target in _links_outside_docs(_read(page), page.parent):
            offenders.append(f"{page.relative_to(REPO_ROOT).as_posix()}: {target}")
    assert not offenders, (
        f"这些站点页面有跨出 docs/ 的相对链接（站点上会 404 并产生构建告警）：{offenders}\n"
        "修法：改写为 https://github.com/YearsAlso/zoo-framework/blob/dev/<path>"
    )


def test_branch_model_is_dev_first() -> None:
    """⑧ 贡献者文档里不得有"从 main 分支创建功能分支"式的表述，且入口必须点明 PR 目标为 dev.

    牙齿：把入口的「open the PR **into `dev`**」改成 main 即红；把旧指南里那句
    "从 main 分支创建功能分支"搬回来即红。
    """
    forbidden = ("从 main 分支创建", "create a feature branch from main", "branch off main")
    for path in (ENTRY, MAINTAINER_SPEC, POINTER_PAGE):
        text = _read(path)
        hits = [phrase for phrase in forbidden if phrase in text]
        assert not hits, f"{path.relative_to(REPO_ROOT)} 含与双分支模型矛盾的表述：{hits}"

    for lang, pattern in (
        ("en", r"into\s+\*{0,2}`?dev`?\*{0,2}"),
        ("zh", r"指向\s*\*{0,2}`?dev`?\*{0,2}"),
    ):
        half = "\n".join(_half(lang))
        assert re.search(pattern, half, re.IGNORECASE), (
            f"入口的 {lang} 半没有点明 PR 目标是 dev 分支"
        )


# ================================================================
# 4. 重叠文档收敛与门禁建议（规格 Scenario：站点指南改指针 / 建议标注未生效）
# ================================================================


def test_pointer_page_points_at_the_single_authority() -> None:
    """⑨ docs/contributing/contributing.md 必须指向完整规范，且不再复述流程.

    牙齿：删掉它指向 ``../CONTRIBUTING_MAINTAINER.md`` 的链接即红；把"从 main 分支创建
    功能分支"搬回来即红（该串也被上一条断言守着）。
    """
    text = _read(POINTER_PAGE)
    assert "../CONTRIBUTING_MAINTAINER.md" in text, (
        "站点指南没有指向完整维护者规范——它必须在这一点上指向唯一权威"
    )
    assert "从 main 分支创建" not in text


def test_backlog_cross_links_the_gate_suggestion_section() -> None:
    """⑮ 维护者待办台账必须交叉引用"建议放宽的门禁"小节，且锚点真实存在.

    台账页不复制正文（它自己的口径是"issue tracker 是唯一真源"），所以这一行只做指针。

    牙齿：删掉台账里那一行即红；把维护者规范里的 ``{#gate-suggestions-zh}`` 改名即红。
    """
    targets = [t for t in _links(_read(BACKLOG)) if t.startswith("../CONTRIBUTING_MAINTAINER.md#")]
    assert targets, "待办台账里没有指向完整规范小节的交叉引用"
    for target in targets:
        fragment = target.split("#", 1)[1]
        assert f"{{#{fragment}}}" in _read(MAINTAINER_SPEC), (
            f"台账指向的锚点 #{fragment} 在完整规范里不存在——链接会点不动"
        )


def test_gate_suggestions_are_marked_as_not_in_effect() -> None:
    """⑮ 放宽门禁的内容必须标注为"建议、尚未生效"，并明说没有改动任何门禁.

    牙齿：把「尚未生效」/「nothing here is in effect」从标题里去掉即红；
    删掉"不改任何门禁"这一句即红——没有它，读者会以为门禁已经放宽。
    """
    text = _read(MAINTAINER_SPEC)
    assert "Gates we are considering adjusting (nothing here is in effect)" in text
    assert "建议调整的门禁（尚未生效）" in text
    assert "No gate is changed" in text
    assert "不改任何门禁" in text


# ================================================================
# 5. 可上手任务清单（规格 Scenario：清单条目要素齐备 / 阻塞项显式标注）
# ================================================================

_TASK_COLUMNS = ("编号", "任务", "文件路径", "量级", "验收标准", "使用者可见的结果")


def _task_rows() -> list[list[str]]:
    """清单里"任务行"= 首格是 issue 链接的表格行."""
    return [row for row in _table_rows(_read(GOOD_FIRST)) if _ISSUE_LINK_RE.search(row[0])]


def _blocker_rows() -> list[list[str]]:
    """阻塞行 = 首格是纯 ``#NNN``、第二格是 issue 链接的表格行."""
    rows = []
    for row in _table_rows(_read(GOOD_FIRST)):
        if len(row) >= 2 and re.fullmatch(r"#\d+", row[0]) and _ISSUE_LINK_RE.search(row[1]):
            rows.append(row)
    return rows


def test_good_first_issues_lists_five_tasks_with_every_required_column() -> None:
    """⑩ 清单必须有 5 条任务，每条都带 issue 编号、文件路径、量级与两项验收信息.

    牙齿：删掉任一列（例如「量级」）即红；某行少写一格即红；把条目数改成 4 条即红。
    """
    text = _read(GOOD_FIRST)
    header = next(
        (line for line in text.splitlines() if "文件路径" in line and line.startswith("|")), None
    )
    assert header, "清单里找不到任务表的表头——结构变了，请同步本断言"
    missing_columns = [column for column in _TASK_COLUMNS if column not in header]
    assert not missing_columns, f"清单表头缺少列：{missing_columns}"

    rows = _task_rows()
    assert len(rows) == 5, f"清单应有 5 条任务，实际 {len(rows)} 条"

    problems = []
    for row in rows:
        number = _ISSUE_LINK_RE.search(row[0]).group(1)
        if len(row) != len(_TASK_COLUMNS):
            problems.append(f"#{number}: 列数 {len(row)}，应为 {len(_TASK_COLUMNS)}")
            continue
        _, _, files, size, criteria, visible = row
        if not re.search(r"\.(?:py|md|toml)\b", files):
            problems.append(f"#{number}: 「文件路径」列没有具体文件（{files!r}）")
        if "分钟" not in size:
            problems.append(f"#{number}: 「量级」列没有耗时量级（{size!r}）")
        if len(criteria) < 20 or len(visible) < 20:
            problems.append(f"#{number}: 「验收标准」或「使用者可见的结果」为空泛描述")
    assert not problems, "清单条目要素不齐：\n" + "\n".join(f"    {p}" for p in problems)

    numbers = {_ISSUE_LINK_RE.search(row[0]).group(1) for row in rows}
    assert len(numbers) == 5, f"清单里的 issue 编号有重复：{sorted(numbers)}"


def test_good_first_issues_separates_immediate_from_blocked() -> None:
    """⑩ 清单必须区分"可立即开始"与"暂不可开始"两组，且每条阻塞项都点名阻塞来源.

    牙齿：把三条阻塞任务并在"可以立即开始"表里即红；删掉阻塞来源表即红。
    """
    text = _read(GOOD_FIRST)
    immediate = _h2_section(text, "可以立即开始")
    blocked = _h2_section(text, "暂不可开始")
    assert "2" in immediate.splitlines()[0], (
        f"「可立即开始」小节的标题未标注条数：{immediate.splitlines()[0]!r}"
    )
    assert "3" in blocked.splitlines()[0], (
        f"「暂不可开始」小节的标题未标注条数：{blocked.splitlines()[0]!r}"
    )

    def _numbers(section: str) -> set[str]:
        return {
            _ISSUE_LINK_RE.search(row[0]).group(1)
            for row in _table_rows(section)
            if _ISSUE_LINK_RE.search(row[0])
        }

    immediate_numbers = _numbers(immediate)
    blocked_numbers = _numbers(blocked)
    assert len(immediate_numbers) == 2, f"「可立即开始」应有 2 条，实际 {sorted(immediate_numbers)}"
    assert len(blocked_numbers) == 3, f"「暂不可开始」应有 3 条，实际 {sorted(blocked_numbers)}"
    assert not (immediate_numbers & blocked_numbers), "两组任务出现了重复编号"

    blockers = _blocker_rows()
    assert len(blockers) == 3, f"阻塞来源表应有 3 行，实际 {len(blockers)} 行"
    named = {row[0].lstrip("#") for row in blockers}
    assert named == blocked_numbers, (
        f"阻塞来源表覆盖的条目与「暂不可开始」列表不一致：表里 {sorted(named)}，"
        f"列表 {sorted(blocked_numbers)}"
    )
    for row in blockers:
        assert _ISSUE_LINK_RE.search(row[1]), f"阻塞行没有点名阻塞来源 issue：{row}"


def test_good_first_issues_records_the_rejected_candidates() -> None:
    """⑩ 被实测否掉的候选方向必须留在清单里（省掉重复讨论），且给出实测理由.

    牙齿：删掉这一节即红。
    """
    text = _read(GOOD_FIRST)
    assert "曾经考虑过" in text, "清单缺少「被实测否掉」的候选方向一节"
    rejected = text.split("曾经考虑过", 1)[1]
    for keyword in ("README", "错误信息"):
        assert keyword in rejected, f"被否掉的候选缺少 {keyword!r} 这一条"


# ================================================================
# 6. 贡献者名单与响应承诺（规格 Scenario：名单收录方式 / 响应承诺同源）
# ================================================================


def test_contributors_file_explains_how_to_get_listed() -> None:
    """⑪ 仓库根必须有一份贡献者名单，写明收录方式、欢迎新贡献者，并把"使用者"分流出去.

    牙齿：删掉"名单在一个 PR 被合入时添加"这句即红；删掉 ADOPTERS.md 的链接即红
    （否则"谁在用"与"谁在写"会混成一份无法核实的名单）。

    刻意**不**断言"表里只有维护者"：第一位真实贡献者被写进来时，那条断言会变成假红。
    规格里的"不声称未经核实的第三方"属于评审判断，不是机械可判定的属性。
    """
    assert CONTRIBUTORS.is_file(), "仓库根缺少 CONTRIBUTORS.md（规格：贡献者收益可见）"
    text = _read(CONTRIBUTORS)
    assert re.search(r"when a pull request\s+is merged", text), (
        "贡献者名单没有写明收录方式（英文半：按合入的 PR 收录）"
    )
    assert re.search(r"一个\s*PR\s*被合入时", text), (
        "贡献者名单没有写明收录方式（中文半：按合入的 PR 收录）"
    )
    assert "could be the next row" in text and "下一行可以是你" in text, (
        "贡献者名单没有欢迎新贡献者的表述"
    )
    assert "ADOPTERS.md" in text, "贡献者名单没有把「使用者」分流到 ADOPTERS.md"
    assert len(_table_rows(text)) >= 2, "贡献者名单里没有任何一行名单"


def _authority_first_reply_days() -> tuple[str, str]:
    """从 MAINTAINERS.md 的 issue/PR 行取出首次回应天数（中英各一处）——承诺的唯一权威."""
    en_row = next(line for line in _lines(MAINTAINERS) if "Issue or pull request" in line)
    zh_row = next(line for line in _lines(MAINTAINERS) if "issue 或 PR" in line)
    en = re.search(r"(\d+)\s*days?", en_row)
    zh = re.search(r"(\d+)\s*天", zh_row)
    assert en and zh, f"MAINTAINERS.md 的首次回应行里找不到天数：{en_row!r} / {zh_row!r}"
    return en.group(1), zh.group(1)


def test_readmes_share_one_authority_for_response_times() -> None:
    """⑫ 两份 README 的社区段都必须指向 MAINTAINERS.md，天数与它一致，且无低自信表述.

    唯一真源是 MAINTAINERS.md：这里把它那行的天数读出来与 README 比对，
    所以"改一处、另一处没跟上"以及"引入第二组天数"都会红。

    牙齿：从 README 删掉 MAINTAINERS.md 链接即红；把 7 天改成 3 天即红；
    写回「尽力而为地回复」式的低自信表述即红。
    """
    en_days, zh_days = _authority_first_reply_days()
    sections = {"README.md": "### Community & Feedback", "README.zh.md": "### 社区与反馈"}
    for name, heading in sections.items():
        section = _section(_read(REPO_ROOT / name), heading)
        assert "MAINTAINERS.md" in section, f"{name} 的社区段没有把 MAINTAINERS.md 作为权威来源"
        assert "CONTRIBUTORS.md" in section, f"{name} 的社区段没有链到贡献者名单"
        assert re.search(r"\bbest[- ]effort\b|尽力而为", section, re.IGNORECASE) is None, (
            f"{name} 的社区段出现了低自信表述——规格要求给出可预期的承诺"
        )

    assert re.search(rf"\b{en_days} days?\b", _read(REPO_ROOT / "README.md")), (
        f"README.md 未给出与 MAINTAINERS.md 一致的 {en_days} 天承诺"
    )
    assert f"{zh_days} 天" in _read(REPO_ROOT / "README.zh.md"), (
        f"README.zh.md 未给出与 MAINTAINERS.md 一致的 {zh_days} 天承诺"
    )

    conflicts = {
        name: sorted(set(re.findall(r"\b(\d+) days?\b", _read(REPO_ROOT / name))) - {en_days})
        for name in ("README.md",)
    }
    conflicts["README.zh.md"] = sorted(
        set(re.findall(r"(\d+) 天", _read(REPO_ROOT / "README.zh.md"))) - {zh_days}
    )
    assert not {k: v for k, v in conflicts.items() if v}, (
        f"README 里出现了与 MAINTAINERS.md 不一致的天数：{conflicts}"
    )


# ================================================================
# 7. 流程资产与文档站接入（规格 Scenario：流程资产位置不变）
# ================================================================


def test_process_assets_are_still_where_discovery_looks_for_them() -> None:
    """⑬ .claude/ 的五个约定目录与 openspec 归档目录必须留在原处，且规范里写明理由.

    移动它们是**静默**破坏：agent / 命令 / skill / 规则按约定从仓库根发现，
    而 openspec 的归档路径由 CLI 自己拼（不可配置）。所以这里既查目录在不在，
    也查规范里那两条机制理由有没有被写下来。

    牙齿：把 ``.claude/skills`` 改名即红；删掉规范里含 ``settings.json`` 的那行即红。
    """
    for name in ("agents", "commands", "rules", "skills", "workflows"):
        assert (REPO_ROOT / ".claude" / name).is_dir(), (
            f".claude/{name}/ 不在约定位置——按约定发现的机制会静默失效"
        )
    assert (REPO_ROOT / "openspec" / "changes" / "archive").is_dir(), (
        "openspec/changes/archive/ 不在 CLI 自己拼出的路径上——archive/validate/list 会看不到既有归档"
    )

    text = _read(MAINTAINER_SPEC)
    for token in (".claude/", "openspec/changes/archive/", "settings.json", "<root>"):
        assert token in text, f"完整规范未说明流程资产为何不能移动（缺少 {token!r}）"


def test_mkdocs_nav_lists_the_new_contributor_pages() -> None:
    """⑬ 两个新页面必须进 nav，且指针页的既有 nav 项保持不动（D5：保留已发布 URL）.

    牙齿：从 mkdocs.yml 的 nav 删掉 GOOD_FIRST_ISSUES.md 即红——页面会建出来但没人看得到。
    """
    nav = _read(MKDOCS_YML).split("nav:", 1)[1].split("\nplugins:", 1)[0]
    for page in ("CONTRIBUTING_MAINTAINER.md", "GOOD_FIRST_ISSUES.md"):
        assert page in nav, f"mkdocs nav 缺少 {page}（页面存在但没有入口）"
    assert "contributing/contributing.md" in nav, (
        "mkdocs nav 丢掉了「贡献指南」指针页——那是个已发布的 URL，改指别处会 404"
    )


# ================================================================
# 8. 防"空跑"自检（任务 7.3）
#
# 上面的断言分两类：**肯定式**（"必须找到 X"）失效时会因为找不到 X 而变红；
# **否定式**（"不得出现 X"）与**切片式**（"取前 20 行"）失效时会**恒真**——
# 正则写错、切片越界都会让它们永远通过。所以这里用合成样本给它们做体检：
# 每条否定式规则必须能匹配一个已知的违规样本，且不能误伤一个合法样本。
# ================================================================


def test_negative_patterns_are_not_dead() -> None:
    """否定式规则必须能匹配已知违规样本，且不误伤合法样本.

    牙齿：把 ``_ABSOLUTE_FLOW_PATTERNS`` 改成一个永不匹配的正则即红——
    那样上面那条"不得出现绝对表述"的断言会变成永远通过的空断言。
    """
    violating = (
        "所有的改动都必须先写 OpenSpec 提案。",
        "一切改动均须先开提案。",
        "All changes must go through OpenSpec before landing.",
    )
    unanswered = [
        sample
        for sample in violating
        if not any(re.search(p, sample, re.IGNORECASE) for p in _ABSOLUTE_FLOW_PATTERNS)
    ]
    assert not unanswered, (
        f"绝对表述的规则匹配不到已知违规样本，那条断言已经变成空断言：{unanswered}"
    )
    legitimate = "Small changes do not need paperwork."
    assert not any(re.search(p, legitimate, re.IGNORECASE) for p in _ABSOLUTE_FLOW_PATTERNS), (
        f"绝对表述的规则误伤了合法样本（词边界写错，例如裸匹配 all changes）：{legitimate!r}"
    )

    cjk = re.compile(r"[㐀-鿿]")
    assert cjk.search("中文"), "中文锚点检测匹配不到已知违规样本（如 #中文）"
    assert not cjk.search("en") and not cjk.search("zh"), "中文锚点检测误伤了 ASCII 锚点"


def test_free_pass_patterns_are_not_dead() -> None:
    """免流程规则必须能匹配两种真实写法，且不会把"需要提案"的句子当成免流程声明.

    牙齿：把规则写成"含 OpenSpec 提案 即命中"即红——那样一句"需要 OpenSpec 提案"
    会被误判成免流程通道。
    """
    positives = {
        "en": "Spelling fixes need **no** OpenSpec proposal and no prior issue.",
        "zh": "拼写类的修正**不需要** OpenSpec 提案、也不需要先开 issue。",
    }
    for lang, sample in positives.items():
        assert re.search(FREE_PASS[lang], sample), (
            f"{lang} 的免流程规则匹配不到真实写法：{sample!r}"
        )

    negatives = {
        "en": "Every behaviour change needs an OpenSpec proposal first.",
        "zh": "凡涉及行为的改动都需要 OpenSpec 提案。",
    }
    for lang, sample in negatives.items():
        assert not re.search(FREE_PASS[lang], sample), (
            f"{lang} 的免流程规则把「需要提案」的句子误判成免流程声明：{sample!r}"
        )


def test_table_and_section_helpers_are_not_dead() -> None:
    """切片式助手必须真的取到内容；找不到标题时必须报错，而不是静默返回空串；
    "跨出 docs/" 的链接检测必须能命中违规样本、且不误伤合法链接.

    牙齿：把 ``_table_rows`` 的过滤条件改坏（返回空列表）即红——那样"5 条任务"
    会被解析成 0 条，报错信息却指向内容而不是解析器。
    """
    sample = "| 编号 | 任务 |\n|---|---|\n| [#1](https://x/1) | 甲 |\n"
    rows = _table_rows(sample)
    assert rows == [["编号", "任务"], ["[#1](https://x/1)", "甲"]], f"表格解析器取错了行：{rows}"

    text = _read(GOOD_FIRST)
    immediate = _h2_section(text, "可以立即开始")
    assert "编号" in immediate and _ISSUE_LINK_RE.search(immediate), (
        f"二级小节切片没有取到表格内容：{immediate[:60]!r}"
    )
    assert "pytest" in _section(_read(ENTRY), "### 1. Set up and run the tests"), (
        "三级小节切片没有取到内容"
    )

    assert _links_outside_docs("见 [入口](../CONTRIBUTING.md)。", DOCS) == ["../CONTRIBUTING.md"], (
        "跨出 docs/ 的链接检测查不出已知违规样本（docs/GOOD_FIRST_ISSUES.md 里那行就是这样）"
    )
    assert not _links_outside_docs(
        "[维护者规范](CONTRIBUTING_MAINTAINER.md) | [台账](contributing/maintainer-backlog.md)",
        DOCS,
    ), "跨出 docs/ 的链接检测误伤了 docs/ 内的相对链接"
    assert not _links_outside_docs(
        "[台账](../CONTRIBUTING_MAINTAINER.md)", DOCS / "contributing"
    ), "跨出 docs/ 的链接检测误伤了 docs/ 子目录里指向 docs/ 内的 ../ 链接"
    assert not _links_outside_docs(
        "[分支策略](https://github.com/YearsAlso/zoo-framework/blob/dev/docs/BRANCHING.md)", DOCS
    ), "跨出 docs/ 的链接检测误伤了绝对 URL"

    with pytest.raises(AssertionError):
        _h2_section(text, "这个二级小节不存在")
    with pytest.raises(AssertionError):
        _section(text, "### 这个三级小节不存在")
    with pytest.raises(AssertionError):
        _half("en", headings={"en": "## 不存在的语言标题"})
