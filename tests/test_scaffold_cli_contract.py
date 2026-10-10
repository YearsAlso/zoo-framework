"""fix-scaffold-cli-contract 的回归测试.

对应：
- `openspec/changes/fix-scaffold-cli-contract/specs/cli-scaffolding/spec.md`
- `openspec/changes/fix-scaffold-cli-contract/specs/project-scaffolding/spec.md`

每条用例映射到一个具体 scenario。用例全部在临时目录内运行，不依赖仓库结构。
"""

import ast
import importlib
import json
import os
import re
import sys
from pathlib import Path

import pytest
from click import BadParameter, UsageError
from click.testing import CliRunner

from zoo_framework.cli import zfc

REPO_ROOT = Path(__file__).resolve().parent.parent

# 脚手架产出的包，导入它们会写框架的进程级全局注册表（config_funcs / 事件通道注册表）
GENERATED_TOP_LEVEL = {"conf", "events", "params", "workers"}
GENERATED_MODULE_NAMES = ("conf.demo_conf", "params.demo_params", "events.demo_event")


def _reset_generated_state(src_dir: Path) -> None:
    """清掉上一个生成项目留下的模块缓存与框架全局状态.

    框架有三处进程级全局状态会被生成模块写入，不清干净，后一次断言可能被前一次
    导入的模块对象蒙混过去：

    - `sys.modules`：模块缓存
    - `config_funcs`：`@configure` 注册表
    - `aop.params.config_params`：`@params` 的解析缓存，**按限定名索引**；
      历史上按裸类名索引，两个同名配置类会在同一进程里命中同一条记录
    """
    for name in list(sys.modules):
        if name == "main" or name.split(".")[0] in GENERATED_TOP_LEVEL:
            sys.modules.pop(name, None)
    path = str(src_dir)
    while path in sys.path:
        sys.path.remove(path)

    from zoo_framework.core.aop import config_funcs
    from zoo_framework.core.aop.params import config_params as resolved_params

    # ThreadSafeDict.pop 不接受默认值，先判存在
    if "demo_conf" in config_funcs:
        config_funcs.pop("demo_conf")
    # 解析缓存以限定名为键，按后缀清掉生成模块留下的条目
    for key in [k for k in list(resolved_params) if k.endswith("DemoParams")]:
        resolved_params.pop(key, None)


def _import_entry(project: Path):
    """导入生成项目的入口模块（不触发 main 的无限循环）."""
    src_dir = project / "src"
    sys.path.insert(0, str(src_dir))
    return importlib.import_module("main")


