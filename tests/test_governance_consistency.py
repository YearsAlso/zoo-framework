"""治理材料一致性机械校验.

为什么存在：``governance-files`` 变更（issue #120）的验收项里有四条是**可机械判定**的
—— ``security.txt`` 字段齐备、``Expires`` 未过期、报送渠道与 ``SECURITY.md`` 一致、
治理文件的引用不悬空。写在人读清单里的验收项会漂移，这里把它们变成 CI 能拦住的断言。

同时守住"机制不退化"：``.well-known/security.txt`` 的可达性靠 mkdocs 构建钩子
（mkdocs 会忽略点开头的目录，所以 ``docs/.well-known/`` 那份副本根本发布不出去），
**钩子、``mkdocs.yml`` 的声明、工作流触发路径**三者少任何一个，security.txt 都会在
站点上静默消失——下面各有一条用例。

对应 ``openspec/changes/governance-files/specs/project-governance/spec.md`` 与
``.../ci-and-packaging/spec.md``。
"""

from __future__ import annotations

import importlib.util
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]
WELL_KNOWN = REPO_ROOT / ".well-known"
SECURITY_TXT = WELL_KNOWN / "security.txt"
SECURITY_MD = REPO_ROOT / "SECURITY.md"
GOVERNANCE_MD = REPO_ROOT / "GOVERNANCE.md"
MAINTAINERS_MD = REPO_ROOT / "MAINTAINERS.md"
ADOPTERS_MD = REPO_ROOT / "ADOPTERS.md"
COC_MD = REPO_ROOT / "CODE_OF_CONDUCT.md"
MKDOCS_YML = REPO_ROOT / "mkdocs.yml"
DOCS_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "docs.yml"
HOOK_SCRIPT = REPO_ROOT / "scripts" / "mkdocs_hooks.py"

# security.txt 的必需字段（RFC 9116 第 2 节）
REQUIRED_FIELDS = ("Contact", "Expires", "Canonical", "Policy", "Preferred-Languages")

# README 两份文件里治理小节的标题，以及该小节必须链到的全部入口
GOVERNANCE_SECTION_HEADINGS = {"README.md": "### Governance", "README.zh.md": "### 治理与规范"}
GOVERNANCE_ENTRIES = (
    "GOVERNANCE.md",
    "MAINTAINERS.md",
    "ADOPTERS.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    ".well-known/security.txt",
)

# 本项目**不具备**的治理机构：出现即说明模板文字回潮。允许出现在否定句里
# （如实写"没有委员会"正是本变更要求的诚实写法），故只拦"未经否定的"出现。
FORBIDDEN_GOVERNANCE_TERMS = (
    "技术委员会",
    "委员会",
    "章程",
    "选举",
    "投票",
    "steering committee",
    "committee",
    "charter",
    "election",
    "voting",
    "TSC",
)
NEGATION_MARKERS = ("没有", "无", "不存在", "不是", "而不是", "no ", "not ", "never", "without")

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_URL_RE = re.compile(r"https?://[^\s)>\]，。]+")
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_FIELD_RE = re.compile(r"^([A-Za-z-]+):\s*(.+)$")


# ---------------------------------------------------------------- 工具


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _security_txt_fields() -> dict[str, list[str]]:
    """把 security.txt 解析成 ``字段 -> 值列表``（注释与空行跳过）."""
    fields: dict[str, list[str]] = {}
    for line in _read(SECURITY_TXT).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = _FIELD_RE.match(line)
        if match:
            fields.setdefault(match.group(1), []).append(match.group(2).strip())
    return fields


def _section(path: Path, heading: str) -> str:
    """取 markdown 中某个三级标题到下一个三级标题之间的内容."""
    text = _read(path)
    start = text.find(heading)
    assert start != -1, f"{path.name} 里找不到小节标题 {heading!r}"
    body = text[start + len(heading) :]
    end = body.find("\n### ")
    return body if end == -1 else body[:end]


def _relative_links(markdown: str) -> set[str]:
    """取出 markdown 里的相对链接目标（排除锚点与站外 URL）."""
    targets = set()
    for target in _MD_LINK_RE.findall(markdown):
        if target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        targets.add(target.split("#", 1)[0])
    return {t for t in targets if t}


def _maintainer_rows() -> list[str]:
    """解析 MAINTAINERS.md 的第一张表（维护者表）的数据行."""
    lines = _read(MAINTAINERS_MD).splitlines()
    rows: list[str] = []
    in_table = False
    for line in lines:
        if line.startswith("|"):
            if set(line) <= set("|-: "):  # 分隔行
                continue
            if "Maintainer |" in line or "维护者 |" in line:
                in_table = True
                continue
            if in_table:
                rows.append(line)
        elif in_table:
            break
    return rows


