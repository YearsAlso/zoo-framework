from multiprocessing import Manager, Lock


class ThreadSafeDict:
    """
    Thread safe dictionary
    """

    def __init__(self, _dict=None):
        if _dict is None:
            _dict = {}
        self._lock = Lock()
        self._dict = _dict

    def __getitem__(self, key):
        with self._lock:
            return self._dict[key]

    def __setitem__(self, key, value):
        with self._lock:
            self._dict[key] = value

    def __delitem__(self, key):
        with self._lock:
            del self._dict[key]

    def __len__(self):
        with self._lock:
            return len(self._dict)

    def __contains__(self, key):
        with self._lock:
            return key in self._dict

    def keys(self):
        with self._lock:
            return list(self._dict.keys())

    def values(self):
        with self._lock:
            return list(self._dict.values())

    def items(self):
        with self._lock:
            return list(self._dict.items())

    def get(self, handler_name):
        with self._lock:
            return self._dict.get(handler_name)

    def has_key(self, key):
        with self._lock:
            return key in self._dict
