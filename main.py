import threading
import time

from conf import log_config
from conf import thread_config
from conf.devices_config import devices_config
from core import worker_threads, Master
from concurrent.futures import ThreadPoolExecutor
import importlib
import events

thread_pool = ThreadPoolExecutor(max_workers=20)


def config():
    log_config()
    devices_config()


def main():
    config()
    master = Master(thread_pool=thread_pool, workers=worker_threads)
    while True:
        master.run()
        time.sleep(1)


if __name__ == '__main__':
    main()
