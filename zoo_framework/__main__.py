import json

import click
import os

DEFAULT_CONF = {
    "log": {
        "path": "./logs"
    }
}


def create():
    pass


@click.command()
@click.option("--create", help="Input target object name and create it")
@click.option("--log", is_flag=True, default=True, help="")
def zfc(create, log):
    object_name = create
    if os.path.exists(object_name):
        return

    os.mkdir(object_name)
    src_dir = object_name + '/src'
    config_file = object_name + "/config.json"
    os.mkdir(src_dir)
    with open(config_file, "w") as fp:
        json.dump(DEFAULT_CONF, fp)


zfc()
