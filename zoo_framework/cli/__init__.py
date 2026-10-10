"""zfc command line tool: scaffold a project and add Workers.

This subpackage is used at **development time** only: the framework runtime does
not import it, which is why its ``click`` dependency is absent from the "what
the framework needs" list - the three ``[project.scripts]`` entry points all
target this package.

Option parsing and file generation live in two modules: this module handles the
options and error presentation; ``zoo_framework.cli.scaffold`` does the actual
generation.
"""

import click

from .scaffold import (
    DEFAULT_CONF,
    SRC_DIR_NAME,
    WORKER_DIR_NAME,
    _validate_worker_name,
    create_func,
    resolve_worker_dir,
    worker_func,
)

__all__ = [
    "DEFAULT_CONF",
    "SRC_DIR_NAME",
    "WORKER_DIR_NAME",
    "create_func",
    "resolve_worker_dir",
    "worker_func",
    "zfc",
]


@click.command()
@click.option("--create", help="Input target object name and create it")
@click.option("--worker", help="Input new worker name and create it")
def zfc(create, worker):
    """Scaffold a project, or add a Worker to an existing project.

    Every option produces an observable output; no-impact invocations are not
    accepted - a silently ignored option would make the caller believe their
    intent was implemented.

    Validation happens before any output: when both ``--create`` and
    ``--worker`` are given, an invalid Worker name fails the whole command
    instead of leaving half a project behind - "invalid input produces no
    files" must hold literally, not only for single-option calls.
    """
    if worker is not None:
        _validate_worker_name(worker.lower())

    project_dir = None
    if create is not None:
        create_func(create)
        project_dir = create

    if worker is not None:
        worker_func(worker.lower(), project_dir)
