import requests
from pip._internal.utils import logging

from conf.params.ricoh_params import RicohParams


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
