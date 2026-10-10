"""AOP 语义的确定性（变更 aop-determinism / issue #51）.

两条顺序耦合的失败模式 MUST 大声：
1. `@params` 在"从未读到配置"的世代解析过、而 Master 随后读到了配置 ⇒ 构造失败并点名
2. `@configure` 在 Master 消费注册表之后注册 ⇒ 大声失败（该注册永远不会被调用）

合法形态 MUST NOT 被误伤：无配置文件（全默认）运行、参数类在配置可见处首次导入。
"""

import json

import pytest

# 注：`import a.b.c as m` 会被包面的同名函数遮蔽（aop/__init__ 导入了函数
# params/configure），故按属性直接导入目标对象。
from zoo_framework.core import Master, param
from zoo_framework.core.aop.configure import config_funcs, configure, seal_config_funcs
from zoo_framework.core.aop.params import _resolved_generation, stale_param_classes
from zoo_framework.core.aop.params import params as params_decorator
from zoo_framework.core.master import MasterConfig
from zoo_framework.core.params_factory import ParamsFactory


def _master() -> Master:
    """不开 SVM 监控线程的 Master 构造（用例只关心构造期核对）."""
    return Master(MasterConfig(enable_svm=False))


def _define_params_class(name: str, path: str, default: str):
    """在测试现场定义一个 @params 类（限定名唯一，避免跨用例缓存命中）."""
    ns = {"KEY": param(value=path, default=default)}
    cls = type(name, (), ns)
    cls.__module__ = f"tests.test_aop_determinism.{name}"
    return params_decorator(cls)


class TestParamsOrderLoudFailure:
    def test_frozen_class_named_when_config_arrives_later(self, tmp_path, monkeypatch):
        """验收构造案例：先导入参数模块（无配置可见）、后构造 Master（有配置）⇒ 必须失败."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(ParamsFactory, "config_params", {})

        frozen = _define_params_class("FrozenOrderParams", "alpha:key", "DEFAULT")
        assert frozen.KEY == "DEFAULT"

        (tmp_path / "config.json").write_text(
            json.dumps({"alpha": {"key": "FROM_CONFIG"}}), encoding="utf-8"
        )

        with pytest.raises(RuntimeError, match="frozen at the defaults"):
            _master()

    def test_no_config_file_is_a_legal_all_defaults_run(self, tmp_path, monkeypatch):
        """全程没有配置文件：全默认是合法形态，核对 MUST NOT 触发."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(ParamsFactory, "config_params", {})

        cls = _define_params_class("NoConfigParams", "alpha:key", "DEFAULT")
        master = _master()  # 不抛
        assert cls.KEY == "DEFAULT"
        assert master is not None

    def test_class_resolved_with_visible_config_is_not_stale(self, tmp_path, monkeypatch):
        """参数类首次解析时 config.json 已在 cwd：取值正确，不该被冻结核对点名."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(ParamsFactory, "config_params", {})
        (tmp_path / "config.json").write_text(
            json.dumps({"alpha": {"key": "FROM_CONFIG"}}), encoding="utf-8"
        )

        cls = _define_params_class("FreshOrderParams", "alpha:key", "DEFAULT")
        assert cls.KEY == "FROM_CONFIG"

        _master()  # 不抛：解析发生在配置可见之后

    def test_stale_list_only_zero_generation_entries(self):
        """判据是 gen == 0，不是 gen < 当前——正世代解析过的条目不得入列."""
        snapshot = dict(_resolved_generation)
        try:
            _resolved_generation.clear()
            _resolved_generation["a.InTime"] = 1
            _resolved_generation["b.Frozen"] = 0
            assert stale_param_classes() == ["b.Frozen"]
        finally:
            _resolved_generation.clear()
            _resolved_generation.update(snapshot)


class TestConfigureSeal:
    def test_registration_before_seal_succeeds_silently(self):
        def hook():
            pass

        configure(topic="det_before_seal")(hook)
        assert config_funcs.get("det_before_seal") is hook

    @staticmethod
    def _capture_warnings(monkeypatch):
        # `import ... as` 会被包面同名函数遮蔽，改从 sys.modules 取真模块对象
        import sys

        configure_module = sys.modules["zoo_framework.core.aop.configure"]

        logged: list[str] = []

        class _CapturingLog:
            @staticmethod
            def warning(message, *_args, **_kwargs):
                logged.append(str(message))

        monkeypatch.setattr(configure_module, "LogUtils", _CapturingLog)
        return logged

    def test_registration_after_seal_is_loud_but_still_recorded(self, monkeypatch):
        """封后注册：登记照旧（给下一个 Master 消费）但 MUST 大声告警，不再静默."""
        logged = self._capture_warnings(monkeypatch)
        seal_config_funcs()

        def late():
            pass

        configure(topic="det_late")(late)

        assert config_funcs.get("det_late") is late
        assert any("registered after a Master" in w for w in logged), "封后注册未出声"

    def test_master_consumption_warns_late_reregistration(self, tmp_path, monkeypatch):
        """同进程重复运行入口（重新导入+重新注册+新 Master）：合法，但告警可见."""
        logged = self._capture_warnings(monkeypatch)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(ParamsFactory, "config_params", {})

        _master()  # 消费并封

        def late():
            pass

        configure(topic="det_after_master")(late)

        assert any("det_after_master" in w for w in logged)
        # 下一个 Master 会消费它——行为与脚手架重复运行契约一致
        _master()
