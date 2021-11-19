import json
import sys

import click
import os
import jinja2
from jinja2 import Environment, PackageLoader, Template
from zoo_framework.templates import thread_template, main_template, thread_mod_insert_template

DEFAULT_CONF = {
    "_exports": [],
    "log": {
        "path": "./logs",
        "level": "debug"
    },
    "worker": {
        "mode": "thread",
        "runPolicy": "simple",
        "pool": {
            "size": 30,
            "enabled": False
        }
    }
}


def create_func(object_name):
    if os.path.exists(object_name):
        return
    
    os.mkdir(object_name)
    src_dir = object_name + '/src'
    conf_dir = src_dir + "/conf"
    params_dir = src_dir + "/params"
    main_file = src_dir + "/main.py"
    events_dir = src_dir + "/events"
    threads_dir = src_dir + "/threads"
    config_file = object_name + "/config.json"
    
    threads_init_file = threads_dir + "/__init__.py"
    config_init_file = conf_dir + "/__init__.py"
    events_init_file = events_dir + "/__init__.py"
    params_init_file = params_dir + "/__init__.py"
    
    os.mkdir(src_dir)
    os.mkdir(conf_dir)
    os.mkdir(threads_dir)
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


def thread_func(thread_name):
    # 创建文件夹
    src_dir = "./threads"
    if str(sys.argv[0]).endswith("/src"):
        src_dir = "./src/threads"
    file_path = src_dir + "/" + thread_name + "_thread.py"
    threads_init_file = src_dir + "/__init__.py"
    template = Template(thread_mod_insert_template)
    content = template.render(thread_name=thread_name)
    
    if not os.path.exists(src_dir):
        os.mkdir(src_dir)
        with open(threads_init_file, "w") as fp:
            fp.write(content)
    elif os.path.exists(threads_init_file):
        with open(threads_init_file, "a") as fp:
            fp.write(content)
    
    template = Template(thread_template)
    content = template.render(thread_name=thread_name)  # 渲染
    with open(file_path, "w") as fp:
        fp.write(content)


@click.command()
@click.option("--create", help="Input target object name and create it")
@click.option("--worker", help="Input new worker name and create it")
@click.option("--config", help="Input new config file name and create it")
def zfc(create, thread, config):
    if create is not None:
        create_func(create)
    
    if thread is not None:
        thread_func(str(thread).lower())


if __name__ == '__main__':
    zfc()
