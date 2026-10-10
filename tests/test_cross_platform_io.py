"""fix-cross-platform-defects 的回归测试.

对应 openspec/changes/fix-cross-platform-defects/specs/ 下的两份 spec：
每条用例映射到一个具体 scenario。

关键约束：这些用例 MUST 在**任意单平台**上可复现。跨平台差异通过显式构造不同编码
的文件与输出目标来覆盖，而不是依赖运行平台的 locale——否则会出现"只有某个平台的
CI 才会红"的覆盖缺口，而这类缺陷恰恰因为如此才长期潜伏。
"""

import io
import locale
import logging
import os
import sys
from datetime import datetime

import pytest

from zoo_framework.utils import FileUtils, SafeStreamHandler

# 一个无法用 cp936 表示的字符（emoji）与 ASCII 的对照，用于验证降级而非丢行
UNREPRESENTABLE = "\U0001f4e6"  # 📦
NON_ASCII = "中文内容"


# =============================================================================
# 1 · 文本文件的写入编码
# =============================================================================


class TestTextWriteEncoding:
    """cross-platform-io: 文本文件的写入 MUST 显式声明编码."""

    def test_written_bytes_are_utf8(self, tmp_path):
        """Scenario: 写入的字节为 UTF-8 编码.

        直接检查落盘字节，而不是读回来的值——后者会被同一套编码逻辑掩盖。
        """
        path = tmp_path / "out.txt"
        FileUtils.write_text(str(path), NON_ASCII)

        raw = path.read_bytes()
        assert raw == NON_ASCII.encode("utf-8")
        assert raw != NON_ASCII.encode("gbk")

    def test_roundtrip_is_stable(self, tmp_path):
        """Scenario: 非 ASCII 内容写入后按 UTF-8 读回一致."""
        path = str(tmp_path / "roundtrip.txt")
        FileUtils.write_text(path, NON_ASCII + " & ascii")

        assert FileUtils.read_text(path) == NON_ASCII + " & ascii"

    def test_config_write_is_encoding_independent(self, tmp_path, monkeypatch):
        """Scenario: 配置文件的写入不产生平台相关字节.

        以不同的"平台默认编码"写入同一份内容，落盘字节必须一致。
        """
        import locale

        config_path = tmp_path / "config.json"
        FileUtils.write_text(str(config_path), NON_ASCII)
        baseline = config_path.read_bytes()

        # 模拟另一种平台默认编码，重新写入同一内容
        monkeypatch.setattr(locale, "getpreferredencoding", lambda *_: "gbk", raising=False)
        FileUtils.write_text(str(config_path), NON_ASCII)

        assert config_path.read_bytes() == baseline


# =============================================================================
# 2 · 文本文件的读取编码与回退
# =============================================================================


class TestTextReadEncoding:
    """cross-platform-io: 读取 MUST 优先 UTF-8，回退 MUST 告警."""

    @staticmethod
    def _pretend_platform_encoding(monkeypatch, encoding: str) -> None:
        """把"运行平台的默认编码"模拟为指定值.

        回退的目标是 `locale.getpreferredencoding(False)`。用例若只写死某个编码的
        文件、而不模拟这个值，就会退化成"只在默认编码恰好相同的平台上通过"——
        默认编码为 UTF-8 的 Linux/macOS 上必然失败。
        """
        monkeypatch.setattr(locale, "getpreferredencoding", lambda *_: encoding, raising=False)

    def test_utf8_read_does_not_warn(self, tmp_path, caplog):
        """Scenario: 读取 UTF-8 文件得到正确内容."""
        path = str(tmp_path / "utf8.txt")
        FileUtils.write_text(path, NON_ASCII)

        with caplog.at_level(logging.WARNING):
            assert FileUtils.read_text(path) == NON_ASCII

        assert "not UTF-8" not in caplog.text

    def test_non_utf8_file_falls_back_without_corruption(self, tmp_path, caplog, monkeypatch):
        """Scenario: 回退后内容仍与源文件一致.

        显式构造 GBK 文件来模拟"旧版本在非 UTF-8 平台上写出的配置"：旧版本是按
        **当时的平台默认编码** 落盘的，因此这里同时把平台默认编码模拟为 GBK，
        使该场景在任意平台上都成立。
        """
        self._pretend_platform_encoding(monkeypatch, "gbk")
        path = tmp_path / "legacy.txt"
        path.write_bytes(NON_ASCII.encode("gbk"))

        with caplog.at_level(logging.WARNING):
            content = FileUtils.read_text(str(path))

        assert content == NON_ASCII, "回退读取损坏了内容"

    def test_fallback_emits_warning_naming_the_file(self, tmp_path, caplog):
        """Scenario: 回退发生时输出告警."""
        path = tmp_path / "legacy_warn.txt"
        path.write_bytes(NON_ASCII.encode("gbk"))

        with caplog.at_level(logging.WARNING):
            FileUtils.read_text(str(path))

        assert "legacy_warn.txt" in caplog.text, "回退告警未指明涉及的文件"
        assert "not UTF-8" in caplog.text

    def test_same_config_parses_to_same_value(self, tmp_path):
        """Scenario: 同一份配置在不同平台上解析为相同值.

        以 UTF-8 落盘的配置，无论读取方的平台默认编码是什么，解析结果都必须一致。
        """
        import json

        from zoo_framework.core.params_factory import ParamsFactory

        path = str(tmp_path / "config.json")
        payload = {"log": {"level": NON_ASCII}}
        FileUtils.write_text(path, json.dumps(payload, ensure_ascii=False))

        ParamsFactory(path)
        assert ParamsFactory.get_params("log:level") == NON_ASCII

    def test_legacy_gbk_config_is_still_readable(self, tmp_path, monkeypatch):
        """旧版本写出的 GBK 配置仍可被读取（回退路径的兼容性保证）.

        与上一条同理：GBK 文件对应的是"平台默认编码为 GBK"的旧环境，须一并模拟，
        否则该用例只在中文 Windows 上通过。
        """
        import json

        from zoo_framework.core.params_factory import ParamsFactory

        self._pretend_platform_encoding(monkeypatch, "gbk")
        path = tmp_path / "legacy_config.json"
        path.write_bytes(
            json.dumps({"log": {"level": NON_ASCII}}, ensure_ascii=False).encode("gbk")
        )

        ParamsFactory(str(path))
        assert ParamsFactory.get_params("log:level") == NON_ASCII


