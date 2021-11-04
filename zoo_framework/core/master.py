import threading
from concurrent.futures import ThreadPoolExecutor
from time import sleep

from .aop import worker_threads, ParamsFactory, config_funcs


class Master(object):
    _dict_lock = threading.Lock()
    worker_dict = {}

    def __init__(self, worker_count=1, loop_interval=1):
        thread_pool = ThreadPoolExecutor(max_workers=worker_count)
        self.workers = worker_threads
        self.thread_pool = thread_pool
        self.loop_interval = loop_interval
        # load params
        ParamsFactory("./config.json")
        self.config()

    def config(self):
        for key, value in config_funcs.items():
            value()

    def worker_defend(self, master, thread):
        self._dict_lock.acquire(blocking=True, timeout=1)
        master.worker_dict[thread.name] = thread
        self._dict_lock.release()

        thread.run()

        self._dict_lock.acquire(blocking=True, timeout=1)
        master.worker_dict[thread.name] = None
        self._dict_lock.release()

    def _run(self):
        workers = []
        for thread in self.workers:
            if thread.is_loop:
                workers.append(thread)
            if self.worker_dict.get(thread.name) is None:
                t = threading.Thread(group=None, target=self.worker_defend, args=(self, thread,))
                t.start()

        self.workers = workers

    def run(self):
        while True:
            self._run()
            if self.loop_interval > 0:
                sleep(self.loop_interval)
