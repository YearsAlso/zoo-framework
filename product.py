# -*- coding: utf-8 -*-

import json
import os
import sys
import time
from datetime import datetime, timedelta

import requests

import socket
import urllib
# import urllib2
import urllib3.connection
import logging

import requests as req

chunk_size = 1024
order_code = None


class Insta360:
    PHOTO_ADDR = "192.168.43.1:20000"
    
    def __init__(self):
        self.Fingerprint = "null"
    
    def request_camera(self, url, body):
        headers = {
            "Content-Type": "application/json;charset=utf-8",
            'X-XSRF-Protected': "1",
            'HOST': '192.168.43.1:20000',
            'Pragma': 'no-cache',
            'Accept': 'text/xml, application/xml, application/xhtml+xml, text/html;q=0.9, text/plain;q=0.8, text/css, image/png, image/jpeg, image/gif;q=0.8, application/x-shockwave-flash, video/mp4;q=0.9, flv-application/octet-stream;q=0.8, video/x-flv;q=0.7, audio/mp4, application/futuresplash, */*;q=0.5, application/x-mpegURL',
            'Accept-Encoding': 'gzip,deflate',
            'User-Agent': 'Apache-HttpClient/4.4',
            'Referer': 'app:/Insta360Pro.swf',
            'x-flash-version': '22,0,0,175',
            'Connection': 'Keep-Alive',
            "Content-Length": str(len(body)),
            "Fingerprint": self.Fingerprint
        }
        
        response = requests.post(url=url, headers=headers, data=body)
        print(response.text)
        return response
    
    def get_connect(self, ):
        headers = {}
        response = requests.post(url="http://{}/osc/commands/execute".format(self.PHOTO_ADDR), headers=headers, json={
            "name": "camera._connect",
            "parameters": {
                "time_zone": "GMT+08:00",
                "hw_time": (datetime.now() + timedelta(hours=-8)).strftime("%Y-%m-%d %H:%M:%S"),
                "date_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        })
        results = json.loads(response.text).get("results")
        if results is None:
            return
        
        self.Fingerprint = results.get("Fingerprint")
    
    def disconnect(self, ):
        response = self.request_camera("http://{}/osc/commands/execute".format(self.PHOTO_ADDR), json.dumps({
            "name": "camera._disconnect",
        }))
        results = json.loads(response.text)
    
    def set_options(self, ):
        body = json.dumps({
            "name": "camera._setOptions",
            "parameters": {
                "value": True,
                "property": "stabilization"
            }
        })
        response = self.request_camera(
            "http://{}/osc/commands/execute".format(self.PHOTO_ADDR), body)
    
    def set_custom(self, ):
        body = json.dumps({
            "name": "camera._setCustom",
            "parameters": {
                "name": "camera._takePicture",
                "parameters": {
                    "stabilization": False,
                    "stiching": {
                        "height": 3840,
                        "mode": "pano",
                        "algorithm": "opticalFlow",
                        "mime": "jpeg",
                        "width": 7680
                    },
                    "origin": {"height": 3000, "saveOrigin": True, "mime": "jpeg", "width": 4000},
                    "bracket": {"min_ev": -32, "count": 5, "max_ev": 32, "enable": True},
                    "delay": 0,
                    "properties": {
                        "len_param": {
                            "iso_cap": 0,
                            "sharpness": 0,
                            "brightness": 0,
                            "contrast": 64,
                            "saturation": 64,
                            "hue": 0,
                            "aaa_mode": 1,
                            "ev_bias": 0,
                            "iso_value": 0,
                            "stabilization": 1,
                            "shutter_value": 0,
                            "wb": 0
                        }, "audio_gain": 64
                    }
                }
            }
        })
        response = self.request_camera(
            "http://{}/osc/commands/execute".format(self.PHOTO_ADDR), body)
    
    def take_photo(self, ):
        body = json.dumps({
            "name": "camera._takePicture",
            "parameters": {
                "stiching": {
                    "mime": "jpeg",
                    "height": 3840,
                    "mode": "pano",
                    "width": 7680,
                    "algorithm": "opticalFlow"
                },
                "origin": {"mime": "jpeg", "height": 3000, "width": 4000, "saveOrigin": True},
                "stabilization": False,
                "delay": 0,
                "bracket": {"count": 5, "max_ev": 32, "enable": True, "min_ev": -32}
            }
        })
        response = self.request_camera(
            "http://{}/osc/commands/execute".format(self.PHOTO_ADDR), body)
    
    def get_image(self, ):
        body = json.dumps({
            "name": "camera.listFiles",
            "parameters": {
                "fileType": "all",
                "path": "/mnt/sdcard",
                "entryCount": 50,
                "maxThumbSize": 100
            }
        })
        response = self.request_camera(
            "http://{}/osc/commands/execute".format(self.PHOTO_ADDR), body)
        try:
            results = json.loads(response.text).get("results")
            if results.get("totalEntries") > 36:
                entries = results.get("entries")
                for i in range(36):
                    file_name = entries[i].get("name")
                    file_url = entries[i].get("fileUrl")
                    if str(file_name).find("pano") != -1:
                        self.latestFileUrl = file_url
                        return "http://192.168.43.1:8000" + file_url + "/" + file_name
        except:
            pass
        return self.get_image()
    
    def download_file(self, url=""):
        if url is None:
            if self.latestFileUrl is None:
                raise Exception("download file url is null")
            else:
                url = self.latestFileUrl
        
        r = requests.get(url, stream=True)
        
        # 检查路径地址
        if not os.path.exists("D:\\FTPServer\\Data\\Insta360"):
            os.makedirs("D:\\FTPServer\\Data\\Insta360")
        with open("D:\\FTPServer\\Data\\Insta360\\pano.jpg", 'wb') as fd:
            for chunk in r.iter_content(chunk_size):
                fd.write(chunk)
    
    def delete_file(self, ):
        body = json.dumps({
            "name": "camera._deleteFile",
            "parameters": {
                "dir": [
                    self.latestFileUrl
                ]
            }
        })
        print(self.latestFileUrl)
        response = self.request_camera(
            url="http://{}/osc/commands/execute".format(self.PHOTO_ADDR), body=body)


def run_insta360():
    insta360 = Insta360()
    insta360.get_connect()
    insta360.set_options()
    insta360.set_custom()
    insta360.take_photo()
    insta360.disconnect()
    time.sleep(30)
    insta360.get_connect()
    file_name = insta360.get_image()
    insta360.download_file(file_name)
    time.sleep(3)
    insta360.delete_file()
    # 删除数据


logging.basicConfig(filename='E:\\FTPServer\\logs\\{}-panophoto.log'.format(datetime.now().strftime("%Y-%m-%d")),
                    level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(name)s - %(message)s')


class Ricoh:
    PHOTO_ADDR = "192.168.1.1:80"
    HANDLER_ADDR = "192.168.1.30:9299"
    
    def __init__(self):
        self.photo_index = 0
        self.ticks = int(time.time())
        self.inputImages = []
        self.outputImage = ""
    
    def request_handle(self, url, params):
        headers = {
            "Content-Type": "application/json;charset=utf-8",
        }
        
        response = requests.get(url=url, headers=headers, params=params)
        # print("[{}] {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response.text))
        logging.info(response.text)
        return response
    
    def request_camera(self, url, body):
        headers = {
            "Host": "192.168.1.1:80",
            "Content-Type": "application/json;charset=utf-8",
            "Accept": "application/json",
            "Content-Length": str(len(body)),
            'Connection': 'close',
        }
        
        response = requests.post(url=url, headers=headers, data=body)
        # print("[{}] {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), response.text))
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
    
    def start_session(self, ):
        body = json.dumps({
            "name": "camera.startSession",
            "parameters": {}
        })
        response = self.request_camera(
            "http://{}/osc/commands/execute".format(self.PHOTO_ADDR), body)
    
    def take_photo(self):
        body = json.dumps({
            "name": "camera.takePicture"
        })
        response = self.request_camera(
            "http://{}/osc/commands/execute".format(self.PHOTO_ADDR), body)
    
    def get_options(self, ):
        body = json.dumps({
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
        })
        response = self.request_camera(
            "http://{}/osc/commands/execute".format(self.PHOTO_ADDR), body)
    
    def set_options(self, opt=None):
        body = json.dumps({
            "name": "camera.setOptions",
            "parameters": {
                "options": opt
            },
        })
        if opt is None:
            body = json.dumps({
                "name": "camera.setOptions",
                "parameters": {
                    "options": {
                        "exposureProgram": 1,
                        "iso": 80,
                        "shutterSpeed": 0.06666666,  # 快门速度
                        "sleepDelay": 1800,
                        "aperture": 5.6,
                        "fileFormat": {"height": 3360, "type": "raw+", "width": 6720}
                    }
                },
            })
        response = self.request_camera(
            "http://{}/osc/commands/execute".format(self.PHOTO_ADDR), body)
    
    def get_image(self, image):
        pass
    
    def compose_images(self, ):
        global order_code
        backupOutFile = None
        if not order_code is None:
            backupOutFile = str(self.outputFile).replace("D:\\FTPServer\\Data\\",
                                                         "E:\\FTPServer\\History\\{}\\".format(order_code))
        params = {
            "inputFiles": " ".join(self.inputImages),
            "outputFilePath": self.outputFile,
            "outputFile": self.outputFile,
            # "backupOutFile": backupOutFile
        }
        response = self.request_handle(
            "http://{}/surface/resultFile/compose".format(self.HANDLER_ADDR), params)
        # response = self.request_handle(
        #     "http://{}/surface/resultFile/rawCompose".format(self.HANDLER_ADDR), params)
    
    def check_for_updates(self):
        body = json.dumps({
            "stateFingerprint": "FIG_0003",
        })
        response = self. \
            request_camera(
            "http://{}/osc/checkForUpdates".format(self.PHOTO_ADDR), body)
    
    def get_state(self, returnLatestFileUrl=False):
        body = json.dumps({
        })
        response = self.request_camera(
            "http://{}/osc/state".format(self.PHOTO_ADDR), body)
        content = json.loads(response.text)
        # print(content._capturedPictures)
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
            time.sleep(10)
            return self.get_state()
    
    def delete(self, url):
        body = json.dumps({
            "name": "camera.delete",
            "parameters": {
                "fileUrls": [url]
            }
        })
        response = self.request_camera(
            "http://{}/osc/commands/execute".format(self.PHOTO_ADDR), body)
    
    def delete_all(self):
        body = json.dumps({
            "name": "camera.delete",
            "parameters": {
                "fileUrls": ["all"]
            }
        })
        response = self.request_camera(
            "http://{}/osc/commands/execute".format(self.PHOTO_ADDR), body)
    
    def download_file(self, url, output_name=None, suffix="jpg", post_handler=False):
        r = requests.get(url, stream=True)
        if suffix is "jpg":
            self.photo_index += 1
        # 检查路径地址
        # ticks = int(time.time())
        outputImage = "E:\\FTPServer\\Cache\\Insta360\\{}".format(self.ticks)
        ticks = int(time.time())
        if not os.path.exists(outputImage):
            os.makedirs(outputImage)
        self.outputImage = outputImage
        
        if output_name is None:
            output_name = "fuse_img{}".format(self.photo_index)
        
        inputImage = "E:\\FTPServer\\Cache\\Insta360\\{}\\{}.{}".format(self.ticks, output_name, suffix)
        with open(inputImage, 'wb') as fd:
            for chunk in r.iter_content(chunk_size):
                fd.write(chunk)
        if post_handler:
            self.inputImages.append(inputImage)
        
        self.outputFile = "D:\\FTPServer\\Data\\Insta360\\{}\\pano.jpg".format(self.ticks)
        
        if not os.path.exists("D:\\FTPServer\\Data\\Insta360"):
            os.mkdir("D:\\FTPServer\\Data\\Insta360")
        
        if not os.path.exists("D:\\FTPServer\\Data\\Insta360\\{}".format(self.ticks)):
            os.mkdir("D:\\FTPServer\\Data\\Insta360\\{}".format(self.ticks))


def run_ricoh():
    ricoh = Ricoh()
    ricoh.get_options()
    ricoh.set_options()
    ricoh.take_photo()
    time.sleep(10)
    latestFileUrl = ricoh.get_state()
    print(latestFileUrl)
    ricoh.download_file(latestFileUrl, "pano")
    latestFileUrl = str(latestFileUrl).replace("JPG", "DNG")
    print(latestFileUrl)
    ricoh.download_file(latestFileUrl, "pano", "DNG")
    ricoh.delete_all()


def run_ricoh_hdr():
    options = [
        
        {
            "exposureProgram": 1,
            "iso": 80,
            "shutterSpeed": 0.25,  # 快门速度 1/5
            "sleepDelay": 1800,
            "aperture": 5.6,
            "fileFormat": {"height": 3360, "type": "raw+", "width": 6720}
        },
        {
            "exposureProgram": 1,
            "iso": 80,
            "shutterSpeed": 0.05,  # 快门速度 1/25
            "sleepDelay": 1800,
            "aperture": 5.6,
            "fileFormat": {"height": 3360, "type": "raw+", "width": 6720}
        },
        {
            "exposureProgram": 1,
            "iso": 80,
            "shutterSpeed": 0.01666666,  # 快门速度 1/40
            "sleepDelay": 1800,
            "aperture": 5.6,
            "fileFormat": {"height": 3360, "type": "raw+", "width": 6720}
        },
    ]
    
    ricoh = Ricoh()
    for option in options:
        ricoh.get_options()
        ricoh.set_options(option)
        time.sleep(1)
        ricoh.take_photo()
        time.sleep(5)
        latestFileUrl = ricoh.get_state()
        print(latestFileUrl)
        ricoh.download_file(latestFileUrl)
        latestFileUrl = str(latestFileUrl).replace("JPG", "DNG")
        print(latestFileUrl)
        ricoh.download_file(url=latestFileUrl, suffix="DNG", post_handler=True)
    
    ricoh.delete_all()
    ricoh.compose_images()


_default_create_socket = socket.create_connection
_urllib3_create_socket = urllib3.connection.connection.create_connection

SOURCE_ADDRESS = ("192.168.1.30", 0)


# SOURCE_ADDRESS = ("192.168.10.2", 0)


def default_create_connection(*args, **kwargs):
    try:
        del kwargs["socket_options"]
    except:
        pass
    in_args = False
    if len(args) >= 3:
        args = list(args)
        args[2] = SOURCE_ADDRESS
        args = tuple(args)
        in_args = True
    if not in_args:
        kwargs["source_address"] = SOURCE_ADDRESS
    # print("args", args)
    # print("kwargs", str(kwargs))
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

if __name__ == '__main__':
    if not os.path.exists(config_file_path):
        text = json.dumps({})
        with open(config_file_path) as f:
            json.dump(obj=default_config, fp=f)
    
    try:
        with open(config_file_path) as f:
            config = json.load(f)
        os.popen("netsh wlan connect name={}".format(config.get("ssid")))
    except Exception as e:
        logging.error(e)
        raise Exception("Error loading config")
    
    need_compose = config.get("needCompose", True)
    bind_network = config.get("bindNetwork", True)
    use_raw = config.get("useRaw")
    
    if bind_network:
        time.sleep(3)
        try:
            socket.create_connection = default_create_connection
            urllib3.connection.connection.create_connection = default_create_connection
        except Exception as e:
            logging.error(e)
            raise Exception("Error bind network")
        time.sleep(3)
    
    value = sys.argv[1]
    if len(sys.argv) > 2:
        order_code = sys.argv[2]
    
    try:
        if value == "insta360":
            run_insta360()
        if value == "ricoh":
            if need_compose:
                run_ricoh_hdr()
            else:
                run_ricoh_hdr()
        if value == "ricoh-hdr":
            run_ricoh_hdr()
    except Exception as e:
        logging.error(e)
        raise e
    finally:
        pass
        # socket.create_connection = _default_create_socket
        # urllib3.connection.connection.create_connection = _urllib3_create_socket
