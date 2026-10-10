"""Scaffold logic: create a project, add a Worker.

Separated from the CLI layer: this module only produces files and does not
depend on click's command/option decorators (except
``click.ClickException`` / ``click.BadParameter`` - those are how this module
reports failure outward, and the CLI layer renders them as user-visible
errors).
"""

import json
import keyword
import os
from string import Template

import click

from zoo_framework.templates import (
    WORKER_IMPORT_MARKER,
    WORKER_REGISTRATION_MARKER,
    conf_template,
    events_template,
    main_template,
    params_template,
    worker_template,
)
from zoo_framework.utils import FileUtils

DEFAULT_CONF = {
    "_exports": [],
    "log": {"path": "./logs", "level": "debug"},
    "worker": {"runPolicy": "simple", "pool": {"size": 5, "enabled": False}},
    # Read by the params example module; the path is demo:greeting
    "demo": {"greeting": "hello from config.json"},
}

# Source directory name produced by the scaffold
SRC_DIR_NAME = "src"
# Subdirectory that hosts Workers
WORKER_DIR_NAME = "workers"


def resolve_worker_dir(cwd: str | None = None) -> str:
    """定位最近的脚手架项目，并返回其 Worker 目录（相对于工作目录）。

    项目入口 ``src/main.py`` 是项目根目录的判据：Worker 必须能从该入口
    注册，单独存在的 ``src/`` 或 ``config.json`` 不足以确认它是脚手架项目。
    从当前目录逐级向父目录查找，因此可在项目根目录、``src/`` 或其子目录中调用。

    Args:
        cwd: 工作目录；None 表示当前工作目录。

    Returns:
        相对于工作目录的 Worker 输出目录。

    Raises:
        click.ClickException: 当前目录及其父目录均没有 ``src/main.py``。
    """
    base = os.path.abspath(cwd or os.getcwd())
    current = base

    while True:
        main_path = os.path.join(current, SRC_DIR_NAME, "main.py")
        if os.path.isfile(main_path):
            worker_dir = os.path.join(current, SRC_DIR_NAME, WORKER_DIR_NAME)
            return os.path.relpath(worker_dir, start=base)

        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    raise click.ClickException(
        "未找到脚手架项目入口 'src/main.py'（当前目录或其父目录中均不存在）。"
        "请先运行 'zfc --create <name>'，或切换到已有脚手架项目目录后重试。"
    )


def create_func(object_name):
    """Create a scaffold project.

    When the target already exists this MUST fail loudly: returning silently
    leaves the caller unable to tell "created this time" from "already
    existed", and proceeding as if the target were ready would mask real
    failures such as a mistyped path.

    Args:
        object_name: Target directory path; parent directories may not exist yet.

    Raises:
        click.ClickException: The target path already exists. Nothing is written
            before this raises.
    """
    if os.path.exists(object_name):
        raise click.ClickException(
            f"Target {object_name!r} already exists; nothing was changed. "
            "Pick another name or delete the directory first."
        )

    os.makedirs(object_name)
    src_dir = os.path.join(object_name, "src")
    conf_dir = os.path.join(src_dir, "conf")
    params_dir = os.path.join(src_dir, "params")
    main_file = os.path.join(src_dir, "main.py")
    events_dir = os.path.join(src_dir, "events")
    workers_dir = os.path.join(src_dir, "workers")
    config_file = os.path.join(object_name, "config.json")

    threads_init_file = os.path.join(workers_dir, "__init__.py")
    config_init_file = os.path.join(conf_dir, "__init__.py")
    events_init_file = os.path.join(events_dir, "__init__.py")
    params_init_file = os.path.join(params_dir, "__init__.py")

    os.mkdir(src_dir)
    os.mkdir(conf_dir)
    os.mkdir(workers_dir)
    os.mkdir(params_dir)
    os.mkdir(events_dir)

    with open(config_file, "w", encoding=FileUtils.DEFAULT_ENCODING) as fp:
        json.dump(DEFAULT_CONF, fp)

    # src/ also acts as the package; without the package marker the generated
    # project's package structure would not be self-consistent.
    for init_file in (
        os.path.join(src_dir, "__init__.py"),
        threads_init_file,
        config_init_file,
        events_init_file,
        params_init_file,
    ):
        FileUtils.write_text(init_file, "")

    # One loadable example module per extension point. Empty directories would
    # make the output self-inconsistent - there would be "generated but never
    # loaded" modules, and the user could not tell what those directories are for.
    for module_file, module_template in (
        (os.path.join(conf_dir, "demo_conf.py"), conf_template),
        (os.path.join(params_dir, "demo_params.py"), params_template),
        (os.path.join(events_dir, "demo_event.py"), events_template),
    ):
        FileUtils.write_text(module_file, module_template)

    with open(main_file, "w", encoding=FileUtils.DEFAULT_ENCODING) as fp:
        fp.write(main_template)


