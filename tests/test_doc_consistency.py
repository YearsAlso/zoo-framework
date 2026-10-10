"""文档一致性机械校验.

这个文件存在的理由：docs/ 里有约 200 段代码与数十条 API 指令，全部手工维护。
在引入本文件之前，没有任何机制能发现"文档里的导入路径跑不通"——
实测就抓到过两处（`zoo_framework.core.MasterConfig` 与
`zoo_framework.statemachine.StateScope` 都不存在，但都写在文档里）。

因此这里把三类可机械判定的约定变成 CI 能拦住的断言：

1. ``docs/api/**`` 里的 mkdocstrings 指令必须指向真实可导入的对象；
2. 文档 python 代码块里的 import 语句必须真的能执行；
3. 文档里的相对链接与资源引用必须指向存在的文件。

对应 ``docs/contributing/brand.md`` 与 ``docs/contributing/contributing.md`` 中
"文档改动 MUST 保持可执行"的约定。
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"

# ---------------------------------------------------------------- 工具

# mkdocstrings 指令：以 "::: " 开头的模块/对象路径，允许后面跟 options 块
_MKDOCSTRINGS_RE = re.compile(r"^:::\s+([A-Za-z_][\w.]*)\s*$", re.MULTILINE)

# python 代码块
_PY_FENCE_RE = re.compile(r"```python\n(.*?)```", re.DOTALL)

# import 语句（含缩进的续行不做处理；文档里的 import 一律顶格）
_IMPORT_RE = re.compile(r"^(?:from\s+[\w.]+\s+import\s+.+|import\s+[\w.,\s]+)$", re.MULTILINE)

# markdown 相对链接
_LINK_RE = re.compile(r"\]\(([^)]+)\)")


# ``docs/internal/`` 是不发布到文档站的内部工作日志（见 mkdocs.yml 的 exclude_docs），
# 其中有引用开发期临时库的片段。它不是对外承诺的文档，故不纳入校验。
_EXCLUDED_DIRS = ("internal",)


# 被 HTML 注释掉的内容不算文档承诺（例如已下线的占位图引用）
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _strip_html_comments(text: str) -> str:
    """去掉 HTML 注释，避免对注释里的内容做校验。"""
    return _HTML_COMMENT_RE.sub("", text)


def _doc_files() -> list[Path]:
    files = [p for p in DOCS.rglob("*.md") if not any(part in _EXCLUDED_DIRS for part in p.parts)]
    files.append(REPO_ROOT / "README.md")
    files.append(REPO_ROOT / "README.zh.md")
    return sorted(p for p in files if p.exists())


def _resolve_dotted(dotted: str):
    """导入 ``a.b.C`` 形式的最长可导入前缀，返回 (module, attr_or_None)."""
    parts = dotted.split(".")
    for split in range(len(parts), 0, -1):
        mod_name = ".".join(parts[:split])
        try:
            mod = importlib.import_module(mod_name)
        except Exception:
            continue
        obj = mod
        for attr in parts[split:]:
            if not hasattr(obj, attr):
                raise AttributeError(f"{mod_name} has no attribute {attr!r}")
            obj = getattr(obj, attr)
        return obj
    raise ImportError(f"cannot import any prefix of {dotted!r}")


# ---------------------------------------------------------------- 1. API 指令


def _mkdocstrings_targets() -> list[tuple[Path, str]]:
    out = []
    for f in sorted((DOCS / "api").rglob("*.md")):
        for m in _MKDOCSTRINGS_RE.finditer(f.read_text(encoding="utf-8")):
            out.append((f, m.group(1)))
    return out


def test_api_pages_have_mkdocstrings_targets():
    """API 参考必须真的由指令生成，而不是空页。"""
    targets = _mkdocstrings_targets()
    assert targets, "docs/api/ 下没有任何 mkdocstrings 指令——API 参考未接入自动生成"


@pytest.mark.parametrize("path,dotted", _mkdocstrings_targets(), ids=lambda v: str(v))
def test_mkdocstrings_target_importable(path: Path, dotted: str):
    """``::: a.b.C`` 必须指向真实可导入的对象，否则文档站会渲染出空白页。"""
    try:
        _resolve_dotted(dotted)
    except Exception as exc:
        pytest.fail(f"{path.relative_to(REPO_ROOT)}: 指令 `::: {dotted}` 无法解析：{exc}")


# ---------------------------------------------------------------- 2. 文档里的 import

# 迁移指南等文档需要展示"旧写法已经跑不通"的反例。这类块必须显式豁免，
# 否则本测试会把有意的反例当成真错误。约定：块内首行含下列标记之一即跳过。
_SKIP_MARKERS = ("# doc-example: skip", "# 反例", "# counter-example")


def _doc_imports() -> list[tuple[Path, str]]:
    out = []
    for f in _doc_files():
        text = _strip_html_comments(f.read_text(encoding="utf-8"))
        for block in _PY_FENCE_RE.findall(text):
            if any(m in block for m in _SKIP_MARKERS):
                continue
            for line in block.splitlines():
                line = line.strip()
                # 相对导入（``from .x import y``）是"示例模块"的写法，无法脱离上下文执行
                if line.startswith("from .") or line.startswith("import ."):
                    continue
                if _IMPORT_RE.match(line):
                    out.append((f, line))
    return out


def test_docs_contain_imports():
    """防止正则失效导致本测试静默退化为空跑。"""
    assert _doc_imports(), "没有从文档中提取到任何 import 语句——提取逻辑可能已失效"


@pytest.mark.parametrize("path,statement", _doc_imports(), ids=lambda v: str(v)[:70])
def test_documented_imports_execute(path: Path, statement: str):
    """文档里写的 import 必须真的能执行。

    这是本文件最有价值的一条：实测它抓到过五处不存在的路径，包括
    ``zoo_framework.core.MasterConfig``、``zoo_framework.statemachine.StateScope``、
    ``zoo_framework.plugin.ExponentialDelayStrategy``（该类根本不存在），
    以及一个**已被删除**的 ``register_worker`` 仍被文档引用。

    对非 ``zoo_framework`` 的导入，校验其顶层模块可导入（标准库或已安装依赖），
    从而拦住"文档引用了本项目并不依赖的库"这类问题。
    """
    try:
        exec(compile(statement, "<doc>", "exec"), {})
    except ImportError as exc:
        pytest.fail(
            f"{path.relative_to(REPO_ROOT)}: 文档中的导入无法执行\n"
            f"    语句: {statement}\n"
            f"    原因: {type(exc).__name__}: {exc}"
        )


# ---------------------------------------------------------------- 3. 链接与资源


def _relative_links() -> list[tuple[Path, str]]:
    out = []
    for f in _doc_files():
        text = _strip_html_comments(f.read_text(encoding="utf-8"))
        for m in _LINK_RE.finditer(text):
            target = m.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            out.append((f, target.split("#", 1)[0]))
    return out


def test_relative_links_resolve():
    """文档中的相对链接必须指向存在的文件（移动文档后最容易失效的一类）。"""
    broken = []
    for f, target in _relative_links():
        if any(part in _EXCLUDED_DIRS for part in f.parts) and False:
            continue
        if not target:
            continue
        resolved = (f.parent / target).resolve()
        if not resolved.exists():
            broken.append(f"    {f.relative_to(REPO_ROOT)} -> {target}")
    assert not broken, "文档中的相对链接指向不存在的文件：\n" + "\n".join(broken)


# ---------------------------------------------------------------- 4. 中文锚点

# mkdocs 默认的 slugify 会**剥离非 ASCII 字符**，因此中文标题产生的锚点是空的或退化的：
# 实测 ``## 🇨🇳 中文`` 生成的 id 是 ``_1``，``## 为 AI 生成代码而设计`` 生成的 id 是 ``ai``。
# 于是 ``[中文](#中文)`` 这类链接指向不存在的锚点——站点上点不动。
#
# 规则：**不要链接到中文锚点**。需要锚点时用 attr_list 显式指定 ASCII id：
#     ## 中文 {#zh}
#     [中文](#zh)
_CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")


def _anchor_links() -> list[tuple[Path, str]]:
    out = []
    for f in _doc_files():
        for m in _LINK_RE.finditer(f.read_text(encoding="utf-8")):
            target = m.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if "#" in target:
                out.append((f, target))
    return out


def test_no_cjk_anchor_links():
    """禁止链接到中文锚点——slugify 会把中文剥空，链接必然点不动。

    需要中文标题作为锚点目标时，用 ``## 标题 {#ascii-id}`` 显式指定。
    """
    bad = []
    for f, target in _anchor_links():
        frag = target.split("#", 1)[1]
        if frag and _CJK.search(frag):
            bad.append(f"    {f.relative_to(REPO_ROOT)} -> {target}")
    assert not bad, (
        "以下链接指向中文锚点，而 mkdocs 的 slugify 会剥离中文字符，锚点实际不存在：\n"
        + "\n".join(bad)
        + "\n修法：给标题加显式 id（## 中文 {#zh}），并链接到该 id。"
    )


def test_readme_hero_image_has_bitmap_fallback():
    """README 首屏的 <picture> 内层 <img> 必须指向位图。

    理由（已实测）：PyPI 的 readme_renderer 会**保留 <picture> 与内层 <img>，
    但剥掉 <source>**。若内层 src 是 SVG，PyPI 上就会没有标识。
    """
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    head = readme[:1500]
    assert "<picture>" in head, "README 首屏应使用 <picture> 以支持深色模式"
    inner = re.search(r'<img\s+src="([^"]+)"', head)
    assert inner, "README 首屏的 <picture> 内缺少 <img> 兜底"
    assert not inner.group(1).endswith(".svg"), (
        "README 首屏 <picture> 的内层 <img> 指向了 SVG；"
        "PyPI 会剥掉 <source> 后落到它，而 SVG 在 PyPI 上不保证可用——请指向位图"
    )


# ================================================================
# 4. 面向读者的陈述与实况一致（doc-consistency-sweep #114）
#
# 这一节维护"文档宣称 = 仓库实况"的机械契约。每条断言都以
# "改坏文档宣称后必须变红"为目标（牙齿见各 docstring）。
# ================================================================

# 硬编码"具体用例数"的禁入区：数值随每次合并漂移，人工维护必错
# （实测基线 1024，旧文档写 367——写下去的当天就开始错）。
_CASE_COUNT_FILES = ("docs/contributing/structure.md",)


def test_no_hardcoded_case_counts():
    """维护者速览文档不得用具体数字描述测试规模。

    牙齿：把 ``see the Tests badge`` 改回 ``367 cases`` 即红——该数字与实况
    无联动，写下即开始漂移（对应 issue #114 第 1 条）。
    """
    pattern = re.compile(r"\d+\s*(?:cases?|条用例)", re.IGNORECASE)
    bad = []
    for name in _CASE_COUNT_FILES:
        for line_no, line in enumerate(
            (REPO_ROOT / name).read_text(encoding="utf-8").splitlines(), 1
        ):
            if pattern.search(line):
                bad.append(f"    {name}:{line_no}: {line.strip()}")
    assert not bad, "文档不得硬编码会漂移的用例数：\n" + "\n".join(bad)


# ---- 4.2 Python 门槛（issue #114 第 5 条） ----

_PY_FLOOR_DOC = "docs/contributing/development.md"


def _pyproject_requires_python() -> str:
    m = re.search(
        r'requires-python\s*=\s*"([^"]+)"',
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"),
    )
    assert m, "pyproject.toml 里找不到 requires-python"
    return m.group(1)


def test_python_floor_claims_match_pyproject():
    """环境要求里的 Python 门槛必须与 pyproject 的 requires-python 一致。

    牙齿：把 development.md 的 ``| Python | 3.13 |`` 改回 ``| Python | 3.8 |``
    即红——那是唯一读得到的"环境要求"事实陈述，而 pyproject 是硬门槛真源。
    """
    spec = _pyproject_requires_python()
    m = re.search(r">=\s*(\d+)\.(\d+)", spec)
    assert m, f"无法解析 requires-python：{spec!r}"
    floor = f"3.{m.group(2)}" if m.group(1) == "3" else f"{m.group(1)}.{m.group(2)}"

    table = (REPO_ROOT / _PY_FLOOR_DOC).read_text(encoding="utf-8")
    row = re.search(r"\|\s*Python\s*\|\s*(\d+)\.(\d+)\s*\|", table)
    assert row, f"{_PY_FLOOR_DOC} 的环境要求表里没有 Python 行"
    claimed = f"{row.group(1)}.{row.group(2)}"
    assert claimed == floor, (
        f"{_PY_FLOOR_DOC} 声称 Python {claimed}，pyproject 要求 {spec} —— 环境要求表过期"
    )
    assert "3.8" not in table, f"{_PY_FLOOR_DOC} 仍出现陈旧的 Python 3.8 门槛"


# ---- 4.3 隐喻映射表三处同源（issue #114 第 4 条） ----

# 表路径与解析约定：每个文件有且仅有一张隐喻表，前两列是 (隐喻, 组件)。
_METAPHOR_TABLE_FILES = {
    "README.md": "| Metaphor | Component",
    "README.zh.md": "| 隐喻 | 对应组件",
    "CLAUDE.md": "| Metaphor | Component",
}
_DEAD_MAPS = ("Zookeeper", "Food", "Feeder queue")


def _metaphor_pairs() -> dict[str, set[tuple[str, str]]]:
    out = {}
    for name, header in _METAPHOR_TABLE_FILES.items():
        pairs = set()
        in_table = False
        for line in (REPO_ROOT / name).read_text(encoding="utf-8").splitlines():
            if line.startswith("|") and header in line:
                in_table = True
                continue
            if in_table:
                if not line.startswith("|"):
                    break  # 表结束
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) >= 2 and cells[0] and "---" not in cells[0]:
                    metaphor = cells[0]
                    component = re.sub(r"[`*]", "", cells[1]).strip()
                    pairs.add((metaphor, component))
        out[name] = pairs
    return out


def test_metaphor_tables_converge():
    """README / README.zh / CLAUDE.md 三处隐喻表描述同一组映射。

    牙齿：在 CLAUDE.md 的表里加回 ``| 👨🌾 Zookeeper | Master | ... |`` 即红
    ——该映射在代码中零引用（Zookeeper/Food/Feeder queue 不存在），
    实况以 README 表为准（对应 issue #114 第 4 条）。
    """
    tables = _metaphor_pairs()
    empty = [name for name, pairs in tables.items() if not pairs]
    assert not empty, f"隐喻表解析为空：{empty}（表格式变了，更新解析器）"

    # 组件列集合必须一致（隐喻前列允许语言差异，组件名是代码实体，逐字比对）。
    # zh 表把 `BaseWorker` 子类 译作 `BaseWorker` subclass 的中文——归一化到"取
    # 第一个反引号实体"这一公共核心，保证三处指同一组件。
    def _norm(pairs: set[tuple[str, str]]) -> set[tuple[str, str]]:
        return {
            (
                m.split()[1] if len(m.split()) > 1 else m,  # 「🦁 **Worker**」→ 实体名
                c.split("`")[0].strip() if "`" in c else c,
            )
            for m, c in pairs
        }

    # 组件列已归一化到反引号前的实体名；zh 的 BaseWorker 子类 需要拆到实体名：
    def _comp_key(c: str) -> str:
        c = re.sub(r"[`*]", "", c).strip()
        # 中文描述带"子类/子目录"尾巴的，取到首个 ascii 词段
        m = re.search(r"[A-Za-z][\w/]*(?:\s*/\s*[A-Za-z][\w/]*)*", c)
        return m.group(0) if m else c

    en = {_comp_key(c) for _, c in tables["README.md"]}
    for other in ("README.zh.md", "CLAUDE.md"):
        got = {_comp_key(c) for _, c in tables[other]}
        assert got == en, f"{other} 的隐喻表组件集与 README.md 不一致：{sorted(got ^ en)}"

    # 禁用废映射：这些隐喻名在代码中零匹配
    for name, pairs in tables.items():
        for dead in _DEAD_MAPS:
            assert not any(dead in m for m, _ in pairs), (
                f"{name} 的隐喻表出现了代码中不存在的隐喻 {dead!r}"
            )


# ---- 4.4 健康监控宣称如实（issue #114 第 2 条 + B2 的日志诚实化防回退） ----

_DEAD_CLAIM = "SVM monitoring started"
# "宣称健康监控能力"的位置及其必须携带的未接通标注
_SVM_CLAIM_SITES = (
    # 只认"能力宣称"位置（表格行 / 特性清单），不认架构图与类图——图里画的是
    # 结构不是能力承诺，逐处标注会把 mermaid 源码改花。
    # 声明形：正则 -> 该宣称行(或其近邻)必须携带的标注之一。
    ("docs/ARCHITECTURE.md", r"^- SVM 健康监控", "尚未接通"),
    ("docs/contributing/roadmap.md", r"^\| .*健康监控.*\|", "尚未接通"),
    ("README.md", r"^\| Health monitoring", "not yet wired"),
    ("README.zh.md", r"^\| .*健康监控.*\|", "尚未接通"),
    ("docs/README.md", r"^\| 健康监控指标链路", "⚠️"),
)


def test_no_dead_health_claims():
    """SVM 能力宣称处必须携带「指标链路尚未接通」级标注；废弃宣称词不得回归。

    牙齿：删掉 ARCHITECTURE.md「关键特性」行里的"（指标链路尚未接通 …）"
    即红；把 `SVM monitoring started` 写回任何文档/源码即红——那是 B2 诚实化
    之前的不实宣称字样（当时 metrics 根本没接线）。
    """
    bad = []
    for name, claim_re, marker in _SVM_CLAIM_SITES:
        lines = (REPO_ROOT / name).read_text(encoding="utf-8").splitlines()
        text = "\n".join(lines)
        if _DEAD_CLAIM in text:
            bad.append(f"    {name}: 出现废弃宣称字样 {_DEAD_CLAIM!r}")
        claims = [i for i, line in enumerate(lines) if re.search(claim_re, line)]
        assert claims or "roadmap" in name, (
            f"{name}: 未找到能力宣称行（{claim_re!r}）——文档结构变了，更新断言"
        )
        for i in claims:
            near = "\n".join(lines[max(0, i - 2) : min(len(lines), i + 3)])
            if not re.search(marker, near):
                bad.append(f"    {name}:{i + 1}: SVM 能力宣称无未接通标注: {lines[i].strip()[:60]}")
    # 运行时日志源码也不得复活旧字样
    for py in sorted((REPO_ROOT / "zoo_framework").rglob("*.py")):
        if _DEAD_CLAIM in py.read_text(encoding="utf-8"):
            bad.append(f"    {py.relative_to(REPO_ROOT)}: 源码出现废弃宣称字样")
    assert not bad, "健康监控宣称与实况不符：\n" + "\n".join(bad)