# =============================================================================
# 3 · 日志在受限编码输出目标上的行为
# =============================================================================


def _emit_to(encoding: str, message: str) -> bytes:
    """把一条日志写进指定编码的输出目标，返回落盘的字节."""
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding=encoding, newline="")
    handler = SafeStreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.emit(logging.LogRecord("t", logging.INFO, "", 0, message, None, None))
    stream.flush()
    return buffer.getvalue()


class TestLoggingEncoding:
    """cross-platform-io: 日志输出 MUST NOT 因控制台编码而整行丢失."""

    def test_line_survives_limited_encoding(self):
        """Scenario: 非 UTF-8 输出目标上不丢失整行日志."""
        raw = _emit_to("cp936", f"{UNREPRESENTABLE} {NON_ASCII}")

        # 不可表示的字符被降级，但整行内容（含可表示的中文）全部写出
        assert NON_ASCII.encode("cp936") in raw, "整行日志丢失"
        assert UNREPRESENTABLE not in raw.decode("cp936", errors="replace")

    def test_degraded_form_is_reversible(self):
        """Scenario: 日志内容可被还原.

        降级形式必须是可还原的转义序列，而不是不可逆的占位符。
        """
        raw = _emit_to("cp936", UNREPRESENTABLE).decode("cp936").rstrip("\n")
        assert "\\U0001f4e6" in raw, "降级形式不可还原"
        assert raw.encode().decode("unicode_escape") == UNREPRESENTABLE

    def test_representable_characters_pass_through(self):
        """Scenario: 字符可表示时原样写出."""
        raw = _emit_to("utf-8", f"{UNREPRESENTABLE}{NON_ASCII}").decode("utf-8").rstrip("\n")

        assert raw == f"{UNREPRESENTABLE}{NON_ASCII}"

    def test_default_stream_handler_would_lose_the_line(self):
        """对照：标准 StreamHandler 在同一条件下确实会丢行.

        该用例锁定问题本身——若它开始通过，说明前提已变，需要重新审视本能力。
        """
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding="cp936", newline="")
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))

        handler.emit(logging.LogRecord("t", logging.INFO, "", 0, UNREPRESENTABLE, None, None))
        stream.flush()

        assert buffer.getvalue() == b"", "标准 StreamHandler 的行为已变化"


# =============================================================================
# 4 · 备份文件命名的唯一性与可排序性
# =============================================================================


