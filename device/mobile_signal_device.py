import re
import time

# import RPi.GPIO as GPIO

from constant import MobileSignalConstant, StateMachineConstant
from core import singleton
from .serial_device import SerialDevice


@singleton
class MobileSignalDevice(SerialDevice):
    def __init__(self):
        SerialDevice.__init__(self, port="/dev/ttyUSB2", bps=115200)
        from statemachine.state_machine_manager import StateMachineManager
        power_on = StateMachineManager().get_topic_value(StateMachineConstant.MOBILE_SIGNAL_TOPIC, "power—on")
        if power_on:
            # GPIO.setmode(GPIO.BOARD)
            # GPIO.setup(11, GPIO.OUT)
            # GPIO.output(11, GPIO.HIGH)
            time.sleep(10)
            StateMachineManager().set_topic_value(StateMachineConstant.MOBILE_SIGNAL_TOPIC, "power—on", True)

    # 拨号上网
    def dial_network(self):
        # GPIO.setmode(GPIO.BOARD)
        # GPIO.setup(11, GPIO.OUT)
        # GPIO.output(11, GPIO.HIGH)
        time.sleep(10)
        # self.write_and_open(b'AT+CNMP=51\n\r')
        self.close()
    
    def is_connected(self):
        self.write_and_open(MobileSignalConstant.MOBILE_READ_SIGNAL_CONNECTED)
        self.readline()
        result = self.readline()
        self.readline()
        success = self.readline()
        self.close()
        if b",1" in result and b"OK" in success:
            return True
        return False
    
    # 信号分贝（强度）
    def signal_decibel(self):
        self.write_and_open(MobileSignalConstant.MOBILE_READ_SIGNAL_DECIBEL)
        self.readline()
        result = self.readline()
        self.readline()
        success = self.readline()
        
        self.close()
        if b"OK" in success and b"+CSQ:" in result:
            result = str(result).replace("+CSQ:", "")
            rssi = re.search(r'\d{1,}', result)
            return int(rssi.group(0))
        return -1