def _load_hook_module() -> ModuleType:
    """按路径加载构建钩子（scripts/ 不是包，从测试里只能这样导入）.

    刻意不让测试依赖 mkdocs：本仓库的 dev extra 不含 mkdocs，CI 的测试作业也没装它，
    而钩子本身只用标准库。
    """
    spec = importlib.util.spec_from_file_location("mkdocs_hooks_under_test", HOOK_SCRIPT)
    assert spec and spec.loader, f"无法加载 {HOOK_SCRIPT}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------- security.txt


def test_security_txt_has_required_fields() -> None:
    """五个必需字段都要有值（RFC 9116）."""
    fields = _security_txt_fields()
    missing = [name for name in REQUIRED_FIELDS if not fields.get(name)]
    assert not missing, f"security.txt 缺少必需字段：{missing}"


def test_security_txt_expires_in_the_future_within_a_year() -> None:
    """``Expires`` 必须是未来日期，且不超过一年——过期即失败，不允许静默过期."""
    raw = _security_txt_fields()["Expires"][0]
    expires = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    assert expires.tzinfo is not None, f"Expires 必须带时区：{raw}"
    now = datetime.now(UTC)
    assert expires > now, f"security.txt 已过期：Expires={raw}，当前 {now.isoformat()}"
    assert expires - now <= timedelta(days=366), f"Expires 超过一年（RFC 9116 建议上限）：{raw}"


def test_security_txt_channels_match_security_md() -> None:
    """``Contact`` 的每条渠道都要能在 SECURITY.md 的**两个语种**里找到.

    SECURITY.md 是中英双份，两份都必须列出报送渠道；只查"整份文件里出现过"会漏掉
    单侧漂移（改了一个语种、另一个还是旧邮箱）。
    """
    fields = _security_txt_fields()
    policy = _read(SECURITY_MD)
    halves = policy.split('<a name="中文"></a>')
    assert len(halves) == 2, f"{SECURITY_MD.name} 的中英双语结构变了，请更新本断言"
    channels = fields["Contact"]
    assert channels, "Contact 为空"
    for channel in channels:
        targets = _EMAIL_RE.findall(channel) or _URL_RE.findall(channel)
        assert targets, f"Contact 项无法识别为邮箱或 URL：{channel}"
        for target in targets:
            missing_in = [i for i, half in enumerate(halves, start=1) if target not in half]
            assert not missing_in, (
                f"security.txt 的 Contact 渠道 {target!r} 不在 SECURITY.md 的第 "
                f"{missing_in} 个语种段落中——两处渠道必须一致（改动一处的报送渠道时"
                "同步另一处）"
            )


def test_security_txt_policy_points_to_repo_security_md() -> None:
    """``Policy`` 必须指向本仓的 SECURITY.md."""
    policy = _security_txt_fields()["Policy"][0]
    assert policy.startswith("https://github.com/YearsAlso/zoo-framework/"), policy
    assert policy.endswith("/SECURITY.md"), policy


# ---------------------------------------------------------------- 治理文件内容


def test_governance_declares_no_invented_institutions() -> None:
    """本项目没有委员会/章程/选举：这些词只能出现在否定句里，且必须至少出现一次."""
    lines = _read(GOVERNANCE_MD).splitlines()
    affirmed = [
        line
        for line in lines
        if any(term in line for term in FORBIDDEN_GOVERNANCE_TERMS)
        and not any(marker in line for marker in NEGATION_MARKERS)
    ]
    assert not affirmed, f"GOVERNANCE.md 出现了未加否定的机构描述：{affirmed}"
    negated = [
        line
        for line in lines
        if any(term in line for term in FORBIDDEN_GOVERNANCE_TERMS)
        and any(marker in line for marker in NEGATION_MARKERS)
    ]
    assert negated, "GOVERNANCE.md 没有写明本项目不存在委员会/章程等机构"


def test_governance_maintainer_count_matches_maintainers_md() -> None:
    """GOVERNANCE.md 的维护者人数声明必须与 MAINTAINERS.md 的名单一致."""
    rows = _maintainer_rows()
    assert rows, "MAINTAINERS.md 里没解析到维护者表"
    text = _read(GOVERNANCE_MD)
    if len(rows) == 1:
        assert "One person" in text and "一个人" in text, (
            "MAINTAINERS.md 只有 1 位维护者，GOVERNANCE.md 必须如实写明（中英两处都要）"
        )
    else:
        assert "One person" not in text and "一个人" not in text, (
            f"MAINTAINERS.md 已列出 {len(rows)} 位维护者，GOVERNANCE.md 仍写着单人维护"
        )


