import pywifi
from pywifi import const

from core import singleton


@singleton
class WifiDevice:
    def __init__(self):
        self.ifaces = self.init()
    
    @staticmethod
    def init():
        wifi = pywifi.PyWiFi()
        ifaces_list = wifi.interfaces()
        ifaces = None
        for i in range(0, len(ifaces_list)):
            if ifaces_list[i].name() == "wlan0":
                ifaces = ifaces_list[i]
        return ifaces
    
    def scan(self):
        if self.ifaces is None:
            return
        
        self.ifaces.scan()  # 扫描
        bessis = self.ifaces.scan_results()
        for data in bessis:
            if data.ssid.strip() == "":
                continue
    
    def get_wifi_state(self):
        if self.ifaces is None:
            return const.IFACE_DISCONNECTED
        return self.ifaces.status()
    
    def is_connected(self):
        return self.get_wifi_state() == const.IFACE_CONNECTED
    
    def get_wifi_info(self):
        if self.ifaces is None:
            return None
        
        self.ifaces.scan()  # 扫描
        bessis = self.ifaces.scan_results()
        for data in bessis:
            if data.ssid.strip() == "":
                continue
            return data
    
    def disconnect(self):
        if self.ifaces is not None:
            self.ifaces.disconnect()
    
    def connect(self, ssid, key):
        profile = pywifi.Profile()  # 配置文件
        profile.ssid = ssid
        tmp_profile = self.ifaces.add_network_profile(profile)  # 加载配置文件
        self.ifaces.connect(tmp_profile)  # 连接
    
    # def close(self):
    #     if self.ifaces is not None:
    #         self.ifaces.close()
