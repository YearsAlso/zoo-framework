"""zfc 命令行工具：生成项目脚手架与新增 Worker.

本子包只在**开发期**使用：框架运行时不导入它，因此它依赖的 `click` 不该出现在
"框架运行需要什么"的清单里——`[project.scripts]` 的三个入口都指向这里。

命令行的解析与脚手架的文件产出分居两个模块：本模块负责选项与错误呈现，
`zoo_framework.cli.scaffold` 负责实际产出。
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
    """生成脚手架项目，或在项目中新增 Worker.

    每个选项都会产生可观察的产出；不接受任何无效果的选项——被静默忽略的选项会让
    调用方以为自己的意图已被实现。

    校验先于一切产出：同时传入 `--create` 与 `--worker` 时，Worker 名非法就不会
    先建出半个项目——"非法输入不产出任何文件"必须是字面成立的，而不是仅对单独调用成立。
    """
    if worker is not None:
        _validate_worker_name(worker.lower())

    project_dir = None
    if create is not None:
        create_func(create)
        project_dir = create

    if worker is not None:
        worker_func(worker.lower(), project_dir)
