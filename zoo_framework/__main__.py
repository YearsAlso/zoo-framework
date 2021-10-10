import json

import click
import os
import jinja2
from jinja2 import Environment, PackageLoader

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
    events_dir = src_dir + "/events"
    threads_dir = src_dir + "/threads"
    config_file = object_name + "/config.json"
    os.mkdir(src_dir)
    os.mkdir(conf_dir)
    os.mkdir(threads_dir)
    # os.mkdir(events_dir)
    with open(config_file, "w") as fp:
        json.dump(DEFAULT_CONF, fp)


def thread_func(thread_name):
    # 创建文件夹
    src_dir = "./threads"
    file_path = src_dir + "/" + thread_name + "_thread.py"
    if not os.path.exists(src_dir):
        os.mkdir(src_dir)
    # 根据模板创建文件
    env = Environment(loader=PackageLoader('zoo_framework', 'templates'))  # 创建一个包加载器对象

    template = env.get_template('thread.pyt')  # 获取一个模板文件
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


zfc()