@pytest.fixture
def in_dir(tmp_path, monkeypatch):
    """把工作目录切到临时目录，避免产出落到仓库里."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _snapshot(root: Path) -> dict:
    """记录目录下每个文件的字节内容，用于比对"现场未被改动"."""
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


# =============================================================================
# 1 · 新增 Worker 的名称 MUST 是合法标识符
# =============================================================================

ILLEGAL_NAMES = ["my-task", "123task", "my task", "my.task", "", "class", "def"]


class TestWorkerNameValidation:
    """cli-scaffolding: 新增 Worker 的名称 MUST 是合法标识符."""

    @pytest.mark.parametrize("name", ILLEGAL_NAMES)
    def test_illegal_name_is_rejected(self, in_dir, name):
        """Scenario: 非法名称被拒绝.

        断言的是"命令失败"与"指出了问题"，不是某个具体措辞——措辞会变，
        失败与否不会。
        """
        from zoo_framework.cli.scaffold import _validate_worker_name

        with pytest.raises((BadParameter, UsageError)):
            _validate_worker_name(name)

    @pytest.mark.parametrize("name", ILLEGAL_NAMES)
    def test_illegal_name_produces_no_file(self, in_dir, name):
        """Scenario: 非法名称不产出任何文件.

        必须在**文件系统**上断言，而不是只断言退出码：本变更要修的正是
        "退出码为 0 但磁盘上多了一份坏产物"。
        """
        runner = CliRunner()
        runner.invoke(zfc, ["--create", "proj"])

        before = _snapshot(in_dir)
        result = runner.invoke(zfc, ["--worker", name], catch_exceptions=False)
        after = _snapshot(in_dir)

        assert result.exit_code != 0, f"{name!r} 被接受了"
        assert before == after, f"{name!r} 产出了文件：{set(after) - set(before)}"

    def test_illegal_name_is_rejected_via_cli(self, in_dir):
        """Scenario: 非法名称被拒绝（命令层）."""
        runner = CliRunner()
        runner.invoke(zfc, ["--create", "proj"])

        result = runner.invoke(zfc, ["--worker", "my-task"])

        assert result.exit_code != 0
        assert "my-task" in result.output or "my_task" in result.output

    @pytest.mark.parametrize("name", ["my_task", "task2", "_private", "a"])
    def test_legal_name_is_accepted(self, in_dir, name):
        """Scenario: 合法名称被接受.

        产出的模块与入口都必须能被解析——"命令成功"不等于"产物可用"。
        """
        runner = CliRunner()
        runner.invoke(zfc, ["--create", "proj"])
        monkeypatch_dir = in_dir / "proj"
        os.chdir(monkeypatch_dir)

        result = runner.invoke(zfc, ["--worker", name])

        assert result.exit_code == 0, result.output
        module = monkeypatch_dir / "src" / "workers" / f"{name}_worker.py"
        assert module.exists()
        for path in (module, monkeypatch_dir / "src" / "main.py"):
            ast.parse(path.read_text(encoding="utf-8"))

    @pytest.mark.parametrize("name", ["my_task", "task2", "_private", "a"])
    def test_legal_name_yields_legal_class_name(self, in_dir, name):
        """合法名称推导出的类名也必须是合法标识符（否则又产出不可解析的文件）."""
        from zoo_framework.cli.scaffold import _worker_names

        _, class_name = _worker_names(name)

        assert class_name.isidentifier(), f"{name!r} 推导出非法类名 {class_name!r}"


# =============================================================================
# 2 · 产出操作无法完成时 MUST 明确失败并保持现场不变
# =============================================================================


class TestCreateFailure:
    """cli-scaffolding: 产出操作无法完成时 MUST 明确失败并保持现场不变."""

    def test_existing_target_fails(self, in_dir):
        """Scenario: 创建目标已存在时报错."""
        (in_dir / "proj").mkdir()

        result = CliRunner().invoke(zfc, ["--create", "proj"])

        assert result.exit_code != 0, "目标已存在却静默成功"
        assert "proj" in result.output

    def test_existing_target_is_untouched(self, in_dir):
        """Scenario: 创建目标已存在时不改动现场."""
        target = in_dir / "proj"
        (target / "sub").mkdir(parents=True)
        (target / "config.json").write_text('{"keep": true}', encoding="utf-8")
        (target / "sub" / "note.txt").write_text("用户手写内容", encoding="utf-8")

        before = _snapshot(target)
        CliRunner().invoke(zfc, ["--create", "proj"])
        after = _snapshot(target)

        assert before == after, "目标已存在时现场被改动了"

    def test_nested_path_is_created(self, in_dir):
        """Scenario: 嵌套路径被正确创建."""
        result = CliRunner().invoke(zfc, ["--create", os.path.join("nested", "app")])

        assert result.exit_code == 0, result.output
        assert (in_dir / "nested" / "app" / "src" / "main.py").exists()

    def test_nested_path_does_not_raise_traceback(self, in_dir):
        """失败路径 MUST NOT 向调用方抛裸异常栈."""
        result = CliRunner().invoke(zfc, ["--create", os.path.join("a", "b", "c")])

        assert result.exit_code == 0, result.output
        assert "Traceback" not in result.output


# =============================================================================
# 2.5 --create 成功摘要与失败摘要抑制（scaffold-demo-worker #110）
# =============================================================================


class TestCreateSummary:
    """project-scaffolding: --create 成功时 MUST 报告结果与下一步命令."""

    def test_success_summary_contains_location_count_and_next_command(self, in_dir):
        """Scenario: 成功摘要含下一步命令."""
        result = CliRunner().invoke(zfc, ["--create", "proj"])

        assert result.exit_code == 0
        out = result.output
        # 三要素：创建位置 / 生成文件量 / 完整可复制的下一步命令
        assert "proj" in out, f"摘要应含创建位置：{out!r}"
        assert re.search(r"\d+", out), f"摘要应含生成文件量：{out!r}"
        assert "cd proj" in out and "python src/main.py" in out, f"摘要应含完整下一步命令：{out!r}"

    def test_failure_suppresses_summary(self, in_dir):
        """Scenario: 失败路径契约不变——成功摘要 MUST NOT 被打印."""
        (in_dir / "proj").mkdir()

        result = CliRunner().invoke(zfc, ["--create", "proj"])

        assert result.exit_code != 0
        assert "cd proj" not in result.output, "失败路径不应打印下一步命令摘要"


# =============================================================================
# 3 · 一次调用中的创建项目与新增 Worker MUST 协同
# =============================================================================


class TestCreateAndWorkerTogether:
    """cli-scaffolding: 一次调用中的创建项目与新增 Worker MUST 协同."""

    def test_worker_lands_inside_created_project(self, in_dir):
        """Scenario: Worker 落入本次创建的项目."""
        result = CliRunner().invoke(zfc, ["--create", "proj", "--worker", "task"])

        assert result.exit_code == 0, result.output
        assert (in_dir / "proj" / "src" / "workers" / "task_worker.py").exists()
        # 产出 MUST NOT 落到本次创建的项目之外
        assert not (in_dir / "workers").exists(), "Worker 落到了项目外"

    def test_worker_is_registered_by_created_entry(self, in_dir):
        """Scenario: Worker 被本次创建的入口注册."""
        CliRunner().invoke(zfc, ["--create", "proj", "--worker", "task"])

        main = (in_dir / "proj" / "src" / "main.py").read_text(encoding="utf-8")
        assert "from workers.task_worker import TaskWorker" in main
        assert '("TaskWorker", TaskWorker),' in main

    def test_entry_with_combined_call_is_parseable(self, in_dir):
        """组合调用的产出必须仍是可解析的入口."""
        CliRunner().invoke(zfc, ["--create", "proj", "--worker", "task"])

        ast.parse((in_dir / "proj" / "src" / "main.py").read_text(encoding="utf-8"))

    def test_illegal_worker_name_creates_nothing(self, in_dir):
        """非法 Worker 名 MUST NOT 留下半个项目.

        "非法输入不产出任何文件"必须是字面成立的，而不是仅对单独调用成立。
        """
        before = _snapshot(in_dir)
        result = CliRunner().invoke(zfc, ["--create", "proj", "--worker", "my-task"])
        after = _snapshot(in_dir)

        assert result.exit_code != 0
        assert before == after, "非法输入留下了产出"


# =============================================================================
# 4 · 重复新增同名 Worker MUST 幂等
# =============================================================================


class TestWorkerWiringIdempotence:
    """cli-scaffolding: 重复新增同名 Worker MUST 幂等."""

    def _count(self, main_text: str, needle: str) -> int:
        return sum(1 for line in main_text.splitlines() if line.strip() == needle)

    def test_repeated_worker_does_not_duplicate_entries(self, in_dir):
        """Scenario: 重复新增同名 Worker 不产生重复条目."""
        runner = CliRunner()
        runner.invoke(zfc, ["--create", "proj"])
        os.chdir(in_dir / "proj")

        runner.invoke(zfc, ["--worker", "hello"])
        runner.invoke(zfc, ["--worker", "hello"])

        main = (in_dir / "proj" / "src" / "main.py").read_text(encoding="utf-8")
        assert self._count(main, "from workers.hello_worker import HelloWorker") == 1
        assert self._count(main, '("HelloWorker", HelloWorker),') == 1

    def test_repeated_worker_still_succeeds(self, in_dir):
        """Scenario: 重复新增同名 Worker 仍成功."""
        runner = CliRunner()
        runner.invoke(zfc, ["--create", "proj"])
        os.chdir(in_dir / "proj")

        assert runner.invoke(zfc, ["--worker", "hello"]).exit_code == 0
        assert runner.invoke(zfc, ["--worker", "hello"]).exit_code == 0

    def test_distinct_workers_coexist(self, in_dir):
        """Scenario: 不同名称的 Worker 互不影响."""
        runner = CliRunner()
        runner.invoke(zfc, ["--create", "proj"])
        os.chdir(in_dir / "proj")

        runner.invoke(zfc, ["--worker", "alpha"])
        runner.invoke(zfc, ["--worker", "beta"])

        main = (in_dir / "proj" / "src" / "main.py").read_text(encoding="utf-8")
        for name, cls in (("alpha", "Alpha"), ("beta", "Beta")):
            assert self._count(main, f"from workers.{name}_worker import {cls}Worker") == 1
            assert self._count(main, f'("{cls}Worker", {cls}Worker),') == 1

    def test_entry_remains_parseable_after_repeats(self, in_dir):
        """重复接线后入口仍可解析."""
        runner = CliRunner()
        runner.invoke(zfc, ["--create", "proj"])
        os.chdir(in_dir / "proj")

        for _ in range(3):
            runner.invoke(zfc, ["--worker", "hello"])

        ast.parse((in_dir / "proj" / "src" / "main.py").read_text(encoding="utf-8"))


# =============================================================================
# 5 · 文档记录的 CLI 选项面 MUST 与实现一致
# =============================================================================


def _strip_inline_comment(line: str) -> str:
    """剥掉行内 shell 注释.

    `#` 只有在**行首或前面是空白**时才是注释起始（与 shell 一致）；`myapp#x`
    是一个完整的词，不能切。若不剥掉，`zfc --create myapp  # 说明` 会被当成
    带 `#`、`->` 等参数的调用，而它在 shell 里本来是合法命令。
    """
    match = re.search(r"(?:^|\s)#", line)
    if match is None:
        return line.strip()
    return line[: match.start()].strip()


def _readme_cli_sequences() -> list:
    """取出 README 中**每一段**脚手架命令序列（每个围栏代码块视为一段）.

    只看围栏代码块内部：正文里为了解释而提到的选项名不是可执行的示例，不该参与
    校验，否则文档措辞的调整会误伤这条用例。

    行内注释按 shell 语义剥离：文档里 `zfc --create myapp  # 产出说明` 是**可执行**
    的写法，校验 MUST 与"照着敲进终端"一致，而不是拿 `str.split()` 当 shell。

    **每段是独立的一套步骤**：同一段示例在文档里会出现多次（英文与中文各一处），
    而每一段都应当从空目录开始——执行方 MUST 为每段分配独立目录，否则后一段会
    因为前一段留下的产物而失败（`--create` 对已存在的目标会明确拒绝）。

    Returns:
        序列列表；每个序列是 `(cd 序列, 命令行)` 的列表，按出现顺序
    """
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    sequences: list = []
    current: list = []
    in_fence = False
    cwd = []
    for raw in readme.splitlines():
        stripped = raw.strip()
        if stripped.startswith("```"):
            if in_fence and current:
                sequences.append(current)
            in_fence = not in_fence
            cwd = []
            current = []
            continue
        if not in_fence:
            continue
        if stripped.startswith("cd "):
            cwd.append(stripped[3:].strip())
        elif stripped.startswith(("zfc ", "zoo ")):
            command = _strip_inline_comment(stripped)
            if command:
                current.append((list(cwd), command))
    if current:
        sequences.append(current)
    return sequences


def _implemented_options() -> set:
    """实现中实际支持的选项名（含长短形式）."""
    options = set()
    for param in zfc.params:
        for opt in getattr(param, "opts", []):
            options.add(opt)
        for opt in getattr(param, "secondary_opts", []):
            options.add(opt)
    return options


class TestDocsMatchImplementation:
    """project-scaffolding: 文档记录的 CLI 选项面 MUST 与实现一致."""

    def test_readme_has_cli_examples(self):
        """前提：README 确实给出了脚手架示例，否则以下断言是空转."""
        assert _readme_cli_sequences(), "README 中找不到 zfc 示例"

    def test_inline_comments_are_stripped_from_examples(self):
        """示例按 shell 语义取值：行内注释 MUST 已被剥离.

        否则 `zfc --create myapp  # 产出说明` 会把注释内容当成命令参数，
        而它在终端里本来是合法命令——校验标准 MUST 与"照着敲"一致。
        """
        for sequence in _readme_cli_sequences():
            for _, command in sequence:
                assert "#" not in command, f"行内注释未被剥离：{command!r}"
                assert "->" not in command, f"注释残留被当成参数：{command!r}"

    def test_documented_options_all_exist(self):
        """Scenario: 文档不示范不存在的选项.

        断言的是"README 里的每个选项都在实现中存在"，因此 README 新增一个
        不存在的选项时本用例会失败——而不是只冻结当前这份名单。
        """
        implemented = _implemented_options()
        documented = set()
        for sequence in _readme_cli_sequences():
            for _, line in sequence:
                documented.update(re.findall(r"(?<![\w-])--[A-Za-z][\w-]*", line))

        assert documented, "README 的示例中未解析出任何选项"
        unknown = documented - implemented
        assert not unknown, f"README 示范了实现中不存在的选项：{sorted(unknown)}"

    def test_documented_examples_run_successfully(self, in_dir):
        """Scenario: 文档示例可被直接执行.

        按文档给出的 `cd` 顺序逐条执行，因此"文档里能跑"与"照着敲能跑"是同一件事。

        **每个序列在自己的沙箱目录里执行**：文档里同一段示例会出现多次（英文与中文
        各一处），而每段都应当从空目录开始——共用目录会让后一段撞上前一段留下的
        产物，从而把"文档的正确性"误测成"重复执行的幂等性"。
        """
        runner = CliRunner()
        base = os.getcwd()
        try:
            for index, sequence in enumerate(_readme_cli_sequences()):
                sandbox = os.path.join(base, f"seq_{index}")
                os.makedirs(sandbox, exist_ok=True)
                for cds, line in sequence:
                    os.chdir(os.path.join(sandbox, *cds) if cds else sandbox)
                    result = runner.invoke(zfc, line.split()[1:])
                    assert result.exit_code == 0, f"{line!r} 执行失败：{result.output}"
        finally:
            os.chdir(base)


# =============================================================================
# 6 · 脚手架产出的每个模块都会被入口加载
# =============================================================================


@pytest.fixture
def scaffold_project(tmp_path, monkeypatch):
    """生成一个脚手架项目并把工作目录切到项目根.

    返回项目根目录；用例结束后恢复工作目录、sys.path 与生成的模块缓存。
    """
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(zfc, ["--create", "app"])
    assert result.exit_code == 0, result.output

    project = tmp_path / "app"
    monkeypatch.chdir(project)
    yield project
    _reset_generated_state(project / "src")


def _noop_run(*_args, **_kwargs):
    """替换 `Master.run`，让生成的入口跑完注册流程而不进入无限循环."""
    return


def _boot(entry, monkeypatch):
    """按生成入口的方式启动一次，但不进入 master.run() 的无限循环."""
    from zoo_framework.core.master import Master

    monkeypatch.setattr(Master, "run", _noop_run)
    entry.main()


class TestGeneratedModulesAreLoaded:
    """project-scaffolding: MUST NOT 存在生成了但从不被加载的模块."""

    def test_every_demo_module_is_on_the_load_path(self, scaffold_project, monkeypatch):
        """Scenario: 不存在从不被加载的生成模块.

        `conf/` / `params/` / `events/` 三个目录都产出了模块，从入口出发追踪加载时
        必须每个都被加载——空包或死文件都不算自洽。
        """
        entry = _import_entry(scaffold_project)

        _boot(entry, monkeypatch)

        for name in GENERATED_MODULE_NAMES:
            assert name in sys.modules, f"{name} 生成了但从未被加载"

    def test_conf_hook_is_actually_invoked(self, scaffold_project, monkeypatch):
        """conf 演示模块的配置钩子由 Master 构造时执行.

        断言的是模块自己的副作用，不是"注册表里有这个 topic"：后者在残留注册的
        情况下也会为真，会掩盖模板失效。
        """
        entry = _import_entry(scaffold_project)
        conf_module = importlib.import_module("conf.demo_conf")
        assert conf_module.executed is False, "前提：钩子尚未执行"

        _boot(entry, monkeypatch)

        assert conf_module.executed is True, "conf 钩子没有被 Master 调用"

    def test_params_demo_resolves_config_json(self, scaffold_project, monkeypatch):
        """params 演示模块取到的是配置文件里声明的值.

        改写生成的 `config.json` 再断言，因此"取到了配置"与"取了模板默认值"能被
        区分开——不必在用例里硬编码模板的默认值。
        """
        config_path = scaffold_project / "config.json"
        declared = json.loads(config_path.read_text(encoding="utf-8"))
        declared["demo"]["greeting"] = "resolved-from-config"
        config_path.write_text(json.dumps(declared), encoding="utf-8")

        entry = _import_entry(scaffold_project)
        _boot(entry, monkeypatch)

        params_module = importlib.import_module("params.demo_params")
        assert params_module.DemoParams.GREETING == "resolved-from-config"

    def test_events_demo_receives_dispatched_event(self, scaffold_project, monkeypatch):
        """events 演示模块注册的反应器能收到事件.

        主题与通道名取自模板（`demo_topic` / `demo_channel`）；模板改了名字这里就该红，
        这正是"模板与运行时对不上"要暴露的时刻。
        """
        entry = _import_entry(scaffold_project)
        _boot(entry, monkeypatch)

        from zoo_framework.event.event_channel_manager import EventChannelManager
        from zoo_framework.fifo.node import EventNode

        events_module = importlib.import_module("events.demo_event")
        before = len(events_module.received)

        EventChannelManager().perform_event(EventNode("demo_topic", "payload-42", "demo_channel"))

        assert events_module.received[before:] == ["payload-42"], "事件未送达演示反应器"

    def test_assertions_survive_prior_runs(self, tmp_path, monkeypatch):
        """连续生成两个项目，各自断言**本次**导入的模块对象.

        框架的配置注册表是进程级全局，前一次生成的模块会留在里面。只断言"注册表里
        有这个 topic"会被残留蒙混过去；断言本次导入的模块自己的副作用才作数。
        """
        runner = CliRunner()

        for index in range(2):
            base = tmp_path / f"run{index}"
            base.mkdir()
            monkeypatch.chdir(base)
            assert runner.invoke(zfc, ["--create", "app"]).exit_code == 0

            project = base / "app"
            monkeypatch.chdir(project)
            try:
                entry = _import_entry(project)
                _boot(entry, monkeypatch)

                conf_module = sys.modules["conf.demo_conf"]
                assert conf_module.executed is True, f"第 {index + 1} 次生成的 conf 钩子未被执行"
            finally:
                _reset_generated_state(project / "src")
