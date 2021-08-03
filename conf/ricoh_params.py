import threading
import time

from core.aop import options
from core.params.base_params import BaseParams


@options(name="RicohParams")
class RicohParams(BaseParams):
    _instance_lock = threading.Lock()
    _photo_index_lock = threading.Lock()
    _input_images_Lock = threading.Lock()
    photo_index = 0
    ticks = int(time.time())
    input_images = []
    output_image = ""
    output_file = ""
    order_code = ""
    merchant_code = ""
    
    def __new__(cls, *args, **kwargs):
        with cls._instance_lock:
            if not hasattr(RicohParams, "_instance"):
                cls._instance = super().__new__(cls)
        return cls._instance
    
    def input_images_append(self, value):
        with self._input_images_Lock:
            self.input_images.append(value)
    
    def photo_index_add(self, value=1):
        with self._photo_index_lock:
            self.photo_index += value