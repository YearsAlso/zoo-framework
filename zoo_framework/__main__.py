import json
import os
import sys

import click
from jinja2 import Template

from zoo_framework.templates import main_template, worker_mod_insert_template, worker_template

DEFAULT_CONF = {
    "_exports": [],
    "log": {"path": "./logs", "level": "debug"},
    "worker": {"runPolicy": "simple", "pool": {"size": 5, "enabled": False}},
}


def create_func(object_name):
    if os.path.exists(object_name):
        return

    os.mkdir(object_name)
    src_dir = object_name + "/src"
    conf_dir = src_dir + "/conf"
    params_dir = src_dir + "/params"
    main_file = src_dir + "/main.py"
    events_dir = src_dir + "/events"
    workers_dir = src_dir + "/workers"
    config_file = object_name + "/config.json"

    threads_init_file = workers_dir + "/__init__.py"
    config_init_file = conf_dir + "/__init__.py"
    events_init_file = events_dir + "/__init__.py"
    params_init_file = params_dir + "/__init__.py"

    os.mkdir(src_dir)
    os.mkdir(conf_dir)
    os.mkdir(workers_dir)
    os.mkdir(params_dir)
    os.mkdir(events_dir)
    # os.mkdir(events_dir)
    with open(config_file, "w") as fp:
        json.dump(DEFAULT_CONF, fp)

    with open(main_file, "w") as fp:
        fp.write(main_template)

    with open(threads_init_file, "w") as fp:
        fp.write("")

    with open(config_init_file, "w") as fp:
        fp.write("")

    with open(events_init_file, "w") as fp:
        fp.write("")

    with open(params_init_file, "w") as fp:
        fp.write("")

    # create main.py


def worker_func(worker_name):
    # 创建文件夹
    src_dir = "./workers"
    if str(sys.argv[0]).endswith("/src"):
        src_dir = "./src/workers"
    file_path = src_dir + "/" + worker_name + "_worker.py"
    workers_init_file = src_dir + "/__init__.py"
    template = Template(worker_mod_insert_template)
    content = template.render(worker_name=worker_name)

    if not os.path.exists(src_dir):
        os.mkdir(src_dir)
        with open(workers_init_file, "w") as fp:
            fp.write(content)
    elif os.path.exists(workers_init_file):
        with open(workers_init_file, "a") as fp:
            fp.write(content)

    template = Template(worker_template)
    content = template.render(worker_name=worker_name)  # 渲染
    with open(file_path, "w") as fp:
        fp.write(content)


@click.command()
@click.option("--create", help="Input target object name and create it")
@click.option("--worker", help="Input new worker name and create it")
@click.option("--config", help="Input new config file name and create it")
def zfc(create, worker, config):
    if create is not None:
        create_func(create)

    if worker is not None:
        worker_func(str(worker).lower())


if __name__ == "__main__":
    zfc()
