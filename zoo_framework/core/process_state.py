"""Explicit classification registry for process-level carriers outside the container (change declare-debt-carriers / issue #50 slice 1).

Background: the container delivered by `scoped-container` only holds
"resolved instances" and cannot reach class attributes and registration
surfaces; `specs/scoped-container` requires the framework's own process-level
sharing to be **explicitly classified**, while test isolation previously
relied on a hand-maintained reset list in `tests/conftest.py` - nothing
guaranteed a newly added process-level shared object would be registered.
This module turns the "classification declaration" into data and the "reset
list" into functions generated from the registry:

- `CARRIERS` is the single source of truth: one declaration per process-level
  shared carrier (classification + reason + optional reset).
- `reset_process_state()` lets the test base run the resets one by one -
  conftest no longer copies the list by hand.
- Leak interception: `tests/test_process_state_registry.py` scans every
  module-level / class-level mutable container of the framework and fails on
  any not matched by an entry of this table (by object identity or canonical
  name) - when a new process-level share is added without being classified,
  the test goes red, not "someday's test-cross-talk mystery".

Entry categories (corresponding to #50's "two kinds that must not be
conflated"):
- registration surface / configuration surface: not resolved instances, not
  forced into the container; here they get an explicit classification and
  reason
- pending absorption: process-level shared instances identified by #50
  (absorption method handled in slice 2); currently reset-isolated first
- execution facilities: runtime facilities with no user-visible state (the
  thread pool); not rebuilt per test case
- the container itself: the reset entry of the framework's process-level
  container
- constants: read-only at runtime; declared = classified

How to claim: a carrier whose object gets **rebound** (e.g.
`ParamsFactory.config_params`, replaced wholesale on load) MUST claim by
canonical name; carriers only mutated in place claim by object identity -
both paths work, choosing the wrong one makes the scan false-positive
"after other test cases ran".
"""

import sys
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Carrier:
    """The classification declaration of one process-level carrier.

    Attributes:
        canonical: the canonical name ("module tail: object name", for humans)
        category: the classification, see the module docstring for values
        reason: the classification reason (MUST state why when judged
            outside the container)
        watch: the registered object itself, matched by identity in the scan;
            rebound objects go in names
        names: the allowed canonical full names ("module.attr" /
            "module.Class.attr")
        reset: the test reset action; None means the carrier need not /
            should not be reset per test case
    """

    canonical: str
    category: str
    reason: str
    watch: object | None = None
    names: tuple[str, ...] = ()
    reset: Callable[[], None] | None = None


