"""zfc 命令行工具：生成项目脚手架与新增 Worker 文件。

文本文件一律显式指定 UTF-8：默认编码随平台变化，脚手架的产物会被跨平台使用，
依赖默认编码会让同一份模板在不同平台上产生不同的字节。
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
    # 供 params 示例模块读取，路径为 demo:greeting
    "demo": {"greeting": "hello from config.json"},
}

# 脚手架产出的源码目录名
SRC_DIR_NAME = "src"
# 承载 Worker 的子目录名
WORKER_DIR_NAME = "workers"


def resolve_worker_dir(cwd: str | None = None) -> str:
    """定位新增 Worker 的产出目录.

    依据当前工作目录的**实际结构**判定，而不是从进程启动路径（`sys.argv[0]`）猜测：
    console script 在 Windows 上是 `.exe` 路径、在 POSIX 上是 `bin` 下的无扩展名文件，
    两者都与源码目录结构无关，据此判断会在所有平台上失效。

    `create_func` 产出的布局是 `<project>/src/workers/`，因此在项目根执行时应落在
    `./src/workers`，在 `src/` 内执行时 `./src` 不存在，自然落到 `./workers`。

    Args:
        cwd: 工作目录；None 表示使用当前工作目录

    Returns:
        产出目录的路径
    """
    base = cwd or os.getcwd()
    if os.path.isdir(os.path.join(base, SRC_DIR_NAME)):
        return os.path.join(".", SRC_DIR_NAME, WORKER_DIR_NAME)
    return os.path.join(".", WORKER_DIR_NAME)


def create_func(object_name):
    """生成一个脚手架项目.

    目标已存在时 MUST 明确失败：静默返回让调用方无法区分"本次创建了"与"本来就存在"，
    而把目标当作"已就绪"继续使用，会掩盖路径写错这类真实故障。

    Args:
        object_name: 目标目录路径，可含尚未存在的父目录

    Raises:
        click.ClickException: 目标路径已存在。抛出前未做任何写入
    """
    if os.path.exists(object_name):
        raise click.ClickException(
            f"目标 {object_name!r} 已存在，未做任何改动。请换一个名称，或先删除该目录。"
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

    # src/ 也承担包角色，缺少包标识会让产出项目的包结构不自洽
    for init_file in (
        os.path.join(src_dir, "__init__.py"),
        threads_init_file,
        config_init_file,
        events_init_file,
        params_init_file,
    ):
        FileUtils.write_text(init_file, "")

    # 三个扩展点各给一份可加载的示例模块。空目录会让产出物本身就不自洽——
    # 存在"生成了但从头到尾不被加载"的模块，用户也看不出这些目录是干什么用的。
    for module_file, module_template in (
        (os.path.join(conf_dir, "demo_conf.py"), conf_template),
        (os.path.join(params_dir, "demo_params.py"), params_template),
        (os.path.join(events_dir, "demo_event.py"), events_template),
    ):
        FileUtils.write_text(module_file, module_template)

    with open(main_file, "w", encoding=FileUtils.DEFAULT_ENCODING) as fp:
        fp.write(main_template)


def _worker_names(worker_name: str) -> tuple[str, str]:
    """由用户输入的 Worker 名推导出 (模块名, 类名).

    Args:
        worker_name: 用户输入的 Worker 名

    Returns:
        (模块名, 类名)
    """
    return f"{worker_name}_worker", f"{worker_name.title()}Worker"


def _wire_worker_into_main(main_path: str, worker_name: str, class_name: str) -> None:
    """把新 Worker 的导入与注册接入脚手架入口.

    入口必须**显式**导入并注册 Worker：包初始化文件里写一行导入语句是装饰性的——
    没有任何代码导入那个包，即使写了也不会被执行。显式化之后，"生成的文件"与
    "被加载的代码"之间才有可追踪的链路。

    接线是**幂等**的：同一个 Worker 重复接入不会让入口累积重复的导入行或注册条目。
    判重按整行精确比较而非子串包含——按行比较与"一个 Worker 一行"的产出形态一致，
    也不会把更长的名字或注释里的片段误判为已存在。

    Args:
        main_path: 入口文件路径
        worker_name: 用户输入的 Worker 名
        class_name: Worker 类名
    """
    module_name = f"{worker_name}_worker"
    content = FileUtils.read_text(main_path)

    import_line = f"from workers.{module_name} import {class_name}"
    # 条目本身不带缩进：插入点保留了标记前的缩进
    registration_line = f'("{class_name}", {class_name}),'

    if import_line not in content.splitlines():
        content = content.replace(WORKER_IMPORT_MARKER, f"{import_line}\n{WORKER_IMPORT_MARKER}", 1)

    if registration_line not in [line.strip() for line in content.splitlines()]:
        content = content.replace(
            WORKER_REGISTRATION_MARKER, f"{registration_line}\n    {WORKER_REGISTRATION_MARKER}", 1
        )

    FileUtils.write_text(main_path, content)


def _validate_worker_name(worker_name: str) -> None:
    """校验 Worker 名称可作 Python 标识符使用.

    校验 MUST 发生在产出之前：先产出再检查等于把恢复成本转嫁给调用方，而且会留下
    一份不可解析的文件——报错时磁盘上已经有坏产物了。

    合法标识符的判定直接取自 Python 自身：`isidentifier()` 覆盖"不以数字开头、
    不含连字符/点号/空格、非空"，`iskeyword()` 补上 `class`/`def` 这类合法标识符
    但不可作类名的情况。

    Args:
        worker_name: 用户输入的 Worker 名

    Raises:
        click.BadParameter: 名称不是合法标识符，或为 Python 关键字
    """
    if worker_name.isidentifier() and not keyword.iskeyword(worker_name):
        return

    raise click.BadParameter(
        f"{worker_name!r} 不是合法的 Worker 名称：它必须是合法的 Python 标识符"
        "（不能以数字开头，不能含连字符、点号或空格，不能是 Python 关键字）。"
        "请改用下划线命名，例如 'my_task'。"
    )


def worker_func(worker_name, project_dir: str | None = None):
    """在当前的脚手架项目中新增一个 Worker 文件.

    产出目录的判定分两条路径：`project_dir` 给定就落在该项目的 `src/workers/`；
    否则按工作目录结构判定（`resolve_worker_dir`）。同一次调用中先创建项目再新增
    Worker 时**必须**走前者——按工作目录判定看不到刚创建的目录，会把文件写到项目外。

    Args:
        worker_name: 用户输入的 Worker 名
        project_dir: 显式指定的项目根目录；None 表示按工作目录结构判定

    Raises:
        click.BadParameter: `worker_name` 不是合法标识符
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

    # 把新 Worker 接入入口——只有当入口存在时才接线（非脚手架目录没有入口）
    main_path = os.path.join(os.path.dirname(src_dir), "main.py")
    if os.path.exists(main_path):
        _wire_worker_into_main(main_path, worker_name, class_name)


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


if __name__ == "__main__":
    zfc()
