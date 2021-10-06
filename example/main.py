import threading
import time

from zoo_framework.conf import log_config
from zoo_framework.conf import thread_config
from zoo_framework.core import worker_threads, Master
from concurrent.futures import ThreadPoolExecutor
import importlib

thread_pool = ThreadPoolExecutor(max_workers=20)

def main():
    master = Master(worker_count=30)
    master.run()


if __name__ == '__main__':
    main()
