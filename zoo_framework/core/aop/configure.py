from typing import Any

from zoo_framework.utils import LogUtils
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict

# A thread-safe dict for storing config functions.
#
# [Known debt] a module-level registry, process-level shared; to be reset
# separately by tests (see the cleanup helper in
# tests/test_scaffold_cli_contract.py). A carrier outside the container, not
# yet absorbed; rationale and criteria in specs/scoped-container's
# "process-level sharing created by the framework itself MUST be explicitly
# classified".
config_funcs: ThreadSafeDict[str, Any] = ThreadSafeDict()

# Registration sealing state (aop-determinism / issue #51): @configure
# registration happens **at import time**, and Master construction iterates
# and **calls each without arguments** once. A registration after the seal
# falls outside "the consumption window of this Master" - historically it
# silently failed (and if no further Master ran, it quietly evaporated).
# Now it is registered as usual, but with a loud warning that "only the next
# Master() will consume it".
# Why not a hard error: re-running an entry point in the same process
# (tests, reloaders, notebooks) re-imports the config modules and registers
# again, immediately followed by a new Master() - a legitimate shape locked
# in by the scaffold contract test (test_scaffold_cli_contract's
# assertions_survive_prior_runs), which a hard error would break.
# The other half - a module "never imported" leaving the registry missing an
# entry - is unobservable at runtime (not imported means no code executes at
# all); the framework does not promise to detect it. The only mitigation is
# for **the entry point to explicitly import** every module containing
# @configure (the scaffold templates already emit it that way, and the
# contract is guarded by "every generated import actually executes"). That
# asymmetry is written into the clauses of specs/aop.
_sealed = False


def seal_config_funcs() -> None:
    """Seal the registry: called after a Master has consumed config_funcs (#51)."""
    global _sealed
    _sealed = True


def unseal_config_funcs_for_tests() -> None:
    """Unseal (a test seam): reset by conftest before each case to avoid cross-case leakage."""
    global _sealed
    _sealed = False


def configure(topic: str):
    """A decorator factory registering a function under the given topic.

    The registration time MUST be before Master construction (the import-time
    side effect is by design); a post-seal registration is still recorded
    but MUST warn loudly - "only the next Master() will consume it"; if no
    further construction happens it silently takes no effect, which is
    exactly the historical silent shape (#51).

    Args:
        topic (str): the topic name, identifying the config function's
            category or purpose.

    Returns:
        function: a decorator function that registers the passed function
            into the config_funcs dict.
    """

    def inner(func):
        if _sealed:
            LogUtils.warning(
                f"@configure('{topic}') was registered after a Master was already constructed:"
                "the current instance will not consume it; it only takes effect when the next Master() is constructed;"
                "if no further Master is constructed in this process, this registration has no effect."
            )
        # Store the passed function into the thread-safe dict keyed by topic
        config_funcs[topic] = func
        return func

    return inner
