import threading
from concurrent.futures import ThreadPoolExecutor
from time import sleep

from threads.base_thread import BaseThread
from utils import LogUtils
from core import worker_threads, ParamsFactory


class Master(object):
    _dict_lock = threading.Lock()
    worker_dict = {}

    def __init__(self, worker_num=1, loop_delay=1):
        thread_pool = ThreadPoolExecutor(max_workers=worker_num)
        self.workers = worker_threads
        self.thread_pool = thread_pool
        self.loop_delay = loop_delay
        # 加载params
        ParamsFactory("./config.json")

    def worker_defend(self, thread):
        Master.worker_dict[thread.name] = thread
        thread.run()
        Master.worker_dict[thread.name] = None

    def _run(self):
        workers = []
        results = []
        for thread in self.workers:
            if thread.is_loop:
                workers.append(thread)
            if Master.worker_dict.get(thread.name) is None:
                t = threading.Thread(group=None, target=self.worker_defend, args=(thread,))
                t.start()

        self.workers = workers

        # for result in results:
        #     result.result()

    def run(self):
        while True:
            self._run()
            sleep(self.loop_delay)
