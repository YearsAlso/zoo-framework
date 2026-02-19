"""
thread_safe_dict - zoo_framework/utils/thread_safe_dict.py

模块功能描述：
TODO: 添加模块功能描述

作者: XiangMeng
版本: 0.5.1-beta
"""

from multiprocessing import Lock

_lock = Lock()


class ThreadSafeDict:
    """Thread safe dictionary."""

    def __init__(self, _dict=None):
        if _dict is None:
            _dict = {}
        self._dict = _dict

    def __getitem__(self, key):
        with _lock:
            return self._dict[key]

    def __setitem__(self, key, value):
        with _lock:
            self._dict[key] = value

    def __delitem__(self, key):
        with _lock:
            del self._dict[key]

    def __len__(self):
        with _lock:
            return len(self._dict)

    def __contains__(self, key):
        with _lock:
            return key in self._dict

    def keys(self):
        with _lock:
            return list(self._dict.keys())

    def values(self):
        with _lock:
            return list(self._dict.values())

    def items(self):
        with _lock:
            return list(self._dict.items())

    def get(self, handler_name):
        with _lock:
            return self._dict.get(handler_name)

    def has_key(self, key):
        with _lock:
            return key in self._dict

    def pop(self, key):
        with _lock:
            return self._dict.pop(key)

    def get_values(self):
        with _lock:
            return list(self._dict.values())

    def get_keys(self):
        with _lock:
            return list(self._dict.keys())
