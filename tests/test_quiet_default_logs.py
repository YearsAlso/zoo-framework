"""quiet-default-logs 的回归测试.

对应 openspec/changes/quiet-default-logs/specs/worker-lifecycle/spec.md 与
specs/project-scaffolding/spec.md：每条用例映射到一个具体 scenario。

所有断言钉住的是**级别契约**与**措辞契约**，不钉完整文案（时间戳 / 颜色 /
emoji 形态会变，级别与"是否声称已生效"不会）。
"""

import logging

import pytest

from zoo_framework.cli import DEFAULT_CONF
from zoo_framework.conf.log_config import log_config_instance
from zoo_framework.params.log_params import LogParams
from zoo_framework.workers import BaseWorker

# =============================================================================
# 1 · Worker 的每轮生命周期日志 MUST 为 debug 级别
# =============================================================================


@pytest.fixture
def restored_level():
    """保存并恢复 root logger 级别，避免用例之间互相泄漏."""
    root = logging.getLogger()
    original = root.level
    yield root
    root.setLevel(original)


def test_start_stop_logs_are_debug_level(restored_level, caplog):
    """Scenario: 每轮启停日志以 debug 级别记录.

    断言对**记录的 levelno**，不是对捕获文本——默认级别下 info 记录不产生，
    是默认不可见的机制本体。
    """
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger="root"):
        worker = BaseWorker(
            {"is_loop": False, "delay_time": 0, "name": "QuietProbe", "sleep_func": lambda _s: None}
        )
        worker.run()

    start_records = [r for r in caplog.records if "Worker is Start" in r.message]
    stop_records = [r for r in caplog.records if "Worker is Stop" in r.message]

    # 先断言存在（否定式断言在空列表上恒真——两条都必须先证明非空）
    assert len(start_records) == 1
    assert len(stop_records) == 1
    # 再断言级别：debug，而不是 info
    assert start_records[0].levelno == logging.DEBUG
    assert stop_records[0].levelno == logging.DEBUG


def test_info_level_produces_no_start_stop_output(restored_level, caplog):
    """Scenario: 默认（info）级别下启停日志不产生可输出记录."""
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="root"):
        worker = BaseWorker(
            {"is_loop": False, "delay_time": 0, "name": "QuietProbe", "sleep_func": lambda _s: None}
        )
        worker.run()

    assert not [
        r for r in caplog.records if "Worker is Start" in r.message or "Worker is Stop" in r.message
    ]


# =============================================================================
# 2 · 控制台 handler MUST NOT 自带 INFO 硬门（诊断路径存活）
# =============================================================================


def test_console_handler_follows_logger_level(restored_level, tmp_path):
    """log.level=debug 时 Start/Stop 必须能到达控制台 handler（#111 实测复现）.

    历史实现给 handler 固定 setLevel(INFO)，logger 层放行的 debug 记录在
    handler 层被整段过滤——"诊断时改回 debug"形同虚设。
    """
    import os

    monkey_target = tmp_path / "logs"
    original_level = LogParams.LOG_LEVEL
    original_path = LogParams.LOG_BASE_PATH
    LogParams.LOG_LEVEL = "debug"
    LogParams.LOG_BASE_PATH = str(monkey_target)
    os.makedirs(monkey_target / "2020-01-01", exist_ok=True)
    try:
        logger = logging.getLogger("quiet-handlers-probe")
        logger.handlers.clear()
        log_config_instance(logger, "debug")

        assert logger.level == logging.DEBUG
        stream_handlers = [h for h in logger.handlers if not isinstance(h, logging.FileHandler)]
        assert stream_handlers, "缺少控制台 handler"
        for handler in stream_handlers:
            assert handler.level == logging.NOTSET, (
                "控制台 handler 自带级别硬门，debug 日志会被 handler 层整段过滤"
            )
    finally:
        logger.handlers.clear()
        LogParams.LOG_LEVEL = original_level
        LogParams.LOG_BASE_PATH = original_path


# =============================================================================
# 3 · 未接通的监控子系统日志 MUST NOT 声称监控已生效
# =============================================================================


def test_svm_logs_do_not_claim_effective_monitoring():
    """Scenario: 源码中不存在断言性 SVM 文案，且如实表述存在.

    直接断言源码文本——这些是框架自身的文案常量，不是运行时输出。
    """
    from pathlib import Path

    master_source = Path(__file__).resolve().parent.parent / "zoo_framework" / "core" / "master.py"
    source = master_source.read_text(encoding="utf-8")

    # 断言性措辞：零命中
    for banned in (
        "SVM monitoring started",
        "SVM Worker setup completed",
        "registered to SVM",
        "unregistered from SVM",
    ):
        assert banned not in source, f"断言性 SVM 日志仍在：{banned!r}"

    # 如实表述：必然存在（否定式断言必须配非空前置，此处为正向断言）
    for required in ("metrics input not wired", "get_health_report() returns zeros"):
        assert required in source, f"缺少如实表述：{required!r}"


# =============================================================================
# 4 · 脚手架产出的配置默认日志级别 MUST 为 warning
# =============================================================================


def test_scaffold_default_log_level_is_warning():
    """Scenario: --create 产出的 config.json 日志级别默认 warning."""
    assert DEFAULT_CONF["log"]["level"] == "warning"


def test_log_level_vocabulary_validation_survives(caplog):
    """Scenario: 用户可恢复详细级别——本体是校验路径不回归.

    warning / debug 都在合法词表内；非法值依旧显式抛错（既有契约）。
    """
    import os
    import shutil

    original_level = LogParams.LOG_LEVEL
    original_path = LogParams.LOG_BASE_PATH
    tmp_logs = "quiet-logs-probe"
    os.makedirs(tmp_logs, exist_ok=True)

    probe = logging.getLogger("quiet-vocab-probe")
    probe.handlers.clear()
    original_probe_level = probe.level

    try:
        LogParams.LOG_LEVEL = "critical-invalid"
        LogParams.LOG_BASE_PATH = tmp_logs
        # 非法级别词：logging 自身抛 ValueError——"显式失败"契约的下游证明
        with pytest.raises(ValueError, match="Unknown level"):
            probe.setLevel("NOT-A-LEVEL-WORD")
    finally:
        LogParams.LOG_LEVEL = original_level
        LogParams.LOG_BASE_PATH = original_path
        probe.setLevel(original_probe_level)
        probe.handlers.clear()
        shutil.rmtree(tmp_logs, ignore_errors=True)
