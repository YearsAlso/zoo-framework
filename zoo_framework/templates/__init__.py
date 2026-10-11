"""Scaffold templates.

Generated code MUST be directly runnable: it references the public API that
actually exists today, and never demonstrates paths that are deprecated or were
never wired up. Historical counterexamples in ``worker_template``:
``from zoo_framework import worker`` and ``@worker(count=1)`` - that name does
not exist at the package root, the registry ``@worker`` writes to has no
consumer, and a Worker registered that way would import fine yet never get
scheduled.

The ``conf`` / ``params`` / ``events`` templates map to three framework extension
points, each demonstrating a mechanism verified to work. Contracts are in
``changes/fix-scaffold-cli-contract/design.md`` D6: functions registered by
``@configure`` are called by ``Master`` with no arguments, ``@params`` resolves
configuration at import time, and the ``@event`` callback receives an
``EventReactorReq`` rather than the raw payload.
"""

# Insertion-point markers inside the templates; `zfc --worker` relies on them
# to wire a new Worker into the entry point.
WORKER_IMPORT_MARKER = "# zfc:worker-imports"
WORKER_REGISTRATION_MARKER = "# zfc:worker-registrations"

worker_template = """from zoo_framework.workers import BaseWorker


class $class_name(BaseWorker):
    \"\"\"$worker_name Worker.\"\"\"

    def __init__(self):
        BaseWorker.__init__(self, {
            "is_loop": True,
            "delay_time": 10,
            "name": "${worker_name}_worker",
        })
        self._tick = 0

    def _execute(self):
        \"\"\"Run the business logic.\"\"\"
        self._tick += 1
        print(f"[${worker_name}_worker] tick #{self._tick}")

    def _destroy(self, result):
        \"\"\"Called when the Worker is unregistered (the shutdown path triggers this).\"\"\"

    def _on_error(self):
        \"\"\"Called when an execution raises.\"\"\"

    def _on_done(self):
        \"\"\"Called at the end of each execution (success or failure).\"\"\"
"""

conf_template = '''"""Startup configuration hook example.

``@configure(topic=...)`` registers the function into the framework's config
registry; ``Master`` calls every registered function **with no arguments** at
construction time. Registration happens at import, so this module MUST be
imported before ``Master()`` - the ``main.py`` entry point already does that.

Only one function per topic: re-registering silently overwrites, so each
config module should use its own topic.
"""

from zoo_framework.core.aop import configure

# Set to True after the hook runs; usable as a self-check. Delete together with
# the assignment below if unneeded.
executed = False


@configure(topic="demo_conf")
def demo_conf():
    """Executed when the framework starts.

    A place for startup preparation: initializing logging, validating
    environment variables, opening external connections, and so on. The function
    takes no arguments and its return value is ignored - read what you need from
    the configuration.
    """
    global executed
    executed = True
'''

params_template = '''"""Configuration declaration example.

``@params`` replaces class attributes **at import time** with the values found
at the corresponding path in ``config.json``. Paths look like ``a:b:c``,
mirroring the nested structure of the config file; when the path is missing the
default given in the declaration is used.

This module's ``demo:greeting`` corresponds to ``demo.greeting`` in the
``config.json`` next to the entry point.
"""

from zoo_framework.core import param
from zoo_framework.core.aop import params


@params
class DemoParams:
    """Maps to the ``demo`` section of ``config.json``."""

    GREETING = param(value="demo:greeting", default="hello from default")
'''

events_template = '''"""Event reactor example.

``@event(topic=..., channel=...)`` registers the function as the reactor for
that topic on that channel; importing this module finishes the registration.
Channels are isolated from each other: a same-named topic sent to another
channel does not trigger this reactor.

The callback receives an **EventReactorReq** object rather than the raw
payload; the payload is on ``req.content``.
"""

from zoo_framework.core.aop import event

# Received event payloads, usable as a self-check. Delete together with the
# append below if unneeded.
received = []


@event(topic="demo_topic", channel="demo_channel")
def on_demo(req):
    """Called when a demo_topic event arrives.

    Args:
        req: The event request object; ``req.topic`` / ``req.content`` /
            ``req.reactor_name``.
    """
    received.append(req.content)
'''

main_template = f"""from zoo_framework.core import Master
from workers.sample_worker import SampleWorker

# Demonstration of import-time wiring and the ordering constraints:
#   conf   - registers the config hook; MUST come before Master(), the hook
#            runs while Master is constructed
#   params - resolves config.json; MUST come after the config is loaded
#   events - registers the event reactor
import conf.demo_conf  # noqa: F401
{WORKER_IMPORT_MARKER}

WORKERS = [
    # 开箱即跑的示例；确认业务后连同上方导入行一起删除
    ("SampleWorker", SampleWorker),
    {WORKER_REGISTRATION_MARKER}
]


def main():
    master = Master()

    # After Master(): the config is loaded and the event channels are ready.
    import events.demo_event  # noqa: F401
    import params.demo_params  # noqa: F401

    for name, worker_class in WORKERS:
        master.register_worker(name, worker_class)
    master.run()


if __name__ == '__main__':
    main()
"""
