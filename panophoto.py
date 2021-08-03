# -*- coding: utf-8 -*-
import io
import json
import os
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
import time
from datetime import datetime, timedelta

import requests
import redis

import socket
import urllib
# import urllib2
import urllib3.connection
import logging

import requests as req
from requests.auth import HTTPDigestAuth

chunk_size = 1024
order_code = None

redis_conn = redis.Redis(host='localhost', port=6379, db=6, decode_responses=True)
MAX_RELOAD_TIMES = 5


def push_message(message):
    redis_conn.publish("ELS_SURFACE_FRONT_MSG", message)


def init_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    BASIC_FORMAT = "%(asctime)s [%(levelname)s]: %(name)s - %(message)s"
    DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter(BASIC_FORMAT, DATE_FORMAT)
    
    chlr = logging.StreamHandler()  # 输出到控制台的handler
    chlr.setFormatter(formatter)
    chlr.setLevel(logging.INFO)  # 也可以不设置，不设置就默认用logger的level
    
    fhlr = logging.FileHandler(
        'E:\\FTPServer\\logs\\{}-panophoto.log'.format(datetime.now().strftime("%Y-%m-%d")))  # 输出到文件的handler
    fhlr.setFormatter(formatter)
    logger.addHandler(chlr)
    logger.addHandler(fhlr)


def push_collect_queue(ossPath, files):
    message = json.dumps({'filesList': files, 'ossPath': ossPath})
    try:
        redis_conn.zadd("ELS_SURFACE_HANDLE::collectQueue", {message: int(time.time() * 1000)})
    except Exception as e:
        logging.error(str(e))


class RicohParams:
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


def get_other_info():
    merchant_code = redis_conn.get("ELS_SURFACE_HANDLE::merchantCode")
    order_code = redis_conn.get("ELS_SURFACE_HANDLE::orderCode")
    return {'merchantCode': merchant_code, "orderCode": order_code}


params = RicohParams()


