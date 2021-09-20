from core import singleton
import serial


class SerialDevice:
    def __init__(self, port: str, bps: int, timex=None):
        self.serial = None
        self.port = port
        self.bps = bps
        self.timex = timex
    
    def open(self):
        if self.serial is None:
            self.serial = serial.Serial(self.port, self.bps, timeout=self.timex)
    
    def is_open(self):
        if self.serial is None:
            return False
        return self.serial.isOpen()
    
    def close(self):
        if not self.is_open():
            return True
        self.serial.close()
        self.serial = None
    
    def read(self, size=1):
        if not self.is_open():
            raise Exception("serial is not open")
        return self.serial.read(size)
    
    def readline(self):
        if not self.is_open():
            raise Exception("serial is not open")
        return self.serial.readline()
    
    def read_hex(self):
        if not self.is_open():
            raise Exception("serial is not open")
        return self.serial.read().hex()
    
    def write(self, data: str):
        if not self.is_open():
            raise Exception("serial is not open")
        self.serial.write(data)
    
    def read_and_open(self):
        self.open()
        return self.read()
    
    def write_and_open(self, data):
        if not self.is_open():
            self.open()
        return self.write(data)
