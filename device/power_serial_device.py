from constant import PowerConstant
from core import singleton
from .serial_device import SerialDevice


@singleton
class PowerSerialDevice(SerialDevice):
    def __init__(self):
        self.charging_flag = False
        self.electricity = 0
        SerialDevice.__init__(self, port='/dev/ttyAMA0', bps=115200)
    
    def get_result(self):
        self.write_and_open(PowerConstant.POWER_READ)
        value_hex = self.read(size=2)
        # value_hex = bytes(value, "utf-8")
        self.charging_flag = value_hex[1] == PowerConstant.POWER_IS_CHARGING
        self.electricity = int(value_hex[0])
        self.close()
    
    def get_electricity(self):
        return self.electricity
    
    def is_charging(self):
        return self.charging_flag