class Ricoh:
    PHOTO_ADDR = "192.168.10.11"
    HANDLER_ADDR = "127.0.0.1"
    
    def __init__(self, ssid, password, photo_addr="192.168.10.156"):
        self.params = RicohParams()
        self.ssid = ssid
        self.password = password
        self.PHOTO_ADDR = photo_addr
    
    def request_handle(self, url, params):
        headers = {
            "Content-Type": "application/json;charset=utf-8",
        }
        
        response = requests.get(url=url, headers=headers, params=params)
        # push_message("[{}] {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response.text))
        logging.info(response.text)
        return response
    
    def request_camera(self, url, body):
        headers = {
            "Host": "192.168.1.1:80",
            "Content-Type": "application/json;charset=utf-8",
            "Accept": "application/json",
            "Content-Length": str(len(body))
        }
        
        error_time = 0
        response = None
        while error_time < 3:
            try:
                response = requests.post(url=url, auth=(HTTPDigestAuth(self.ssid, self.password)), json=body, timeout=5)
                break
            except Exception as e:
                logging.error(str(e))
            finally:
                error_time += 1
        
        # push_message("[{}] {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response.text))
        if response is None:
            raise Exception("request timeout")
        
        logging.info(response.text)
        
        if not response.text is None:
            try:
                resp = json.loads(response.text)
                if (resp.get('state')) == "error":
                    raise Exception("相机内部错误")
            except Exception as e:
                logging.warning(e)
                raise
        
        return response
    
    def get_info(self):
        url = 'http://{}/osc/info'.format(self.PHOTO_ADDR)
        response = requests.get(url, auth=(HTTPDigestAuth(self.ssid, self.password)))
        try:
            result = response.json()
            logging.info(result)
        except Exception as e:
            logging.error(str(e))
    
    def start_session(self, ):
        body = json.dumps({
            "name": "camera.startSession",
            "parameters": {}
        })
        response = self.request_camera(
            "http://{}/osc/commands/execute".format(self.PHOTO_ADDR), body)
    
    def take_photo(self):
        body = {
            "name": "camera.takePicture"
        }
        response = self.request_camera(
            "http://{}/osc/commands/execute".format(self.PHOTO_ADDR), body)
    
    def get_options(self, ):
        body = {
            "name": "camera.getOptions",
            "parameters": {
                "optionNames": [
                    "fileFormat",
                    "fileFormatSupport",
                    "iso",
                    "shutterSpeed",  # 快门速度
                    "sleepDelay",
                    "aperture"
                ]
            }
        }
        response = self.request_camera(
            "http://{}/osc/commands/execute".format(self.PHOTO_ADDR), body)
    
    def set_options(self, opt=None):
        body = {
            "name": "camera.setOptions",
            "parameters": {
                "options": opt
            },
        }
        if opt is None:
            body = {
                "name": "camera.setOptions",
                "parameters": {
                    "options": {
                        "exposureProgram": 1,
                        "iso": 80,
                        "shutterSpeed": 0.06666666,  # 快门速度 1/15
                        "sleepDelay": 1800,
                        "aperture": 5.6,
                        "_filter": "off",
                        "fileFormat": {"height": 3360, "type": "raw+", "width": 6720}
                    }
                },
            }
        response = self.request_camera(
            "http://{}/osc/commands/execute".format(self.PHOTO_ADDR), body)
    
    def get_image(self, image):
        pass
    
    def compose_images(self, ):
        global order_code, params
        backupOutFile = None
        if not order_code is None:
            backupOutFile = str(params.output_file).replace("D:\\FTPServer\\Data\\",
                                                            "E:\\FTPServer\\History\\{}\\".format(order_code))
        
        _params = {
            "inputFiles": " ".join(params.input_images),
            "outputFilePath": params.output_file,
            "outputFile": params.output_file,
            # "backupOutFile": backupOutFile
        }
        response = self.request_handle(
            "http://{}/surface/resultFile/compose".format(self.HANDLER_ADDR), _params)
        # response = self.request_handle(
        #     "http://{}/surface/resultFile/rawCompose".format(self.HANDLER_ADDR), params)
    
    def check_for_updates(self):
        body = {
            "stateFingerprint": "FIG_0003",
        }
        response = self. \
            request_camera(
            "http://{}/osc/checkForUpdates".format(self.PHOTO_ADDR), body)
    
    def get_state(self, returnLatestFileUrl=False):
        body = {
        }
        response = self.request_camera(
            "http://{}/osc/state".format(self.PHOTO_ADDR), body)
        content = json.loads(response.text)
        # push_message(content._capturedPictures)
        state = content.get("state")
        captureStatus = state.get("_captureStatus")
        if captureStatus == "idle":
            if returnLatestFileUrl is False:
                time.sleep(2)
                return self.get_state(True)
            self.latestFileUrl = state.get("_latestFileUrl")
            if self.latestFileUrl == "" or self.latestFileUrl is None:
                return self.get_state()
            return self.latestFileUrl
        else:
            time.sleep(5)
            return self.get_state()
    
    def delete(self, url):
        body = {
            "name": "camera.delete",
            "parameters": {
                "fileUrls": [url]
            }
        }
        response = self.request_camera(
            "http://{}/osc/commands/execute".format(self.PHOTO_ADDR), body)
    
    def delete_all(self):
        body = {
            "name": "camera.delete",
            "parameters": {
                "fileUrls": ["all"]
            }
        }
        response = self.request_camera(
            "http://{}/osc/commands/execute".format(self.PHOTO_ADDR), body)
    
    def download_file(self, url, output_name=None, suffix="jpg", post_handler=False, output_abspath=None):
        global params
        logging.info("start download file:{}".format(output_name))
        _error_count = 0
        r = None
        while _error_count < 3:
            try:
                r = requests.get(url, stream=True, auth=(HTTPDigestAuth(self.ssid, self.password)), timeout=60)
                break
            except Exception as e:
                logging.error(str(e))
                _error_count += 1
                pass
            time.sleep(2)
        if _error_count == 3 or r is None:
            logging.error("Photo download fail")
            raise Exception("Photo download fail")
        
        # 如果后缀为JPG
        if suffix is "jpg":
            params.photo_index_add()
        # 检查路径地址
        # ticks = int(time.time())
        outputImage = "E:\\FTPServer\\Cache\\Insta360\\{}".format(params.ticks)
        ticks = int(time.time())
        if not os.path.exists(outputImage):
            os.makedirs(outputImage)
        params.outputImage = outputImage
        logging.info("outputImage:{}".format(outputImage))
        
        if output_name is None:
            output_name = "fuse_img{}".format(params.photo_index)
        
        if not os.path.exists("D:\\FTPServer\\Data\\Insta360"):
            dirname = "D:\\FTPServer\\Data\\Insta360"
            os.mkdir(dirname)
            logging.info(dirname)
        
        if not os.path.exists("D:\\FTPServer\\Data\\Insta360\\{}".format(params.ticks)):
            dirname = "D:\\FTPServer\\Data\\Insta360\\{}".format(params.ticks)
            os.mkdir(dirname)
            logging.info("mkdir {}".format(dirname))
        
        if output_abspath is None:
            output_abspath = "E:\\FTPServer\\Cache\\Insta360\\{}\\{}.{}".format(params.ticks, output_name, suffix)
        
        reload_times = 0
        while reload_times < MAX_RELOAD_TIMES:
            with open(output_abspath, 'wb') as fd:
                for chunk in r.iter_content(chunk_size):
                    fd.write(chunk)
            file_size = os.path.getsize(output_abspath)
            if (file_size / float(1024 * 1024)) > 1:
                reload_times = MAX_RELOAD_TIMES
            reload_times += 1
            time.sleep(5)
        
        if reload_times == MAX_RELOAD_TIMES:
            raise Exception("捕获图片文件过小")
        
        if post_handler:
            params.input_images_append(output_abspath)
        
        params.output_file = "D:\\FTPServer\\Data\\Insta360\\{}\\pano.jpg".format(params.ticks)


