from core import worker_threads
from threads.base_thread import BaseThread
import threading
from concurrent.futures import ThreadPoolExecutor



thread_pool = ThreadPoolExecutor(max_workers=8)


def thread_config():
    for thread in worker_threads:
        res = threading.Thread(thread)
