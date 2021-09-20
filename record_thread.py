from core import worker
from device.sqlite_device import SqliteDevice
from mapper.record_mapper import RecordMapper
from utils import CmdUtils, DateTimeUtils
from .base_thread import BaseThread


@worker()
class RecordThread(BaseThread):
    def __init__(self):
        BaseThread.__init__(self, {
            "is_loop": True,
            "delay_time": 60,
            "name": "RecordThread"
        })
        self.is_loop = True
    
    def _destroy(self, result):
        pass
    
    def _execute(self):
        cpu_user = CmdUtils.cmd_read("top -b -n 1 | grep Cpu | awk '{print $2}' | cut -f 1 -d \"%\"")
        cpu_system = CmdUtils.cmd_read("top -b -n 1 | grep Cpu | awk '{print $4}' | cut -f 1 -d \"%\"")
        cpu_idle = CmdUtils.cmd_read("top -b -n 1 | grep Cpu | awk '{print $8}' | cut -f 1 -d \"%\"")
        
        mem_total = CmdUtils.cmd_read("free | grep Mem | awk '{print $2}'")
        mem_sys_used = CmdUtils.cmd_read("free | grep Mem | awk '{print $3}'")
        mem_sys_free = CmdUtils.cmd_read("free | grep Mem | awk '{print $4}'")
        mem_user_used = CmdUtils.cmd_read("free | sed -n 3p | awk '{print $3}'")
        mem_user_free = CmdUtils.cmd_read("free | sed -n 3p | awk '{print $4}'")
        
        disk_sda_rs = CmdUtils.cmd_read("iostat -kx | grep mmcblk0| awk '{print $3}'")
        disk_sda_ws = CmdUtils.cmd_read("iostat -kx | grep mmcblk0| awk '{print $4}'")
        
        # 写入Redis
        # 写入当前内容
        create_time = DateTimeUtils.get_format_now()
        expired_time = DateTimeUtils.get_format_sub_datetime(30, '%Y-%m-%d %H:%M:%S.%f')
        
        sql_cmd = RecordMapper.INSERT_RECORD.format(create_time,
                                                    expired_time,
                                                    cpu_user, cpu_system,
                                                    cpu_idle, mem_total,
                                                    mem_sys_used,
                                                    mem_sys_free,
                                                    mem_user_used,
                                                    mem_user_free,
                                                    disk_sda_rs,
                                                    disk_sda_ws)
        sql_device = SqliteDevice()
        
        sql_device.execute(sql_cmd)