def run_ricoh(ssid, password, photo_addr):
    ricoh = Ricoh(ssid, password, photo_addr)
    push_message("获取相机参数")
    ricoh.get_info()
    ricoh.get_options()
    push_message("设置相机参数")
    ricoh.set_options({
        "exposureProgram": 1,
        "sleepDelay": 1800,
        "_filter": "hdr",
        "fileFormat": {"height": 3360, "type": "raw+", "width": 6720}
    })
    time.sleep(5)
    push_message("开始拍照")
    ricoh.take_photo()
    time.sleep(5)
    latestFileUrl = ricoh.get_state()
    push_message("拍摄成功，开始获取图片")
    # push_message(latestFileUrl)
    ricoh.download_file(latestFileUrl, "pano",
                        output_abspath="D:\\FTPServer\\Data\\Insta360\\{}\\pano.jpg".format(params.ticks))
    # latestFileUrl = str(latestFileUrl).replace("JPG", "DNG")
    push_message("图片下载完成")
    # ricoh.download_file(latestFileUrl, "pano", "DNG")
    ricoh.delete_all()
    push_message("清理图片")


def run_ricoh_burst(ssid, password, photo_addr):
    other_info = get_other_info()
    
    options = [
        {
            "exposureProgram": 1,
            "iso": 80,
            "shutterSpeed": 0.03333333,  # 快门速度 1/30
            "sleepDelay": 1800,
            "aperture": 5.6,
            "_filter": "off",
            "fileFormat": {"height": 3360, "type": "raw+", "width": 6720}
        },
        {
            "exposureProgram": 1,
            "iso": 80,
            "shutterSpeed": 0.1,  # 快门速度 1/10
            "sleepDelay": 1800,
            "aperture": 5.6,
            "_filter": "off",
            "fileFormat": {"height": 3360, "type": "raw+", "width": 6720}
        },
        {
            "exposureProgram": 1,
            "iso": 80,
            "shutterSpeed": 0.25,  # 快门速度 1/4
            "sleepDelay": 1800,
            "aperture": 5.6,
            "_filter": "off",
            "fileFormat": {"height": 3360, "type": "raw+", "width": 6720}
        },
    ]
    
    # pool = mp.Pool(processes=20)
    pool = ThreadPoolExecutor(max_workers=8)
    
    all_result = []
    
    ricoh = Ricoh(ssid, password, photo_addr)
    
    ricoh.get_info()
    ricoh.get_options()
    push_message("设置相机参数")

    latest_file_urls = []
    output_abspaths = []
    for i in range(len(options)):
        push_message("第{0}重拍摄测试开始".format((i+1)))
        option = options[i]
        ricoh.set_options(option)
        time.sleep(1)
        ricoh.take_photo()
        time.sleep(5)
        latest_file_url = ricoh.get_state()
        latest_file_url = str(latest_file_url).replace("JPG", "DNG")
        latest_file_urls.append(latest_file_url)
        print(latest_file_url)
        output_name = "fuse_img" + str(i + 1)
        output_abspath = "E:\\FTPServer\\Cache\\Insta360\\{}\\{}.{}".format(params.ticks, output_name,
                                                                            "DNG")
        output_abspaths.append(output_abspath)
        push_message("第{0}重拍摄测试结束".format((i+1)))
        # res = pool.submit(ricoh.download_file, latest_file_url, output_name, "DNG", True, output_abspath)
        # all_result.append(res)
    
    # for result in all_result:
    #     result.done()
    #     result.result(timeout=70)
    
    ricoh.set_options({
        "exposureProgram": 1,
        "sleepDelay": 1800,
        "_filter": "hdr",
        "fileFormat": {"height": 3360, "type": "raw+", "width": 6720}
    })
    time.sleep(5)
    push_message("开始拍照")
    ricoh.take_photo()
    time.sleep(5)
    latestFileUrl = ricoh.get_state()
    push_message("拍摄成功，开始获取图片")
    # push_message(latestFileUrl)
    ricoh.download_file(url=latestFileUrl, output_name="pano",
                        output_abspath="D:\\FTPServer\\Data\\Insta360\\{}\\pano.jpg".format(params.ticks))

    # shutil.copy("D:\\FTPServer\\Data\\Insta360\\{}\\pano.jpg".format(params.ticks),
    #             "E:\\FTPServer\\Cache\\Insta360\\{}\\source_img.jpg".format(params.ticks))
    
    # with open("E:\\FTPServer\\Cache\\Insta360\\{}\\info.json".format(params.ticks), "w") as f:
    #     json.dump(other_info, f)
    #
    # output_abspaths.append("E:\\FTPServer\\Cache\\Insta360\\{}\\source_img.jpg".format(params.ticks))
    # output_abspaths.append("E:\\FTPServer\\Cache\\Insta360\\{}\\info.json".format(params.ticks))
    # push_collect_queue("collection/PanoCamera/{}".format(params.ticks), output_abspaths)
    pool.shutdown()
    ricoh.delete_all()


