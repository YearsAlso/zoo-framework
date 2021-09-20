import sqlite3

from core.aop import singleton
from utils import LogUtils
import threading


@singleton
class SqliteDevice(object):
    _execute_lock = threading.Lock()
    
    def __init__(self, sql_path="/home/pi/Els/db/els_timer.db"):
        self.sqlite_path = sql_path
    
    def _connect(self):
        self._conn = sqlite3.connect(self.sqlite_path)
    
    def _close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception as e:
                LogUtils.warning(str(e), self.__class__.__name__)
    
    def execute(self, sql_cmd):
        self._connect()
        with self._execute_lock:
            try:
                cur = self._conn.cursor()
                cur.execute(sql_cmd)
                self._conn.commit()
            except Exception as e:
                LogUtils.warning(str(e), self.__class__.__name__)
            finally:
                self._close()