def _register_all() -> dict[str, Carrier]:
    """Build the registry: every registered object is imported here once (lazily inside the function, avoiding import cycles)."""
    # Reading a submodule by attribute gets shadowed by the package-surface
    # function of the same name (aop/__init__ imports the function), so
    # trigger the import first and then fetch the real module object from
    # sys.modules.
    import zoo_framework.core.aop.configure
    import zoo_framework.core.aop.params  # noqa: F401

    configure_mod = sys.modules["zoo_framework.core.aop.configure"]
    params_mod = sys.modules["zoo_framework.core.aop.params"]

    from zoo_framework.cli import DEFAULT_CONF as _cli_default
    from zoo_framework.core.container import framework_container
    from zoo_framework.core.params_factory import ParamsFactory
    from zoo_framework.core.waiter.base_waiter import LEGACY_POLICY_TO_BACKPRESSURE
    from zoo_framework.fifo.single_fifo import SingleFIFO
    from zoo_framework.plugin import Plugin
    from zoo_framework.reactor.event_reactor_req import get_channel_manager
    from zoo_framework.statemachine.state_index_factory import StateIndexFactory

    # ---- Reset actions (named functions: return None, do not use a tuple expression as a Callable) ----

    def reset_config_funcs() -> None:
        configure_mod.config_funcs.clear()
        configure_mod.unseal_config_funcs_for_tests()

    def reset_params_cache() -> None:
        params_mod.config_params.clear()
        params_mod._resolved_generation.clear()

    def reset_config_dict() -> None:
        ParamsFactory.config_params = {}
        ParamsFactory._generation = 0

    def reset_channel_manager() -> None:
        manager = get_channel_manager()
        manager._channels.clear()
        manager._reactor_channels.clear()

    def reset_container() -> None:
        framework_container().reset()

    carriers: list[Carrier] = [
        # ---- Registration surface / configuration surface (not forced into the container, declared + reset) ----
        Carrier(
            canonical="core.aop.configure:config_funcs",
            category="注册面",
            reason=(
                "Import-time registry of @configure, not a resolved instance; "
                "the consume/seal contract is in specs/aop. Reset = clear and "
                "unseal (test cases start from a clean registration surface)."
            ),
            watch=configure_mod.config_funcs,
            reset=reset_config_funcs,
        ),
        Carrier(
            canonical="core.aop.configure:_sealed",
            category="注册面",
            reason=(
                "The seal flag of the registry (a bool, invisible to the scan); "
                "reset together with config_funcs."
            ),
            reset=configure_mod.unseal_config_funcs_for_tests,
        ),
        Carrier(
            canonical="core.aop.params:config_params",
            category="配置面",
            reason=(
                "Resolution cache of @params (qualified name -> class) and the "
                "resolution-generation record of #51: it registers the "
                "resolution side, not a container item; reset = clear (may "
                "re-resolve within tests), unrelated to the rebinding "
                "semantics of ParamsFactory.config_params (this table mutates "
                "in place)."
            ),
            watch=params_mod.config_params,
            reset=reset_params_cache,
        ),
        Carrier(
            canonical="core.aop.params:_resolved_generation",
            category="配置面",
            reason=(
                "The resolution-generation record of #51, sharing the "
                "lifecycle of config_params; reset together with it."
            ),
            watch=params_mod._resolved_generation,
        ),
        Carrier(
            canonical="core.params_factory:ParamsFactory.config_params",
            category="配置面",
            reason=(
                "The configuration dict actually read by get_params (a class "
                "attribute). **Rebound wholesale** on load rather than mutated "
                "in place, hence claimed by canonical name; reset also zeroes "
                "the load-generation counter."
            ),
            names=("zoo_framework.core.params_factory.ParamsFactory.config_params",),
            reset=reset_config_dict,
        ),
        # ---- Absorbed into the container (change absorb-debt-carriers / #50 deliverable 1, option A) ----
        Carrier(
            canonical="reactor.event_reactor_manager:reactor_map",
            category="容器本身",
            reason=(
                "Absorbed from [known debt]: the registry was downgraded to an "
                "attribute of the process_scoped instance, so a container "
                "reset fully resets it; class-level reads go through the "
                "metaclass proxy to the process-level instance, hence claimed "
                "by canonical name."
            ),
            names=("zoo_framework.reactor.event_reactor_manager.EventReactorManager.reactor_map",),
        ),
        Carrier(
            canonical="event.event_channel_register:_channel_map",
            category="容器本身",
            reason=(
                "Same as reactor_map: absorbed into instance state, so a "
                "container reset fully resets it."
            ),
            names=("zoo_framework.event.event_channel_register.EventChannelRegister._channel_map",),
        ),
        Carrier(
            canonical="core.worker_registry:get_worker_registry",
            category="容器本身",
            reason=(
                "The original module-level implicit singleton _global_registry "
                "has been absorbed: the process-level entry resolves through "
                "the framework container, and a container reset rebuilds a "
                "new instance, i.e. a full reset (directly constructing a "
                "private instance is unaffected)."
            ),
        ),
        # ---- Execution facilities (no user-visible state, not rebuilt per test case) ----
        Carrier(
            canonical="statemachine.state_node:_effect_executor",
            category="执行设施",
            reason=(
                "The module-level shared thread pool introduced by "
                "align-execution-primitives: an execution facility, not state "
                "storage; rebuilding per test case would only leak threads, "
                "and reclamation relies on concurrent.futures' atexit hook."
            ),
        ),
        # ---- The container itself and the reset seam ----
        Carrier(
            canonical="core.container.registry:framework_container",
            category="容器本身",
            reason=(
                "The reset entry of the framework's process-level container - "
                "the first hand-copied reset source of the original conftest."
            ),
            reset=reset_container,
        ),
        Carrier(
            canonical="reactor.event_reactor_req:channel_manager",
            category="注册面",
            reason=(
                "Channel listening configuration (the internal tables of the "
                "get_channel_manager singleton): not resolved instances, "
                "registered outside the container; reset = clear the two "
                "internal tables (current conftest semantics)."
            ),
            reset=reset_channel_manager,
        ),
        # ---- Pending absorption (registered here, handled by later slices) ----
        Carrier(
            canonical="fifo.single_fifo:SingleFIFO.index_list",
            category="待收编",
            reason=(
                "A class-attribute dict shared across instances - the "
                "single_fifo doc self-marks it [known debt]; not listed in "
                "#50's inventory (newly found once the scan mechanism went "
                "live). This slice only declares the classification and does "
                "not reset per test case (changing the reset semantics is out "
                "of scope); same shape as reactor_map, absorption in a later "
                "change."
            ),
            watch=SingleFIFO.index_list,
        ),
        Carrier(
            canonical="cli:DEFAULT_CONF",
            category="常量",
            reason=(
                "The scaffold's default configuration template; read-only at "
                "runtime (the scaffold-side entry of the same name is an "
                "alias)."
            ),
            watch=_cli_default,
            names=("zoo_framework.cli.scaffold.DEFAULT_CONF",),
        ),
        Carrier(
            canonical="conf.log_config:颜色与级别映射",
            category="常量",
            reason="The log level/color table; read-only at runtime.",
            names=(
                "zoo_framework.conf.log_config.level_relations",
                "zoo_framework.conf.log_config.log_colors_config",
            ),
        ),
        Carrier(
            canonical="core.waiter.base_waiter:LEGACY_POLICY_TO_BACKPRESSURE",
            category="常量",
            reason="Legacy policy-name mapping; read-only at runtime.",
            watch=LEGACY_POLICY_TO_BACKPRESSURE,
        ),
        Carrier(
            canonical="plugin:Plugin.dependencies",
            category="常量",
            reason=(
                "A class-attribute empty list serving only as a default; "
                "instance writes go through self-shadowing and never mutate "
                "the class object."
            ),
            watch=Plugin.dependencies,
        ),
        Carrier(
            canonical="core.container.thread_safety:ThreadSafety.DESCRIPTIONS",
            category="常量",
            reason=(
                "The human-readable description table of thread-safety "
                "declarations; reads like an enum but is a plain class, "
                "read-only at runtime."
            ),
            names=("zoo_framework.core.container.thread_safety.ThreadSafety.DESCRIPTIONS",),
        ),
        Carrier(
            canonical="statemachine.state_index_factory:StateIndexFactory._index_types",
            category="注册面",
            reason=(
                "The registry of the index-type factory (written at decorator "
                "import time, append-only at runtime), same shape as "
                "config_funcs: not forced into the container, declared = "
                "classified; needs no reset across test cases."
            ),
            watch=StateIndexFactory._index_types,
        ),
    ]
    table = {c.canonical: c for c in carriers}
    # The registry itself: read-only after construction (new carriers are
    # added by editing the source, not registering at runtime); claimed by
    # name so the scan mechanism is not tripped by its own source of truth.
    table["core.process_state:CARRIERS"] = Carrier(
        canonical="core.process_state:CARRIERS",
        category="常量",
        reason=(
            "The registry itself: read-only after construction; it registers "
            "itself so the scan mechanism is not tripped by its own source of "
            "truth."
        ),
        names=("zoo_framework.core.process_state.CARRIERS",),
    )
    return table


#: The single source of truth of the registry (built at import; the imports of
#: registered modules happen inside _register_all).
CARRIERS: dict[str, Carrier] = _register_all()


def reset_process_state() -> None:
    """Reset each item per the registry - the sole entry of the test base (replacing conftest's hand-copied list).

    A single reset's exception does not mask the remaining resets: run all of
    them first, then aggregate and raise.
    """
    failures: list[str] = []
    for name, carrier in CARRIERS.items():
        if carrier.reset is None:
            continue
        try:
            carrier.reset()
        except (
            Exception
        ) as exc:  # aggregate before reporting, so one failure does not swallow the other resets
            failures.append(f"{name}: {exc!r}")
    if failures:
        raise RuntimeError("process-level carrier reset failed:\n" + "\n".join(failures))


def known_carrier_ids() -> set[int]:
    """For scan interception: the identity set of the registered objects."""
    return {id(c.watch) for c in CARRIERS.values() if c.watch is not None}


def known_carrier_names() -> set[str]:
    """For scan interception: the set of registered canonical full names (rebinding-type / alias carriers)."""
    return {n for c in CARRIERS.values() for n in c.names}
