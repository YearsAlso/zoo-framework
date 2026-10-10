"""供应链加固与安全文档的机械校验.

为什么存在：``security-supply-chain`` 变更（issue #121）的结论里有好几条是**可离线判定**
的事实——"所有 action 都钉了 SHA""每个 workflow 都声明了最小权限""发布走 OIDC 而不是长期
token""依赖真源唯一""支持版本表不随版本号漂移"。写在人读文档里的这类结论会漂移，这里把它们
变成 CI 能拦住的断言。

**刻意不发网络请求**：PyPI 的来源证明、Scorecard 的分数这类需要联网或需要一次真实发布才能
验证的结论，写在 ``docs/security-supply-chain.md`` 里作为可复跑命令留档（测试在 CI 三平台
跑，联网断言会带来假红；分数本来就是快照，不适合做恒等断言）。

对应 ``openspec/changes/security-supply-chain/specs/security-model/spec.md`` 与
``.../ci-and-packaging/spec.md``。
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
RELEASE_WORKFLOW = WORKFLOW_DIR / "release.yml"
PYPROJECT = REPO_ROOT / "pyproject.toml"
UV_LOCK = REPO_ROOT / "uv.lock"
SECURITY_MD = REPO_ROOT / "SECURITY.md"
SECURITY_MODEL_MD = REPO_ROOT / "docs" / "SECURITY_MODEL.md"
SUPPLY_CHAIN_MD = REPO_ROOT / "docs" / "security-supply-chain.md"

# 可能藏第二份依赖清单的目录（不含 venv/ 之类的本地环境）
MANIFEST_SEARCH_DIRS = ("zoo_framework", "docs", "tests", ".github", "bench", "scripts")

# docs/SECURITY_MODEL.md 必须齐备的四节，中英各一份
SECURITY_MODEL_HEADINGS = (
    "### Supported versions",
    "### Reporting a vulnerability",
    "### Dependency policy",
    "### What we have not done",
    "### 支持的版本",
    "### 报告漏洞",
    "### 依赖策略",
    "### 未做的事",
)

# 支持版本表里唯一允许出现的版本字面量（固定边界，不随时间漂移）
FIXED_BOUNDARY = "1.0"

_SHA_PINNED_USES = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
_VERSION_LITERAL = re.compile(r"\d+\.\d+")
_HEADING_RE = re.compile(r"^#{2,4} ", re.MULTILINE)


# ---------------------------------------------------------------- 工具


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _workflow_paths() -> list[Path]:
    paths = sorted(WORKFLOW_DIR.glob("*.yml"))
    assert paths, f"{WORKFLOW_DIR} 下没有 workflow，断言失去意义"
    return paths


def _code_lines(text: str) -> list[str]:
    """去掉整行注释与空行后的工作流文本行.

    注释里会出现**故意提及**的反例写法（例如 release.yml 说明"原先这里写了
    ``password: secrets.PYPI_API_TOKEN``"），不剔除注释会把这些说明误判成实际配置。
    """
    return [line for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]


def _job_block(text: str, job: str) -> str:
    """取某个作业的文本块（从作业名到下一个同级作业名）."""
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.startswith(f"  {job}:"):
            start = index
            break
    assert start is not None, f"release.yml 里找不到作业 {job!r}"
    block = [lines[start]]
    for line in lines[start + 1 :]:
        if re.match(r"^  \S+:$", line):
            break
        block.append(line)
    return "\n".join(block)


def _project_metadata() -> dict[str, object]:
    return tomllib.loads(_read(PYPROJECT))["project"]


def _declared_dependency_names() -> set[str]:
    """``pyproject.toml`` 声明的运行依赖名（PEP 503 归一化）."""
    names = set()
    for spec in _project_metadata()["dependencies"]:  # type: ignore[index]
        match = re.match(r"[A-Za-z0-9._-]+", spec)
        assert match, f"无法解析依赖声明：{spec!r}"
        names.add(_normalize(match.group(0)))
    return names


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _markdown_tables(text: str) -> list[list[str]]:
    """把 markdown 里连续的 ``|`` 行切成若干张表（每张是行列表）."""
    tables: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("|"):
            current.append(line)
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def _cells(row: str) -> list[str]:
    """按 ``" | "`` 切分表格行，去掉首尾竖线（保留 ``\\|`` 转义）."""
    stripped = row.strip()
    assert stripped.startswith("|") and stripped.endswith("|"), row
    return [cell.strip() for cell in stripped[1:-1].split(" | ")]


def _section(text: str, heading: str) -> str:
    """取某个标题到下一个同级/更高级标题之间的内容."""
    start = text.find(heading)
    assert start != -1, f"找不到小节 {heading!r}"
    body = text[start + len(heading) :]
    end = _HEADING_RE.search(body)
    return body if end is None else body[: end.start()]


# ---------------------------------------------------------------- 工作流：权限与钉 SHA


def test_every_workflow_declares_top_level_permissions() -> None:
    """每个 workflow 都要在顶层声明权限，且顶层不得放开写权限."""
    missing: list[str] = []
    top_level_write: list[str] = []
    for path in _workflow_paths():
        text = _read(path)
        match = re.search(r"^permissions:\s*(.*)$", text, re.MULTILINE)
        if not match:
            missing.append(path.name)
            continue
        # 顶层块的取值范围：行内值（如 `read-all`）或紧随其后的缩进行
        inline = match.group(1).strip()
        block = [inline] if inline else []
        for line in text[match.end() :].splitlines():
            if not line.strip():
                continue
            if not line.startswith((" ", "\t")):
                break
            block.append(line.strip())
        if "write" in " ".join(block).lower():
            top_level_write.append(path.name)
    assert not missing, f"这些 workflow 没有顶层 permissions：{missing}"
    assert not top_level_write, f"这些 workflow 在顶层放开了写权限：{top_level_write}"


def test_every_action_reference_is_pinned_to_a_commit_sha() -> None:
    """所有 ``uses:`` 都必须钉在 40 位 commit SHA 上——一处漏项即失败.

    "大部分钉了"不算通过：供应链投毒只需要一个未钉的引用。本变更前 release.yml 有两处
    ``actions/checkout@v4``，正是这条断言要拦住的形态。
    """
    unpinned: list[str] = []
    total = 0
    for path in _workflow_paths():
        for line in _code_lines(_read(path)):
            match = re.search(r"uses:\s*(\S+)", line)
            if not match:
                continue
            total += 1
            target = match.group(1)
            if not _SHA_PINNED_USES.match(target):
                unpinned.append(f"{path.name}: {target}")
    assert total > 10, f"只解析到 {total} 个 uses 引用，解析逻辑可能失效"
    assert not unpinned, f"存在未钉 commit SHA 的 action 引用：{unpinned}"


def test_workflow_write_permissions_are_declared_at_job_level() -> None:
    """需要写权限的作业只在作业级声明；发布相关作业确实需要写权限."""
    text = _read(RELEASE_WORKFLOW)
    job_level = re.findall(r"^\s+permissions:$", text, re.MULTILINE)
    assert job_level, "release.yml 的作业级权限声明不见了——顶层一旦放宽会默认继承过大权限"
    builders = _code_lines(text)
    assert any("contents: write" in line for line in builders), (
        "推分支/tag 的作业应有 contents: write"
    )


# ---------------------------------------------------------------- 工作流：发布路径


def test_release_job_publishes_with_oidc() -> None:
    """发布作业用 OIDC 短期令牌（``id-token: write``）."""
    block = _job_block(_read(RELEASE_WORKFLOW), "release")
    assert "id-token: write" in block, (
        "发布作业没有声明 id-token: write（Trusted Publishing 的前提）"
    )


def test_release_job_does_not_pass_a_long_lived_token() -> None:
    """发布步骤不得传长期 token（``password``）——OIDC 的触发条件就是它为空."""
    for line in _code_lines(_read(RELEASE_WORKFLOW)):
        assert not re.match(r"^\s+password:", line), f"发布路径又接回了长期 token：{line.strip()}"
        assert "secrets.PYPI_API_TOKEN" not in line, (
            f"引用了不存在的长期 token secret：{line.strip()}"
        )


def test_release_job_produces_sbom_and_signature() -> None:
    """发布产物要有 SBOM 与 keyless 签名（"看起来成功但没有来源证明"比没有更糟）."""
    code = "\n".join(_code_lines(_read(RELEASE_WORKFLOW)))
    assert "anchore/sbom-action" in code, "发布作业缺少 SBOM 步骤"
    assert "spdx-json" in code, "SBOM 步骤不是 SPDX 格式"
    assert re.search(r"cosign sign-blob", code), "发布作业缺少 keyless 签名步骤"


def test_release_job_depends_on_tests_and_quality() -> None:
    """发布以测试与质量作业为前提——测试没过就不该有发布."""
    block = _job_block(_read(RELEASE_WORKFLOW), "release")
    match = re.search(r"needs:\s*\[([^\]]+)\]", block)
    assert match, "release.yml 的发布作业没有 needs 链"
    needs = {item.strip() for item in match.group(1).split(",")}
    assert {"test", "quality"} <= needs, f"发布作业的 needs 缺项：{needs}"


# ---------------------------------------------------------------- 依赖真源


def test_no_second_dependency_manifest() -> None:
    """仓库内不得再出现第二份手工维护的依赖清单（它与 pyproject 长期漂移过）.

    仓库根单独查一遍：`requirements.txt` 历史上就放在根目录，而根目录不能整体递归
    （本机可能有未跟踪的 `venv/` 之类的本地环境）。
    """
    found = [path.name for path in REPO_ROOT.glob("requirements*.txt")]
    for name in MANIFEST_SEARCH_DIRS:
        directory = REPO_ROOT / name
        if directory.is_dir():
            found.extend(
                str(path.relative_to(REPO_ROOT)) for path in directory.rglob("requirements*.txt")
            )
    assert not found, f"依赖真源必须唯一，发现第二份清单：{found}"


def test_lockfile_covers_every_declared_dependency() -> None:
    """``uv.lock`` 必须包含 ``pyproject.toml`` 声明的每个运行依赖."""
    locked = {_normalize(name) for name in re.findall(r'^name = "([^"]+)"$', _read(UV_LOCK), re.M)}
    assert locked, "uv.lock 里没解析到任何包，解析逻辑可能失效"
    declared = _declared_dependency_names()
    missing = sorted(declared - locked)
    assert not missing, f"这些运行依赖没有出现在 uv.lock 中（锁文件与 pyproject 已漂移）：{missing}"


# ---------------------------------------------------------------- 支持版本表


def _supported_version_tables() -> list[list[str]]:
    """取 ``SECURITY.md`` 里的支持版本表（中英各一张）的数据行."""
    tables: list[list[str]] = []
    for table in _markdown_tables(_read(SECURITY_MD)):
        header = _cells(table[0]) if table else []
        if header == ["Version", "Supported"] or header == ["版本", "是否支持"]:
            tables.append(table[2:])
    assert len(tables) == 2, f"SECURITY.md 的支持版本表结构变了：解析到 {len(tables)} 张"
    return tables


def test_supported_versions_table_has_no_drifting_version_literals() -> None:
    """支持版本表不得写死当前版本线——**举例里的版本号同样会漂移**."""
    for index, rows in enumerate(_supported_version_tables(), start=1):
        body = "\n".join(rows).replace(FIXED_BOUNDARY, "")
        literals = _VERSION_LITERAL.findall(body)
        assert not literals, (
            f"第 {index} 张支持版本表里出现了会漂移的版本字面量 {literals}："
            "改成相对表述（最新 minor 线 / 更早的 minor 线），别在表里写具体版本号"
        )


def test_supported_versions_tables_agree_across_languages() -> None:
    """中英两份支持表的行数与逐行支持标记必须一致."""
    english, chinese = _supported_version_tables()
    assert len(english) == len(chinese), f"中英支持表行数不一致：{len(english)} vs {len(chinese)}"
    for english_row, chinese_row in zip(english, chinese, strict=True):
        english_marks = [mark for mark in ("✅", "❌") if mark in english_row]
        chinese_marks = [mark for mark in ("✅", "❌") if mark in chinese_row]
        assert english_marks == chinese_marks, (
            f"同一行的支持标记不一致：{english_row!r} vs {chinese_row!r}"
        )


def test_security_policy_does_not_name_the_current_version() -> None:
    """``SECURITY.md`` 不得出现 ``pyproject.toml`` 的当前版本串（否则每次发版都会漂移）."""
    version = _project_metadata()["version"]
    assert version not in _read(SECURITY_MD), (
        f"SECURITY.md 里写死了当前版本 {version}——发版后会立刻过时"
    )


# ---------------------------------------------------------------- 安全模型文档


def test_security_model_document_has_required_sections() -> None:
    """四节齐备，中英各一份."""
    text = _read(SECURITY_MODEL_MD)
    missing = [heading for heading in SECURITY_MODEL_HEADINGS if heading not in text]
    assert not missing, f"docs/SECURITY_MODEL.md 缺小节：{missing}"


def test_security_model_lists_what_has_not_been_done() -> None:
    """「未做的事」必须具体：至少三条，且包含「没有第三方审计」与「默认分支未生效」."""
    english = _section(_read(SECURITY_MODEL_MD), "### What we have not done")
    chinese = _section(_read(SECURITY_MODEL_MD), "### 未做的事")
    for name, body in (("英文", english), ("中文", chinese)):
        bullets = [line for line in body.splitlines() if line.strip().startswith("- ")]
        assert len(bullets) >= 3, f"{name}的「未做的事」只有 {len(bullets)} 条"
        assert "#107" in body, f"{name}的「未做的事」没有点出默认分支未生效（#107）"
    assert "audit" in english.lower(), "英文「未做的事」没有明写尚未做第三方安全审计"
    assert "审计" in chinese, "中文「未做的事」没有明写尚未做第三方安全审计"


def test_security_model_dependency_facts_match_pyproject() -> None:
    """文档声明的运行依赖条数与名字必须与 ``pyproject.toml`` 一致."""
    text = _read(SECURITY_MODEL_MD)
    declared = _declared_dependency_names()
    english = re.search(r"Runtime dependencies \(\**(\d+)\**\):\s*([^\n]+)", text)
    chinese = re.search(r"运行依赖（(\d+) 个）：([^\n]+)", text)
    assert english, "英文依赖策略没有给出可核对的依赖清单"
    assert chinese, "中文依赖策略没有给出可核对的依赖清单"
    for name, match in (("英文", english), ("中文", chinese)):
        count = int(match.group(1))
        listed = {
            _normalize(item.strip().strip(".。"))
            for item in re.split(r"[,、]", match.group(2))
            if item.strip()
        }
        assert count == len(declared), (
            f"{name}声明 {count} 个运行依赖，pyproject.toml 实为 {len(declared)} 个"
        )
        assert listed == declared, f"{name}列出的依赖与 pyproject.toml 不一致：{listed ^ declared}"


# ---------------------------------------------------------------- 供应链状态表


def _status_rows() -> list[dict[str, str]]:
    """取状态表的数据行（``| 项 | 结论 | 生效范围 | 证据 |``）."""
    tables = [
        table
        for table in _markdown_tables(_read(SUPPLY_CHAIN_MD))
        if table and _cells(table[0]) == ["项", "结论", "生效范围", "证据"]
    ]
    assert tables, "docs/security-supply-chain.md 里找不到 | 项 | 结论 | 生效范围 | 证据 | 表"
    rows: list[dict[str, str]] = []
    for table in tables:
        for row in table[2:]:
            item, conclusion, scope, evidence = _cells(row)
            rows.append(
                {"item": item, "conclusion": conclusion, "scope": scope, "evidence": evidence}
            )
    return rows


def test_status_table_covers_every_issue_with_evidence() -> None:
    """#89–#95 每条都要在表里，且证据列是可复核的定位而不是断言."""
    rows = _status_rows()
    items = " ".join(row["item"] for row in rows)
    missing = [f"#{number}" for number in range(89, 96) if f"#{number}" not in items]
    assert not missing, f"状态表缺项：{missing}"
    for row in rows:
        evidence = row["evidence"]
        assert len(evidence) > 20, f"{row['item']} 的证据过于笼统：{evidence!r}"
        assert not re.fullmatch(r"(已完成|已落地|done|已做)[。.]?", evidence), (
            f"{row['item']} 的证据列只是断言，没有给出文件/行号或可复跑命令"
        )


