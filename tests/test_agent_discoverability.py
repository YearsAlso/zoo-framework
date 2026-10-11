"""AI 检索发现层一致性机械校验.

为什么存在：变更 ``agent-discoverability``（issue #122）新增了三处面向检索的入口——
仓库根 ``llms.txt``、仓库根 ``AGENTS.md``、两份 README 的 FAQ——它们描述的是**同一批
事实**（支持什么、不支持什么、怎么接入、去哪看细节）。这类"同一事实写在三处"的材料
最容易静默漂移，而写在人读清单里的验收项不会拦住它——所以这里把契约变成 CI 能拦住的
断言（与 ``test_doc_consistency`` / ``test_governance_consistency`` 同一做法）。

四组断言，各自的牙齿：

1. ``llms.txt`` 的结构与**准确性**——未实现的能力不得被写成可用（真源取 README 的
   特性表/对比表，不在这里再抄一份能力清单）；
2. ``llms.txt`` 的绝对 URL 必须落在**实测可达白名单**内——凭直觉写站点子页即红
   （白名单见下方 ``ALLOWED_URLS``，复核方式在文件头注释里）；
3. ``AGENTS.md`` 引用的报错文本必须与 ``zoo_framework`` 源码**实际 raise 的文本**一致
   ——代码改文案而文档没跟上即红；
4. 两份 README 的 FAQ 与 ``docs/FAQ.md`` 的**主题覆盖**与**不支持口径**一致——比对的是
   主题集合与结论，不是逐字译文（中英两份是各自本地化，逐字比对必然失败）。

链接可达性**刻意不做联网断言**：三平台 CI 上的联网断言只会带来假红。需要联网核对时用
``llms.txt`` 里的 URL 逐个 ``curl -s -o /dev/null -w "%{http_code}" -L`` 复跑。
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
LLMS_TXT = REPO_ROOT / "llms.txt"
AGENTS_MD = REPO_ROOT / "AGENTS.md"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
DOCS_FAQ = REPO_ROOT / "docs" / "FAQ.md"
DOCS_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "docs.yml"
HOOK_SCRIPT = REPO_ROOT / "scripts" / "mkdocs_hooks.py"
MKDOCS_YML = REPO_ROOT / "mkdocs.yml"

# 两份 README 的 FAQ 小节标题（各自本地化，故分别列出——与 test_governance_consistency
# 对治理小节的处理同一做法）
README_FAQ_SECTIONS = {"README.md": "### FAQ", "README.zh.md": "### 常见问题"}

# docs/FAQ.md 的 dev 分支绝对链接：README 的每条短答都要给出它（读者要细节有去处）
DOCS_FAQ_URL = "https://github.com/YearsAlso/zoo-framework/blob/dev/docs/FAQ.md"

# ---------------------------------------------------------------- 1. llms.txt 结构与准确性

# llms.txt 的绝对 URL 白名单 = 2026-10-10 逐个 curl 实测 200 的四项。
# 站点子页（/api/、/install/、/FAQ/）当天**全部 404**——docs.yml 只由 main 触发，而本
# 变更在 perfect/docs 上；凭直觉写站点子页会立刻被下面的断言拦住。
# 复核方式：对 ALLOWED_URLS 里每一项重跑 curl（见文件头 docstring）。
ALLOWED_URLS = {
    "https://yearsalso.github.io/zoo-framework/",
    "https://yearsalso.github.io/zoo-framework/benchmark/",
    "https://github.com/YearsAlso/zoo-framework/blob/dev/docs/api/README.md",
    "https://github.com/YearsAlso/zoo-framework/blob/dev/CHANGELOG.md",
}

# llms.txt 必须能定位到的六类内容（对应 ai-discoverability 规格的六类）
_LLMS_SECTIONS = (
    "## What this is",
    "## When to use it",
    "## When not to use it",
    "## Core concepts",
    "## Minimal runnable example",
    "## Links",
)

# 「不要用」清单必须明写的三条替代
_LLMS_SUBSTITUTES = {
    "跨机器 → Celery": (r"\bCelery\b",),
    "cron → APScheduler": (r"APScheduler",),
    "多进程 → 本框架未实现": (r"\b[Mm]ulti-process\b",),
}

# 最小可运行示例必须与 example/minimal.py 的事实一致（同一批事实，不得各写一套）
_MINIMAL_EXAMPLE_FACTS = ("class MyWorker(BaseWorker)", '"is_loop": True', '"delay_time": 1.0')

_URL_RE = re.compile(r"https?://[^\s)\]}>,;\"']+")

# 否定语境标记：英文（llms.txt / README.md）与中文（README.zh.md）各一套。
# 只用于「未实现的能力不得被写成可用」这一类断言。
_NEGATION_RE = re.compile(
    r"\b(?:not|no|never|cannot|can't|unsupported|declines?|without|instead|out of scope)\b"
    r"|不支持|未实现|不能|无法|不会|没有",
    re.IGNORECASE,
)


# ---------------------------------------------------------------- 共用：issue #122 点名的 10 个问题主题

# 主题 -> 关键词集合（多语种写法并列）。断言的是**主题命中**而不是逐字译文：中英两份
# README 各自本地化、docs/FAQ.md 是中文，逐字比对必然失败且无意义。
TOPICS: dict[str, tuple[str, ...]] = {
    "不装 broker 能否跑定时任务": ("redis", "rabbitmq", "broker"),
    "与 Celery 的区别与选型": ("celery",),
    "与 APScheduler 的区别": ("apscheduler",),
    "多进程与跨机器": ("multi-process", "multiple processes", "多进程"),
    "cron 表达式": ("cron",),
    "任务卡住是否被强杀": ("run_timeout", "killed", "卡住", "强杀"),
    "重启后状态是否恢复": ("restart", "state machine", "重启", "状态机"),
    "为什么叫 Zoo 与名字对应": ("zoo", "metaphor", "隐喻"),
    "与 AI Agent 的关系": ("ai agent", "agent"),
    "生产环境使用情况": ("production", "生产环境"),
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _lines(path: Path) -> list[str]:
    return _read(path).splitlines()


def _section(text: str, heading: str) -> str:
    """取 markdown 中某个三级标题到下一个三级标题之间的内容.

    ``"\\n### "`` 不会匹配 ``"\\n#### "``（第四个字符是 ``#`` 不是空格），
    因此四级标题（FAQ 的问句）不会截断小节。
    """
    start = text.find(heading)
    assert start != -1, f"找不到小节标题 {heading!r}"
    body = text[start + len(heading) :]
    end = body.find("\n### ")
    return body if end == -1 else body[:end]


def _absolute_urls(text: str) -> set[str]:
    """取出文本里的绝对 URL（去掉句末标点与多余的右括号）."""
    return {m.group(0).rstrip(".,;:") for m in _URL_RE.finditer(text)}


def test_llms_txt_exists_with_expected_shape() -> None:
    """仓库根 llms.txt 必须是 H1 + 引用式摘要 + 分节标题列表.

    牙齿：删掉 H1 或引用式摘要即红——这两项是 llms.txt 约定本身的形状，
    没有它们的文件不会被按 llms.txt 消费。
    """
    assert LLMS_TXT.is_file(), "仓库根缺少 llms.txt（issue #122 第 2 条）"
    lines = _lines(LLMS_TXT)
    assert lines[0].startswith("# "), f"llms.txt 首行必须是 H1，实际是：{lines[0]!r}"

    first_section = next((i for i, line in enumerate(lines) if line.startswith("## ")), None)
    assert first_section, "llms.txt 没有分节标题（## …）"
    summary = [line for line in lines[1:first_section] if line.startswith(">")]
    assert summary, "llms.txt 的 H1 之后必须有引用式摘要（'>' 开头的一行）"


def test_llms_txt_covers_the_six_content_classes() -> None:
    """六类内容齐备：这是什么 / 什么时候用 / 什么时候不要用 / 核心概念 / 最小示例 / 外部链接.

    牙齿：删掉任一节标题即红；把「不要用」清单里的三条替代任一删掉即红。
    """
    text = _read(LLMS_TXT)
    missing = [section for section in _LLMS_SECTIONS if section not in text]
    assert not missing, f"llms.txt 缺少这些节：{missing}"

    for label, patterns in _LLMS_SUBSTITUTES.items():
        assert any(re.search(p, text) for p in patterns), (
            f"llms.txt 的「不要用」清单缺少替代：{label}"
        )

    for fact in _MINIMAL_EXAMPLE_FACTS:
        assert fact in text, f"llms.txt 的最小示例与 example/minimal.py 不一致：找不到 {fact!r}"


def test_llms_txt_declares_the_metaphor_is_naming_only() -> None:
    """隐喻只影响命名、不影响语义——必须显式写出来，否则检索方会把名字当语义.

    牙齿：删掉该声明即红（这是 ais-discoverability 规格里明写的一条要求）。
    """
    text = _read(LLMS_TXT)
    assert re.search(r"metaphor\b", text, re.IGNORECASE), "llms.txt 未提及隐喻"
    assert re.search(r"only affects naming", text, re.IGNORECASE), (
        "llms.txt 必须显式声明「隐喻只影响命名、不影响语义」"
    )


def test_llms_txt_links_are_within_the_measured_allowlist() -> None:
    """llms.txt 里的绝对 URL 必须落在实测可达白名单内，且四类链接齐备.

    牙齿：把文档站链接改成站点子页（如 ``.../zoo-framework/api/``）即红——那些 URL
    2026-10-10 实测 404，写进去就是死链。
    """
    found = _absolute_urls(_read(LLMS_TXT))
    offenders = sorted(found - ALLOWED_URLS)
    assert not offenders, (
        f"llms.txt 出现了白名单之外的 URL：{offenders}\n"
        "白名单只收实测可达的链接；新增前先 curl 实测，并把结果记进 tests 的白名单与 design 的表。"
    )
    assert found >= ALLOWED_URLS, f"llms.txt 缺少这些链接：{sorted(ALLOWED_URLS - found)}"


# ---------------------------------------------------------------- 2. 未实现的能力不得被写成可用

# 话题 -> (README.md 中宣称行的前缀正则, 关键词正则组, FAQ 是否必须提到该话题)
# 真源是 README：这里只断言"README 说它不行"与"文档也按不行表述"，不另抄能力清单。
# 关键词按语种给出多个写法（中英两份 FAQ 各自本地化），与前一张主题表**共用同一个来源**，
# 避免同一话题的关键词在两处各写一套而漂移。``required_in_faq`` 为 False 的话题只要求
# "提到就必须是否定"，不要求 FAQ 必须覆盖它（健康监控不在 issue #122 的问题清单里）。
_NOT_IMPLEMENTED_TOPICS = (
    ("多进程", r"^\| \*\*Multi-process execution\*\*", TOPICS["多进程与跨机器"], True),
    ("cron 表达式", r"^\| Cron expressions", TOPICS["cron 表达式"], True),
    ("健康监控", r"^\| Health monitoring", ("health monitoring", "健康监控"), False),
)

# markdown 的"块"起点：标题 / 列表项 / 引用块。折行不是语义单位，所以否定语境的判定
# 必须以块为单位——列表项或段落折成两行时，否定词落在第二行是正常的。
_UNIT_START_RE = re.compile(r"^(?:#{1,6}\s|[-*+]\s|\d+\.\s|>)")


def _truth_row(pattern: str) -> str:
    """从 README.md 取出话题对应的宣称行（不存在即说明文档结构变了）."""
    for line in _lines(REPO_ROOT / "README.md"):
        if re.search(pattern, line):
            return line
    pytest.fail(f"README.md 里找不到宣称行 {pattern!r}——特性表结构变了，请更新本断言")


def _units(text: str) -> list[str]:
    """把 markdown 切成"块"：标题、列表项（含其折行）、段落各为一块."""
    units: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            if current:
                units.append("\n".join(current))
                current = []
            continue
        if _UNIT_START_RE.match(line) and current:
            units.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        units.append("\n".join(current))
    return units


def _units_mentioning(text: str, keywords: tuple[str, ...]) -> list[str]:
    """列出提到该话题的块（标题块排除：问句天然不含否定词，那不是能力宣称）."""
    return [
        unit
        for unit in _units(text)
        if not unit.lstrip().startswith("#")
        and any(re.search(k, unit, re.IGNORECASE) for k in keywords)
    ]


# 行内代码（`` `…` ``）里引用的**报错原文**不算叙述：报错串经常自带 "not implemented"
# 之类字样，若不剔除，一句"该模式可用，请求会被 `… not implemented …` 拒绝"就能骗过否定
# 检查。因此判定否定语境前先剥掉行内代码。
_CODE_SPAN_RE = re.compile(r"`[^`]*`")


def _prose(text: str) -> str:
    """剥掉行内代码（含报错原文）后的叙述文本."""
    return _CODE_SPAN_RE.sub("", text)


@pytest.mark.parametrize(
    "topic,row_pattern,keywords,_required", _NOT_IMPLEMENTED_TOPICS, ids=lambda v: str(v)[:18]
)
def test_llms_txt_states_unimplemented_capabilities_negatively(
    topic: str, row_pattern: str, keywords: tuple[str, ...], _required: bool
) -> None:
    """未实现的能力在 llms.txt 里必须被提到，且处于否定语境.

    牙齿：把 llms.txt 的多进程描述改成可用（去掉 not implemented）即红；反过来，
    README 把该行从 ❌ 改成 ✅ 而 llms.txt 没跟上也即红。
    """
    row = _truth_row(row_pattern)
    assert "❌" in row or "⚠️" in row, (
        f"README.md 已不再把「{topic}」标为未实现/未接通：{row.strip()}\n"
        "若能力已经实现，请同步 llms.txt / AGENTS.md / FAQ 与 design 的表述。"
    )

    hits = _units_mentioning(_read(LLMS_TXT), keywords)
    assert hits, f"llms.txt 没有提到「{topic}」——README 标为未实现的能力必须在此如实说明"
    bad = [unit.strip() for unit in hits if not _NEGATION_RE.search(_prose(unit))]
    assert not bad, f"llms.txt 把「{topic}」写得像可用了（叙述里是否定缺失）：{bad}"


@pytest.mark.parametrize(
    "topic,row_pattern,keywords,required", _NOT_IMPLEMENTED_TOPICS, ids=lambda v: str(v)[:18]
)
def test_readme_faq_states_unimplemented_capabilities_negatively(
    topic: str, row_pattern: str, keywords: tuple[str, ...], required: bool
) -> None:
    """README FAQ 里**该话题自己那组问答**的结论必须与特性表一致（中英两份都查）.

    与 llms.txt 的判定口径不同：llms.txt 是紧凑索引，凡提到未实现能力都必须是否定；
    FAQ 是散文，一句对比句里出现别的工具支持 cron 是正常表述，因此这里只要求
    「命中该话题关键词的那组问答，其答案是否定语境」。

    牙齿：把英文 FAQ 的「Multi-process execution is not implemented」改成可用即红；
    从 FAQ 删掉多进程那条（该话题必须覆盖）也即红。
    """
    row = _truth_row(row_pattern)
    assert "❌" in row or "⚠️" in row, f"README.md 已不再把「{topic}」标为未实现：{row.strip()}"

    for name, heading in README_FAQ_SECTIONS.items():
        faq = _section(_read(REPO_ROOT / name), heading)
        matches = [
            body
            for question, body in _faq_qa_pairs(faq)
            if any(re.search(k, question, re.IGNORECASE) for k in keywords)
        ]
        if not matches:
            assert not required, f"{name} 的 FAQ 没有提到「{topic}」（该话题必须出现在 FAQ 里）"
            continue
        bad = [body.strip() for body in matches if not _NEGATION_RE.search(_prose(body))]
        assert not bad, f"{name} 的 FAQ 把「{topic}」写得像可用了：{bad}"


# ---------------------------------------------------------------- 3. AGENTS.md 的报错文本与源码一致

# AGENTS.md 必须包含的接入说明四类内容（对应 ai-discoverability 规格）
_AGENTS_SECTIONS = (
    "## Install and version floor",
    "## A Worker must be registered as a **class**",
    "## Configuration is separate from implementation",
    "## Failures are explicit, never silently downgraded",
    "## Verify your change",
)

# (源码文件, 该文件里实际 raise 的文本片段)。文档引用的必须是**源码里的这两段字面量**，
# 因此代码改文案而文档没跟上、或文档改错一个字符，都会红。
_SOURCE_RAISE_LITERALS = (
    ("zoo_framework/core/worker_registry.py", "Must inherit from BaseWorker: "),
    (
        "zoo_framework/core/worker_registry.py",
        "requires constructor arguments and cannot be lazily instantiated;"
        "use register_instance or register_factory instead",
    ),
    ("zoo_framework/core/waiter/base_waiter.py", "unknown run policy "),
    ("zoo_framework/core/waiter/base_waiter.py", "is not implemented; implemented modes are "),
)

# 函数/实例被拒时抛的是内建 issubclass 的报错，源码里没有这段字面量——
# 真源是"registry 用 issubclass 校验"这一事实，故断言调用点本身。
_ISSUBCLASS_CALL = "issubclass(worker_class, BaseWorker)"
_ISSUBCLASS_ERROR = "issubclass() arg 1 must be a class"

_PY_FENCE_RE = re.compile(r"```python\n(.*?)```", re.DOTALL)
_IMPORT_RE = re.compile(r"^(?:from\s+[\w.]+\s+import\s+.+|import\s+[\w.,\s]+)$")


def test_agents_md_covers_the_onboarding_content() -> None:
    """AGENTS.md 四类接入内容齐备（安装与门槛 / 注册为类 / 配置与实现分离 / 大声失败 / 验证命令）.

    牙齿：删掉任一节标题即红。
    """
    assert AGENTS_MD.is_file(), "仓库根缺少 AGENTS.md（issue #122 第 2 条）"
    text = _read(AGENTS_MD)
    missing = [section for section in _AGENTS_SECTIONS if section not in text]
    assert not missing, f"AGENTS.md 缺少这些节：{missing}"


def _flatten_string_concatenation(source: str) -> str:
    """把源码里跨行的隐式字符串拼接还原成运行期的那一条字符串.

    ``f"..."`` 换行接 ``f"..."`` 在**运行期**是一条消息，但在源码文本里被引号与缩进
    隔开。要断言"文档引用的报错文本 = 源码实际 raise 的文本"，就得先还原这一层，
    否则断言会因为排版（而非文案）变化而红。
    """
    return re.sub(r'"\n\s*f?"', "", source)


@pytest.mark.parametrize("source,literal", _SOURCE_RAISE_LITERALS, ids=lambda v: str(v)[:40])
def test_agents_md_quotes_the_real_error_text(source: str, literal: str) -> None:
    """AGENTS.md 引用的报错文本必须与源码实际 raise 的文本逐字一致.

    牙齿：把 AGENTS.md 里的报错串改错一个字符即红；改了源码文案而没改文档也即红。
    """
    src = _flatten_string_concatenation(_read(REPO_ROOT / source))
    assert literal in src, (
        f"{source} 里已找不到 {literal!r}——报错文案变了，请同步本断言与 AGENTS.md"
    )
    assert literal in _read(AGENTS_MD), f"AGENTS.md 未逐字引用 {source} 的报错文本 {literal!r}"


def test_agents_md_documents_the_class_only_registration_rule() -> None:
    """「Worker 必须以类注册」必须写明被拒绝的输入与各自报错，而不是只说"必须是类".

    牙齿：删掉 ``issubclass() arg 1 must be a class`` 这句即红——没有它，
    读文档的 agent 无法据以自我纠正。
    """
    agents = _read(AGENTS_MD)
    registry = _read(REPO_ROOT / "zoo_framework" / "core" / "worker_registry.py")
    assert _ISSUBCLASS_CALL in registry, (
        f"worker_registry.py 不再用 {_ISSUBCLASS_CALL!r} 校验——注册契约变了，请同步文档与本断言"
    )
    assert _ISSUBCLASS_ERROR in agents, (
        f"AGENTS.md 未给出函数/实例被拒时的报错：{_ISSUBCLASS_ERROR!r}"
    )
    for alternative in ("register_instance", "register_factory"):
        assert alternative in agents, f"AGENTS.md 未给出 {alternative} 这条出路"


def test_agents_md_python_floor_matches_pyproject() -> None:
    """版本门槛必须与 pyproject 的 requires-python 一致（防门槛漂移）.

    牙齿：pyproject 升到 3.14 而 AGENTS.md 仍写 3.13 即红。
    """
    match = re.search(r'requires-python\s*=\s*"([^"]+)"', _read(REPO_ROOT / "pyproject.toml"))
    assert match, "pyproject.toml 里找不到 requires-python"
    floor = re.search(r">=\s*(\d+\.\d+)", match.group(1))
    assert floor, f"无法解析 requires-python：{match.group(1)!r}"
    assert floor.group(1) in _read(AGENTS_MD), (
        f"AGENTS.md 未写明 Python 门槛 {floor.group(1)}（pyproject 要求 {match.group(1)}）"
    )


def test_agents_md_imports_execute() -> None:
    """AGENTS.md 代码块里的 import 必须真的能执行（照抄就会踩的坑）.

    牙齿：把 ``from zoo_framework.workers import BaseWorker`` 写成不存在的路径即红。
    """
    statements = [
        line.strip()
        for block in _PY_FENCE_RE.findall(_read(AGENTS_MD))
        for line in block.splitlines()
        if _IMPORT_RE.match(line.strip())
    ]
    assert statements, "AGENTS.md 里没有解析到 import 语句——解析逻辑可能已失效"
    for statement in statements:
        try:
            exec(compile(statement, "<agents-md>", "exec"), {})
        except ImportError as exc:
            pytest.fail(f"AGENTS.md 的 import 无法执行：{statement}\n    原因：{exc}")


def test_agents_md_separates_its_audience_from_claude_md() -> None:
    """AGENTS.md 面向「用本库写代码」，CLAUDE.md 面向「在本仓库改代码」——分工必须写在开头.

    牙齿：删掉 AGENTS.md 开头对 CLAUDE.md 的分工声明即红。
    """
    head = "\n".join(_lines(AGENTS_MD)[:15])
    assert "CLAUDE.md" in head, "AGENTS.md 的开头未声明与 CLAUDE.md 的分工"
    assert re.search(r"librar|using Zoo Framework", head, re.IGNORECASE), (
        "AGENTS.md 的开头未说明它讲的是「用本库写代码」"
    )
    assert CLAUDE_MD.is_file(), "CLAUDE.md 不存在——两份受众说明的分工失去了对照面"
    assert "guidance to Claude Code" in _read(CLAUDE_MD), (
        "CLAUDE.md 不再声明自己是本仓库的开发指引——请检查两份受众说明是否已混同"
    )
    for name in ("AGENTS.md", "CLAUDE.md"):
        assert "pytest" in _read(REPO_ROOT / name), f"{name} 未给出测试命令（两者必须一致可用）"


# ---------------------------------------------------------------- 4. 两份 README 的 FAQ

_QUESTION_RE = re.compile(r"^#### (.+)$", re.MULTILINE)


def _faq_section(name: str) -> str:
    """取某个 README 的 FAQ 小节正文."""
    return _section(_read(REPO_ROOT / name), README_FAQ_SECTIONS[name])


def _faq_qa_pairs(faq: str) -> list[tuple[str, str]]:
    """把 FAQ 小节切成 (问句, 短答) 对——问句是四级标题，短答是它到下一个问句之间的内容."""
    pairs: list[tuple[str, str]] = []
    for part in re.split(r"^#### ", faq, flags=re.MULTILINE)[1:]:
        question, _, body = part.partition("\n")
        pairs.append((question.strip(), body))
    return pairs


def _faq_questions(name: str) -> list[str]:
    """取某个 README 的 FAQ 问句."""
    return [question for question, _ in _faq_qa_pairs(_faq_section(name))]


def _faq_blocks(name: str) -> list[str]:
    """每块 = 一个问句 + 它的短答（首行是问句，便于失败信息定位）."""
    return [f"{question}\n{body}" for question, body in _faq_qa_pairs(_faq_section(name))]


@pytest.mark.parametrize("name", sorted(README_FAQ_SECTIONS))
def test_readme_faq_covers_every_topic(name: str) -> None:
    """每份 README 的 FAQ 必须 ≥10 组问句，且 10 个主题各自至少命中一问.

    牙齿：从任一份 README 删掉一个主题的问句（例如多进程那条）即红。
    """
    questions = _faq_questions(name)
    assert len(questions) >= 10, f"{name} 的 FAQ 只有 {len(questions)} 组问句（要求 ≥10）"
    assert all(q.rstrip().endswith(("?", "？")) for q in questions), (
        f"{name} 的 FAQ 存在非问句标题：{[q for q in questions if not q.rstrip().endswith(('?', '？'))]}"
    )
    haystack = "\n".join(questions).lower()
    unhit = [topic for topic, keys in TOPICS.items() if not any(k in haystack for k in keys)]
    assert not unhit, f"{name} 的 FAQ 未覆盖这些主题：{unhit}"


def test_readme_pair_faq_questions_match() -> None:
    """两份 README 的 FAQ 问句数与主题命中集合必须一致（各自本地化、结构同构）.

    牙齿：只给英文 README 加一条问句即红——本仓库的 README 是严格镜像维护的。
    """
    counts = {name: len(_faq_questions(name)) for name in README_FAQ_SECTIONS}
    assert len(set(counts.values())) == 1, f"两份 README 的 FAQ 问句数不一致：{counts}"

    def hits(name: str) -> set[str]:
        haystack = "\n".join(_faq_questions(name)).lower()
        return {topic for topic, keys in TOPICS.items() if any(k in haystack for k in keys)}

    first, second = hits("README.md"), hits("README.zh.md")
    assert first == second, (
        f"两份 README 的 FAQ 主题集合不一致：仅英文 {sorted(first - second)}，"
        f"仅中文 {sorted(second - first)}"
    )


def test_every_faq_answer_links_the_detailed_source() -> None:
    """每组短答末必须给出 docs/FAQ.md 的详版链接（读者要细节有去处）.

    牙齿：删掉任一组短答末尾的链接即红。
    """
    for name in README_FAQ_SECTIONS:
        blocks = _faq_blocks(name)
        assert blocks, f"{name} 的 FAQ 未解析到问答块——结构变了，请更新本断言"
        missing = [block.splitlines()[0].strip() for block in blocks if DOCS_FAQ_URL not in block]
        assert not missing, f"{name} 的这些 FAQ 短答没有给出详版链接：{missing}"


def test_readme_faq_topics_exist_in_docs_faq() -> None:
    """每个主题在 docs/FAQ.md 里都要有对应条目（详版真源必须真的更详）.

    牙齿：docs/FAQ.md 删掉「支持多进程吗？」一条即红。
    """
    headings = _QUESTION_RE.findall(_read(DOCS_FAQ)) or re.findall(
        r"^## (.+)$", _read(DOCS_FAQ), re.MULTILINE
    )
    assert headings, "docs/FAQ.md 里没有解析到问句标题——结构变了，请更新本断言"
    haystack = "\n".join(headings).lower()
    unhit = [topic for topic, keys in TOPICS.items() if not any(k in haystack for k in keys)]
    assert not unhit, f"docs/FAQ.md 缺少这些主题的条目：{unhit}"


# ---------------------------------------------------------------- 5. 发布机制（真源唯一 + 构建期复制）


def _load_hook_module():
    """按路径加载构建钩子（与 test_governance_consistency 同一做法）."""
    spec = importlib.util.spec_from_file_location("mkdocs_hooks_for_discoverability", HOOK_SCRIPT)
    assert spec and spec.loader, f"无法加载 {HOOK_SCRIPT}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_llms_txt_has_a_single_hand_written_source() -> None:
    """仓库内只有一份手写 llms.txt；docs/ 下不得有副本.

    排除 ``site/``：那是构建产物（已被 .gitignore 忽略），站点根那份正是钩子复制的结果。

    牙齿：在 docs/ 下放一份 llms.txt 副本即红——副本既会漂移、又被 mkdocs 当页面渲染。
    """
    found = sorted(
        p.relative_to(REPO_ROOT).as_posix()
        for p in REPO_ROOT.rglob("llms.txt")
        if "site" not in p.relative_to(REPO_ROOT).parts
    )
    assert found == ["llms.txt"], f"llms.txt 的手写真源必须唯一（仓库根一份），实际找到：{found}"


def test_hook_manifest_publishes_llms_txt(tmp_path: Path) -> None:
    """构建钩子的复制清单必须含 llms.txt，且复制结果与真源逐字节一致.

    牙齿：从 COPY_MANIFEST 删掉 llms.txt 即红。
    """
    hooks = _load_hook_module()
    manifest = {name for name, _, _ in hooks.COPY_MANIFEST}
    assert "llms.txt" in manifest, f"复制清单缺少 llms.txt：{sorted(manifest)}"
    assert ".well-known" in manifest, (
        f"复制清单丢掉了 .well-known（#120 的既有语义）：{sorted(manifest)}"
    )

    site_dir = tmp_path / "site"
    written = hooks.publish_manifest(
        {"config_file_path": str(MKDOCS_YML), "site_dir": str(site_dir)}
    )
    published = site_dir / "llms.txt"
    assert published in written, "清单里没有产出站点根 llms.txt"
    assert published.read_bytes() == LLMS_TXT.read_bytes(), "站点产物与真源不是逐字节一致"


def test_hook_fails_when_llms_txt_is_missing(tmp_path: Path) -> None:
    """真源 llms.txt 缺失时必须报错，而不是静默产出"没有它"的站点.

    牙齿：把钩子改成"缺失就跳过"即红。
    """
    hooks = _load_hook_module()
    root = tmp_path / "repo"
    (root / ".well-known").mkdir(parents=True)
    (root / ".well-known" / "security.txt").write_text(
        "Contact: mailto:x@example.com\n", encoding="utf-8"
    )
    config = {"config_file_path": str(root / "mkdocs.yml"), "site_dir": str(tmp_path / "site")}
    with pytest.raises(FileNotFoundError, match=r"llms\.txt"):
        hooks.publish_manifest(config)

    # 对照：把 llms.txt 放回去就不再报错（证明上一条断言是被它拦住的，不是别的原因）
    (root / "llms.txt").write_text("# Zoo Framework\n", encoding="utf-8")
    assert hooks.publish_manifest(config), "补上 llms.txt 后仍无法发布——上一条断言的理由不成立"


def test_docs_workflow_triggers_on_llms_txt() -> None:
    """部署触发路径必须覆盖 llms.txt，否则单独改它不会重新发布站点.

    牙齿：从 docs.yml 的 on.push.paths 删掉 'llms.txt' 即红。
    """
    workflow = _read(DOCS_WORKFLOW)
    assert "'llms.txt'" in workflow, (
        "docs.yml 的触发路径缺少 llms.txt：只改它时不会重新部署，站点会一直带着旧版本"
    )
    assert "'.well-known/**'" in workflow, (
        "docs.yml 丢掉 .well-known/** 的触发路径（#120 的既有语义）"
    )