def test_adopters_rows_are_labelled() -> None:
    """ADOPTERS.md 的每条使用者都必须标注可核实与否；标为可核实的要给出可查依据."""
    section = _section(ADOPTERS_MD, "### Known users") + _section(ADOPTERS_MD, "### 已知使用者")
    rows = [line for line in section.splitlines() if line.startswith("|")]
    data_rows = [line for line in rows if not set(line) <= set("|-: ")]
    assert data_rows, "ADOPTERS.md 的使用者表没有数据行"
    for row in data_rows:
        if "项目或组织" in row or "Project or organisation" in row:
            continue
        has_label = "可核实" in row or "verifiable" in row.lower()
        assert has_label, f"使用者条目未标注可核实与否：{row}"
        if "✅" in row:
            assert "http" in row, f"标为可核实却没有可查依据：{row}"


# ---------------------------------------------------------------- 引用可达性


def test_readme_pair_links_the_same_governance_entries() -> None:
    """两份 README 的治理小节必须链到同一组入口，且至少覆盖全部七个."""
    seen: dict[str, set[str]] = {}
    for name, heading in GOVERNANCE_SECTION_HEADINGS.items():
        targets = _relative_links(_section(REPO_ROOT / name, heading))
        missing = [entry for entry in GOVERNANCE_ENTRIES if entry not in targets]
        assert not missing, f"{name} 的治理小节缺少入口：{missing}"
        seen[name] = targets
    first, second = seen.values()
    assert first == second, (
        f"两份 README 的治理小节链接不一致："
        f"仅英文有 {sorted(first - second)}，仅中文有 {sorted(second - first)}"
    )


def test_governance_file_links_resolve() -> None:
    """治理文件之间的相对链接必须指向存在的文件（含 README 的治理小节）."""
    sources = [GOVERNANCE_MD, MAINTAINERS_MD, ADOPTERS_MD, COC_MD]
    broken: list[str] = []
    for path in sources:
        for target in _relative_links(_read(path)):
            if not (REPO_ROOT / target).exists():
                broken.append(f"{path.name} -> {target}")
    assert not broken, f"失效链接：{broken}"


def test_faq_adopters_reference_resolves() -> None:
    """docs/FAQ.md 早就引用了 ADOPTERS.md，本变更让这条引用不再悬空."""
    faq = _read(REPO_ROOT / "docs" / "FAQ.md")
    assert "ADOPTERS.md" in faq, "FAQ 不再引用 ADOPTERS.md，请检查该断言是否仍必要"
    assert ADOPTERS_MD.exists()


# ---------------------------------------------------------------- 可达性机制


def test_security_txt_has_a_single_hand_written_source() -> None:
    """docs/ 下不得有副本：mkdocs 忽略点开头的目录，那份副本既不可达又会导致漂移."""
    assert not (REPO_ROOT / "docs" / ".well-known").exists(), (
        "docs/.well-known/ 会被 mkdocs 忽略（发布不出去）且与真源重复，请删除"
    )


def test_mkdocs_declares_the_publishing_hook() -> None:
    """mkdocs.yml 必须声明构建钩子——否则站点产物里不会有 .well-known/."""
    config = _read(MKDOCS_YML)
    assert re.search(r"^hooks:", config, re.MULTILINE), "mkdocs.yml 缺少 hooks 声明"
    assert "scripts/mkdocs_hooks.py" in config, "mkdocs.yml 未指向构建钩子脚本"


def test_docs_workflow_triggers_on_security_txt() -> None:
    """触发路径必须覆盖 .well-known/**，否则续期 Expires 不会重新发布站点."""
    workflow = _read(DOCS_WORKFLOW)
    assert "'.well-known/**'" in workflow, (
        "docs.yml 的 on.push.paths 缺少 '.well-known/**'：只改 security.txt 时不会重新部署"
    )


def test_hook_publishes_security_txt_into_site_dir(tmp_path: Path) -> None:
    """钩子把真源复制进产物目录，且逐字节一致."""
    hooks = _load_hook_module()
    site_dir = tmp_path / "site"
    written = hooks.publish_well_known(
        {"config_file_path": str(MKDOCS_YML), "site_dir": str(site_dir)}
    )
    published = site_dir / ".well-known" / "security.txt"
    assert published in written
    assert published.read_bytes() == SECURITY_TXT.read_bytes()


def test_hook_fails_when_source_is_missing(tmp_path: Path) -> None:
    """真源缺失时必须报错——静默产出"没有 security.txt 的站点"比不产出更糟."""
    hooks = _load_hook_module()
    with pytest.raises(FileNotFoundError):
        hooks.publish_well_known(
            {
                "config_file_path": str(tmp_path / "mkdocs.yml"),
                "site_dir": str(tmp_path / "site"),
            }
        )