_default_create_socket = socket.create_connection
_urllib3_create_socket = urllib3.connection.connection.create_connection

SOURCE_ADDRESS = ("192.168.1.30", 0)


# SOURCE_ADDRESS = ("192.168.10.2", 0)


def default_create_connection(*args, **kwargs):
    try:
        del kwargs["socket_options"]
    except Exception as e:
        logging.error(e)
    in_args = False
    if len(args) >= 3:
        args = list(args)
        args[2] = SOURCE_ADDRESS
        args = tuple(args)
        in_args = True
    if not in_args:
        kwargs["source_address"] = SOURCE_ADDRESS
    # push_message("args", args)
    # push_message("kwargs", str(kwargs))
    return _default_create_socket(*args, **kwargs)


default_config = {
    "ssid": "THETAYN11100867.OSC",
    "needCompose": True,
    "bindNetwork": False,
    "options": {
        "captureMode": "image",
        "exposureProgram": 1,
        "iso": 80,
        "shutterSpeed": 0.06666666,
        "sleepDelay": 1800,
        "aperture": 5.6
    }
}

config_file_path = "D:\\FTPServer\\Config\\panophoto.json"


def start(config):
    logging.info("start running panophoto.py")
    push_message("连接相机网络")
    need_compose = config.get("needCompose", False)
    try:
        if need_compose:
            run_ricoh_burst(config.get("ssid"), config.get("password"), config.get("photoAddr"))
        else:
            run_ricoh(config.get("ssid"), config.get("password"), config.get("photoAddr"))
    except Exception as e:
        logging.error(str(e))
        raise e
    finally:
        stop_time = time.time()
        logging.info("stop running panophoto.py,runing time: {}".format(stop_time - start_time))
        logging.info("wlan disconnect")
        
        # socket.create_connection = _default_create_socket
        # urllib3.connection.connection.create_connection = _urllib3_create_socket


if __name__ == '__main__':
    init_logging()
    error_count = 0
    push_message("开始内饰拍摄")
    logging.info("start running panophoto.py")
    start_time = time.time()
    if not os.path.exists(config_file_path):
        text = json.dumps({})
        with open(config_file_path) as f:
            json.dump(obj=default_config, fp=f)
    push_message("初始化网络")
    with open(config_file_path) as f:
        config = json.load(f)
    
    max_error_count = config.get('max_error_count', 5)
    
    while error_count < max_error_count:
        try:
            push_message("第{}次内饰拍摄开始".format(error_count + 1))
            logging.info("Take Photo:{} Time".format(error_count + 1))
            start(config)
            push_message("第{}次内饰拍摄完成".format(error_count + 1))
            break
        except Exception as e:
            push_message("第{}次内饰拍摄失败".format(error_count + 1))
            error_count += 1
            time.sleep(10)
            logging.error(str(e))
    
    if error_count == max_error_count:
        raise Exception("take photo error")
