import os
import time

from core import worker
from device import SqliteDevice
from mapper import ClearMapper
from .base_thread import BaseThread
from utils import DateTimeUtils, LogUtils


@worker()
class CleanerThread(BaseThread):
    def __init__(self):
        BaseThread.__init__(self, {
            "is_loop": True,
            "delay_time": 60,
            "name": "CleanerThread"
        })
        self.is_loop = True
    
    def clean_recorder(self):
        sql_cmd = ClearMapper.DELETE_RECORD.format(
            DateTimeUtils.get_format_now())
        sql_device = SqliteDevice()
        sql_device.execute(sql_cmd)
    
    def clean_data(self):
        file_list = os.listdir("/home/pi/data")
        
        file_list.sort(reverse=True)
        
        file_length = len(file_list)
        if file_length > 100:
            del_files = file_list[100:-1]
            
            for file_abspath in del_files:
                os.removedirs(file_abspath)
    
    def clean_log(self, path):
        # 文件夹内的子文件夹
        # 遍历，如果文件夹的创建时间小于设置时间的就会删除
        file_list = os.listdir(path)
        
        del_files = []
        
        for file_name in file_list:
            file_abspath = path + '/' + file_name
            create_time = os.path.getctime(file_abspath)
            create_time = time.localtime(create_time)
            create_time = time.strftime('%Y-%m-%d %H:%M:%S', create_time)
            expired_time = DateTimeUtils.get_format_sub_datetime(-14, '%Y-%m-%d %H:%M:%S')
            if create_time < expired_time:
                del_files.append(file_abspath)
        
        for file_abspath in del_files:
            os.system("sudo rm -R " + file_abspath)
    
    def _execute(self):
        self.clean_log("/var/log/tiretouch/pages")
        self.clean_log("/var/log/tiretouch/service")
        self.clean_log("/var/log/tiretouch/uploader")
        self.clean_recorder()
        self.clean_data()