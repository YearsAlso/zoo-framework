"""scoped-container 的 config-resolution 组回归测试.

对应 openspec/changes/scoped-container/specs/config-resolution/spec.md：
每条用例映射到一个具体 scenario。

用例分两类：
- 缺陷复现（先红）：同名参数类复用他人配置值，修复后转绿。
- 契约守护（本就绿）：别名回退顺序与"已配置假值 ≠ 缺失"——这两条语义刚获得，
  尚无 spec 覆盖，此处固定下来防止回归。
"""

import importlib

import pytest

from zoo_framework.core import aop
from zoo_framework.core.aop.params import params as params_decorator
from zoo_framework.core.params_factory import ParamsFactory
from zoo_framework.core.params_path import ParamsPath

# 注意：不能写 `import zoo_framework.core.aop.params as m`——包 __init__ 里的
# `from .params import params` 把子模块属性覆盖成了函数，该写法会绑定到函数。
# 而给函数 setattr 会静默成功，导致"清缓存"实际无效。必须经 importlib 取模块。
params_module = importlib.import_module("zoo_framework.core.aop.params")


def _params_class(name, path, default="", aliases=None):
    """构造一个具名参数类并交给 `@params` 解析.

    名字逐用例唯一，避免不同用例共享同一个缓存键而互相干扰。
    """
    cls = type(name, (), {"KEY": ParamsPath(value=path, default=default, aliases=aliases)})
    return params_decorator(cls)


@pytest.fixture
def config(monkeypatch):
    """把配置来源与解析缓存都替换为受控状态.

    - `ParamsFactory.config_params`：`get_params` 实际读取的配置字典
    - `aop.params.config_params`：`@params` 的解析缓存，逐个用例清空，
      避免进程级缓存在用例之间串扰
    """
    config_dict = {}
    monkeypatch.setattr(ParamsFactory, "config_params", config_dict, raising=False)
    monkeypatch.setattr(params_module, "config_params", {}, raising=False)
    return config_dict


# =============================================================================
# 缺陷复现：解析缓存以裸类名做键 → 同名参数类复用他人配置值
# =============================================================================


def _define_alpha(params_decorator, ParamsPath):
    """在独立作用域内定义一个名为 SameNameParams 的参数类.

    限定名含所在函数，故与下一个 helper 里的同名类属于不同定义位置。
    """

    @params_decorator
    class SameNameParams:
        KEY = ParamsPath(value="alpha:key", default="ALPHA_DEFAULT")

    return SameNameParams


def _define_beta(params_decorator, ParamsPath):
    """定义另一个名为 SameNameParams 的参数类，指向不同的配置路径."""

    @params_decorator
    class SameNameParams:
        KEY = ParamsPath(value="beta:key", default="BETA_DEFAULT")

    return SameNameParams


class TestCacheKeyUniqueness:
    """config-resolution: 参数类解析缓存 MUST 以进程内唯一标识为键."""

    def test_same_named_params_classes_resolve_independently(self, config):
        """Scenario: 同名参数类各自独立解析."""
        config["alpha"] = {"key": "from-alpha"}
        config["beta"] = {"key": "from-beta"}

        alpha = _define_alpha(params_decorator, ParamsPath)
        beta = _define_beta(params_decorator, ParamsPath)

        assert alpha.KEY == "from-alpha"
        assert beta.KEY == "from-beta", (
            f"同名参数类复用了他人配置值：期望 'from-beta'，实际 {beta.KEY!r}"
        )

    def test_same_named_class_does_not_skip_resolution(self, config):
        """Scenario: 同名参数类不会跳过解析."""
        config["alpha"] = {"key": "from-alpha"}
        config["beta"] = {"key": "from-beta"}

        alpha = _define_alpha(params_decorator, ParamsPath)
        beta = _define_beta(params_decorator, ParamsPath)

        # 后定义者必须拿到自己的配置路径解析结果，而不是前者的类
        assert beta is not alpha
        assert not isinstance(beta.KEY, ParamsPath), "解析被跳过，类属性仍是 ParamsPath 句柄"

    def test_same_params_class_resolves_once(self, config):
        """Scenario: 同一参数类重复导入只解析一次."""
        config["alpha"] = {"key": "from-alpha"}

        first = _define_alpha(params_decorator, ParamsPath)
        resolved_value = first.KEY
        config["alpha"] = {"key": "changed-after-resolution"}

        second = _define_alpha(params_decorator, ParamsPath)

        assert second is first
        assert resolved_value == second.KEY, "同一参数类被重复解析"


# =============================================================================
# 契约守护：别名回退顺序
# =============================================================================


