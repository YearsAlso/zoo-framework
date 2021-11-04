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
            sleep(self.loop_interval)
