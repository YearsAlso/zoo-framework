import json

import click
import os
import jinja2

DEFAULT_CONF = {
    "log": {
        "path": "./logs"
    }
}


def create(object_name):
    if os.path.exists(object_name):
        return
    
    os.mkdir(object_name)
    src_dir = object_name + '/src'
    config_file = object_name + "/config.json"
    os.mkdir(src_dir)
    with open(config_file, "w") as fp:
        json.dump(DEFAULT_CONF, fp)


def thread(thread_name):
    # 创建文件夹
    src_dir = "./threads"
    if os.path.exists(src_dir):
        os.mkdir(src_dir)
    # 根据模板创建文件
    env = Environment(loader=PackageLoader('python_project', 'templates'))  # 创建一个包加载器对象

    template = env.get_template('bast.html')  # 获取一个模板文件
    template.render(name='daxin', age=18)  # 渲染
    pass


@click.command()
@click.option("--create", is_flag=True, help="Input target object name and create it")
@click.option("--thread", is_flag=True, help="nput new thread name and create it")
def zfc(create, thread):
    if create is not None:
        create(create)
    
    if thread is not None:
        thread(thread, create)


zfc()