class TestAliasFallback:
    """config-resolution: 别名回退 MUST 按声明顺序生效."""

    PATH = "primary:key"
    DEFAULT = "THE_DEFAULT"
    ALIASES = ["legacy:key", "older:key"]

    def test_primary_wins_when_present(self, config):
        """Scenario: 首选路径存在时不使用别名."""
        config["primary"] = {"key": "from-primary"}
        config["legacy"] = {"key": "from-legacy"}
        cls = _params_class("AliasPrimaryWins", self.PATH, self.DEFAULT, self.ALIASES)
        assert cls.KEY == "from-primary"

    def test_falls_back_to_alias_when_primary_missing(self, config):
        """Scenario: 首选路径缺失时回退到别名."""
        config["legacy"] = {"key": "from-legacy"}
        cls = _params_class("AliasFallback", self.PATH, self.DEFAULT, self.ALIASES)
        assert cls.KEY == "from-legacy"

    def test_default_when_all_candidates_missing(self, config):
        """Scenario: 全部候选缺失时使用默认值."""
        cls = _params_class("AliasAllMissing", self.PATH, self.DEFAULT, self.ALIASES)
        assert cls.KEY == self.DEFAULT

    def test_multiple_aliases_follow_declared_order(self, config):
        """Scenario: 多个别名按声明顺序回退."""
        config["legacy"] = {"key": "from-legacy"}
        config["older"] = {"key": "from-older"}
        cls = _params_class("AliasOrder", self.PATH, self.DEFAULT, self.ALIASES)
        # legacy 在 ALIASES 中先于 older，故取 legacy
        assert cls.KEY == "from-legacy"


# =============================================================================
# 契约守护：已配置的假值 ≠ 缺失
# =============================================================================


class TestFalsyVersusMissing:
    """config-resolution: 已配置的假值 MUST 与缺失区分."""

    def test_configured_false_is_honoured(self, config):
        """Scenario: 配置为 False 时得到 False."""
        config["flag"] = False

        @params_decorator
        class BoolParams:
            KEY = ParamsPath(value="flag", default=True)

        assert BoolParams.KEY is False

    def test_configured_zero_is_honoured(self, config):
        """Scenario: 配置为 0 时得到 0."""
        config["num"] = 0

        @params_decorator
        class NumParams:
            KEY = ParamsPath(value="num", default=5)

        assert NumParams.KEY == 0

    def test_configured_empty_string_is_honoured(self, config):
        """Scenario: 配置为空字符串时得到空字符串."""
        config["text"] = ""

        @params_decorator
        class TextParams:
            KEY = ParamsPath(value="text", default="fallback")

        assert TextParams.KEY == ""


# =============================================================================
# 新增参数键：事件批量投递（optimize-event-dispatch-batching 任务 1.2）
# =============================================================================


class TestEventBatchingKeys:
    """新键走既有解析路径：嵌套键生效、缺省给保守默认、假值不误伤开关.

    下面的声明与 `zoo_framework/params/event_params.py` 的键路径、默认值逐字对应；
    末条用真类把这份一致性钉住（防声明漂移）。
    """

    @staticmethod
    def _declare_batching():
        @params_decorator
        class EventBatchingParams:
            DISPATCH_BATCHING_ENABLED = ParamsPath(
                value="event:dispatchBatchingEnabled", default=False
            )
            BATCH_MAX_SIZE = ParamsPath(value="event:batchMaxSize", default=64)

        return EventBatchingParams

    def test_nested_config_is_resolved(self, config):
        """嵌套键（`event:*`）配置后按配置值解析，而不是留在默认."""
        config["event"] = {"dispatchBatchingEnabled": True, "batchMaxSize": 128}
        cls = self._declare_batching()
        assert cls.DISPATCH_BATCHING_ENABLED is True
        assert cls.BATCH_MAX_SIZE == 128

    def test_missing_keys_keep_conservative_defaults(self, config):
        """缺省 → 开关关闭、批上限保守值：未配置时行为零变化."""
        cls = self._declare_batching()
        assert cls.DISPATCH_BATCHING_ENABLED is False
        assert cls.BATCH_MAX_SIZE == 64

    def test_configured_false_keeps_batching_off(self, config):
        """显式配置 false → 仍是关闭（假值被尊重；此处假值即保守方向）."""
        config["event"] = {"dispatchBatchingEnabled": False}
        cls = self._declare_batching()
        assert cls.DISPATCH_BATCHING_ENABLED is False

    def test_defaults_match_event_params_declaration(self):
        """真类 `EventParams` 的缺省值与上面声明一致（防两处声明漂移）."""
        from zoo_framework.params import EventParams

        assert EventParams.DISPATCH_BATCHING_ENABLED is False
        assert EventParams.BATCH_MAX_SIZE == 64


# =============================================================================
# 收口：该组改动不得改变既有配置读取行为
# =============================================================================


def test_aop_package_still_exports_params():
    """`@params` 仍可从 `zoo_framework.core.aop` 取用."""
    assert callable(aop.params)
