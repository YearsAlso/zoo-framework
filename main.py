import threading
import time

from conf import log_config
from conf import thread_config
from core import worker_threads, Master
from concurrent.futures import ThreadPoolExecutor
import importlib

thread_pool = ThreadPoolExecutor(max_workers=20)

def main():
    master = Master(30)
    master.run()


if __name__ == '__main__':
    main()
