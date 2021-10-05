from core import worker_threads
from core.aop import configure
import threading
from concurrent.futures import ThreadPoolExecutor



thread_pool = ThreadPoolExecutor(max_workers=8)

@configure(topic="thread_config")
def thread_config():
    for thread in worker_threads:
        res = threading.Thread(thread)