def _worker_names(worker_name: str) -> tuple[str, str]:
    """Derive (module name, class name) from the user-supplied Worker name.

    Args:
        worker_name: The user-supplied Worker name.

    Returns:
        (module name, class name)
    """
    return f"{worker_name}_worker", f"{worker_name.title()}Worker"


def _wire_worker_into_main(main_path: str, worker_name: str, class_name: str) -> None:
    """Wire a new Worker's import and registration into the scaffold entry point.

    The entry point MUST import and register Workers **explicitly**: an import
    line in a package ``__init__`` is decorative - nothing imports that package,
    so it would never execute. Only with the explicit wiring is there a
    traceable chain from "generated file" to "loaded code".

    Wiring is **idempotent**: re-adding the same Worker never accumulates
    duplicated import lines or registration entries. Deduplication compares
    whole lines exactly rather than by substring containment - per-line
    comparison matches the "one Worker per line" output shape and never
    misreads longer names or fragments inside comments as already present.

    Args:
        main_path: Entry point file path.
        worker_name: The user-supplied Worker name.
        class_name: The Worker class name.
    """
    module_name = f"{worker_name}_worker"
    content = FileUtils.read_text(main_path)

    import_line = f"from workers.{module_name} import {class_name}"
    # The entry itself carries no indentation: the insertion point keeps the
    # indentation that precedes the marker.
    registration_line = f'("{class_name}", {class_name}),'

    if import_line not in content.splitlines():
        content = content.replace(WORKER_IMPORT_MARKER, f"{import_line}\n{WORKER_IMPORT_MARKER}", 1)

    if registration_line not in [line.strip() for line in content.splitlines()]:
        content = content.replace(
            WORKER_REGISTRATION_MARKER, f"{registration_line}\n    {WORKER_REGISTRATION_MARKER}", 1
        )

    FileUtils.write_text(main_path, content)


def _validate_worker_name(worker_name: str) -> None:
    """Validate that a Worker name is usable as a Python identifier.

    Validation MUST happen before any output: produce-then-check hands the
    recovery cost to the caller and leaves an unparseable file on disk - at
    failure time the bad artifact is already there.

    The identifier decision comes from Python itself: ``isidentifier()``
    covers "not starting with a digit, no hyphen/dot/space, non-empty", and
    ``iskeyword()`` covers keywords like ``class``/``def`` which are valid
    identifiers but unusable as class names.

    Args:
        worker_name: The user-supplied Worker name.

    Raises:
        click.BadParameter: The name is not a valid identifier or is a Python keyword.
    """
    if worker_name.isidentifier() and not keyword.iskeyword(worker_name):
        return

    raise click.BadParameter(
        f"{worker_name!r} is not a valid Worker name: it must be a valid Python "
        "identifier (must not start with a digit, contain hyphens, dots or "
        "spaces, or be a Python keyword). "
        "Use underscores instead, e.g. 'my_task'."
    )


def worker_func(worker_name, project_dir: str | None = None):
    """Add a Worker file to the current scaffold project.

    The output directory is decided along two paths: with ``project_dir``
    given, it lands in that project's ``src/workers/``; otherwise it is
    decided from the working directory layout (``resolve_worker_dir``). When a
    single call both creates a project and adds a Worker it MUST take the
    former - deciding from the working directory cannot see the just-created
    directory and would write outside the project.

    Args:
        worker_name: The user-supplied Worker name.
        project_dir: Explicit project root; None decides from the working
            directory layout.

    Raises:
        click.BadParameter: ``worker_name`` is not a valid identifier.
    """
    _validate_worker_name(worker_name)

    if project_dir is not None:
        src_dir = os.path.join(project_dir, SRC_DIR_NAME, WORKER_DIR_NAME)
    else:
        src_dir = resolve_worker_dir()

    module_name, class_name = _worker_names(worker_name)
    file_path = os.path.join(src_dir, f"{module_name}.py")

    if not os.path.exists(src_dir):
        os.makedirs(src_dir, exist_ok=True)
        FileUtils.write_text(os.path.join(src_dir, "__init__.py"), "")

    template = Template(worker_template)
    FileUtils.write_text(
        file_path, template.substitute(worker_name=worker_name, class_name=class_name)
    )

    # Wire the new Worker into the entry point - only when an entry point
    # exists (a non-scaffold directory has none).
    main_path = os.path.join(os.path.dirname(os.path.abspath(src_dir)), "main.py")
    if os.path.exists(main_path):
        _wire_worker_into_main(main_path, worker_name, class_name)
