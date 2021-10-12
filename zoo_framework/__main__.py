import json
import sys

import click
import os
import jinja2
from jinja2 import Environment, PackageLoader, Template
from zoo_framework.templates import thread_template, main_template

DEFAULT_CONF = {
    "log": {
        "path": "./logs"
    }
}


def create_func(object_name):
    if os.path.exists(object_name):
        return

    os.mkdir(object_name)
    src_dir = object_name + '/src'
    conf_dir = src_dir + "/conf"
    main_file = src_dir + "/main.py"
    events_dir = src_dir + "/events"
    threads_dir = src_dir + "/threads"
    config_file = object_name + "/config.json"
    os.mkdir(src_dir)
    os.mkdir(conf_dir)
    os.mkdir(threads_dir)
    # os.mkdir(events_dir)
    with open(config_file, "w") as fp:
        json.dump(DEFAULT_CONF, fp)

    with open(main_file, "w") as fp:
        fp.write(main_template)
    # create main.py


def thread_func(thread_name):
    # 创建文件夹
    src_dir = "./threads"
    if str(sys.argv[0]).endswith("/src"):
        src_dir = "./src/threads"
    file_path = src_dir + "/" + thread_name + "_thread.py"
    if not os.path.exists(src_dir):
        os.mkdir(src_dir)

    template = Template(thread_template)
    content = template.render(thread_name=thread_name)  # 渲染
    with open(file_path, "w") as fp:
        fp.write(content)


@click.command()
@click.option("--create", help="Input target object name and create it")
@click.option("--thread", help="nput new thread name and create it")
def zfc(create, thread):
    if create is not None:
        create_func(create)

    if thread is not None:
        thread_func(str(thread).lower())

if __name__ == '__main__':
    zfc()
