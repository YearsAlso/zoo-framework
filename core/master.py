import threading

from threads.base_thread import BaseThread
from utils import LogUtils


class Master(object):
    _dict_lock = threading.Lock()
    worker_dict = {}
    
    def __init__(self, thread_pool, workers: list):
        self.workers = workers
        self.thread_pool = thread_pool
    
    def worker_defend(self, thread):
        Master.worker_dict[thread.name] = thread
        thread.run()
        Master.worker_dict[thread.name] = None
    
    def run(self):
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