def test_status_table_flags_items_that_only_landed_on_the_development_line() -> None:
    """已落地的项必须标注生效范围——把只落在开发线的加固写成「已生效」要变红."""
    flagged = 0
    for row in _status_rows():
        if "已落地" in row["conclusion"] or "部分落地" in row["conclusion"]:
            assert "默认分支尚未生效" in row["scope"], (
                f"{row['item']} 记了已落地，但没标注默认分支的生效范围"
            )
            flagged += 1
    assert flagged >= 5, f"只有 {flagged} 项被标注，状态表可能已不为 #89–#95 记账"


def test_status_table_records_the_external_snapshot() -> None:
    """外部审计结论要能追溯到采样时间与被采样 commit，而不是一句"分数低"."""
    text = _read(SUPPLY_CHAIN_MD)
    assert "api.securityscorecards.dev" in text, "状态表没有给出 Scorecard 的复核入口"
    assert "6ee3944e5566a4184ac12fcab2f51ed5196c60d8" in text, "状态表没有记录被采样的 commit"
    assert "2026-10-10T01:54:00Z" in text, "状态表没有记录采样时间"
    assert "Token-Permissions" in text and "Pinned-Dependencies" in text, (
        "状态表没有逐项记录扣分项，无法解释分数"
    )


def test_status_table_records_rerunnable_commands() -> None:
    """依赖漏洞的结论必须配可复跑的命令（不依赖 CI 也能复核）."""
    text = _read(SUPPLY_CHAIN_MD)
    assert "pip-audit" in text, "状态表没有给出依赖漏洞扫描命令"
    assert "uv lock --check" in text, "状态表没有给出锁文件一致性命令"
    assert "provenance" in text, "状态表没有给出产物来源证明的核对命令"