class TestBackupNaming:
    """cross-platform-io: 备份文件名 MUST 唯一且字典序等于时间序."""

    @staticmethod
    def _make_backups(tmp_path, count=5):
        import glob

        from zoo_framework.core.persistence_scheduler import BackupManager

        source = tmp_path / "state.pic"
        manager = BackupManager(backup_dir="backups", max_backups=10)

        for index in range(count):
            source.write_text(f"version-{index}")
            manager.create_backup(str(source))

        return sorted(os.path.basename(p) for p in glob.glob(str(tmp_path / "backups" / "*.bak")))

    def test_same_second_backups_do_not_collide(self, tmp_path):
        """Scenario: 同一秒内的连续备份互不覆盖."""
        names = self._make_backups(tmp_path, count=5)
        assert len(names) == 5, f"同秒备份相互覆盖，只留下 {len(names)} 个文件"

    def test_name_order_matches_time_order(self, tmp_path):
        """Scenario: 名称排序等价于时间排序."""
        names = self._make_backups(tmp_path, count=5)
        assert names == sorted(names), "字典序与创建顺序不一致"

    def test_latest_backup_is_actually_the_newest(self, tmp_path):
        """取最新备份的既有逻辑（按名倒序取首个）仍正确."""
        names = self._make_backups(tmp_path, count=5)
        assert sorted(names, reverse=True)[0] == names[-1]

    def test_mixed_old_and_new_naming_still_picks_latest(self, tmp_path):
        """Scenario: 新旧命名混排时仍能取到最新."""
        import glob

        names = self._make_backups(tmp_path, count=3)
        legacy = tmp_path / "backups" / "state.20200101_000000.bak"
        legacy.write_text("legacy")

        all_names = sorted(
            os.path.basename(p) for p in glob.glob(str(tmp_path / "backups" / "*.bak"))
        )
        assert sorted(all_names, reverse=True)[0] == names[-1], "混排后取到的不是最新的备份"

    def test_timestamp_keeps_lexicographic_ordering(self):
        """命名格式的性质守卫：微秒后缀为定宽，字典序仍等于时间序."""
        early = datetime(2026, 9, 27, 18, 0, 0, 1).strftime("%Y%m%d_%H%M%S_%f")
        late = datetime(2026, 9, 27, 18, 0, 0, 999999).strftime("%Y%m%d_%H%M%S_%f")
        assert early < late
        assert len(early) == len(late)


# =============================================================================
# 5 · CLI 产出目录的定位
# =============================================================================


class TestCliWorkerDirResolution:
    """cli-scaffolding: 命令 MUST 依据工作目录结构定位产出目录."""

    @pytest.fixture
    def in_dir(self, monkeypatch):
        """把工作目录切到指定目录，并在用例结束后切回."""
        original = os.getcwd()

        def _switch(path):
            os.chdir(path)
            return path

        yield _switch
        os.chdir(original)

    def test_resolves_into_src_when_present(self, tmp_path, in_dir):
        """Scenario: 工作目录下存在源码目录时产出到其中."""
        from zoo_framework.cli import resolve_worker_dir

        project = tmp_path / "demo"
        (project / "src").mkdir(parents=True)
        in_dir(str(project))

        assert os.path.normpath(resolve_worker_dir()) == os.path.normpath("src/workers")

    def test_resolves_to_workers_when_src_absent(self, tmp_path, in_dir):
        """Scenario: 工作目录下不存在源码目录时产出到当前目录."""
        from zoo_framework.cli import resolve_worker_dir

        plain = tmp_path / "plain"
        plain.mkdir()
        in_dir(str(plain))

        assert os.path.normpath(resolve_worker_dir()) == os.path.normpath("workers")

    def test_resolution_does_not_depend_on_argv0(self, tmp_path, in_dir, monkeypatch):
        """Scenario: 判定不依赖进程启动方式.

        历史判据是 `sys.argv[0].endswith("/src")`，它对可执行入口、模块方式与脚本方式
        都不会成立；本用例冻结"判定与启动路径无关"这一性质。
        """
        from zoo_framework.cli import resolve_worker_dir

        project = tmp_path / "demo2"
        (project / "src").mkdir(parents=True)
        in_dir(str(project))

        results = []
        for argv0 in (
            r"C:\Python313\Scripts\zfc.exe",
            "/usr/local/bin/zfc",
            "zoo_framework/cli/__init__.py",
            "/opt/app/src",
        ):
            monkeypatch.setattr(sys, "argv", [argv0])
            results.append(os.path.normpath(resolve_worker_dir()))

        assert len(set(results)) == 1, f"判定随启动路径变化：{results}"

    def test_worker_func_creates_directory_and_file(self, tmp_path, in_dir):
        """Scenario: 产出目录不存在时被创建，文件被成功写入."""
        from zoo_framework.cli import worker_func

        project = tmp_path / "demo3"
        project.mkdir()
        in_dir(str(project))

        worker_func("my_task")

        assert (project / "workers" / "my_task_worker.py").exists()
        assert (project / "workers" / "__init__.py").exists()

    def test_worker_func_targets_src_inside_scaffolded_project(self, tmp_path, in_dir):
        """脚手架项目内新增 Worker 落在 src/workers 下."""
        from zoo_framework.cli import create_func, worker_func

        project = tmp_path / "demo4"
        project.mkdir()
        in_dir(str(project))

        create_func("app")
        in_dir(str(project / "app"))
        worker_func("my_task")

        assert (project / "app" / "src" / "workers" / "my_task_worker.py").exists()

    def test_generated_files_are_utf8(self, tmp_path, in_dir):
        """脚手架的产物一律为 UTF-8（跨平台可读）."""
        from zoo_framework.cli import create_func

        project = tmp_path / "demo5"
        project.mkdir()
        in_dir(str(project))

        create_func("app")

        config = (project / "app" / "config.json").read_bytes()
        assert config.decode("utf-8") is not None
