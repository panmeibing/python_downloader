import logging
import os.path
import sys
import time
from datetime import datetime
from threading import Thread, BoundedSemaphore

import requests
from Crypto.Cipher import AES
from fake_useragent import UserAgent

import m3u8
from tqdm import tqdm


# pip install requests
# pip install fake-useragent==0.1.11
# pip install m3u8
# pip install pycryptodome
# pip install tqdm


def decode_video(video_stream, key, iv):
    if iv and iv and str(iv).startswith("0x") and int(iv, 16):
        aes = AES.new(bytes(key, encoding='utf8'), AES.MODE_CBC, bytes(iv, encoding='utf8'))
    else:
        aes = AES.new(bytes(key, encoding='utf8'), AES.MODE_CBC, bytes(key, encoding='utf8'))
    return aes.decrypt(video_stream)


def get_datetime_num():
    return datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")


def get_user_agent():
    return UserAgent(path="./utils/fake_useragent_0.1.11.json").random


class M3U8Downloader:
    def __init__(self, m3u8_url, save_dir, video_folder, headers, if_random_ug, merge_name, ffmpeg_path, sp_count):
        self.tqdm = None
        self.m3u8_url = m3u8_url
        self.base_url = str(m3u8_url).rsplit("/", maxsplit=1)[0]
        self.to_download_url = list()
        self.download_failed_dict = dict()
        self.key_method = None
        self.key_iv = None
        self.key_str = None
        self.current_file_path = os.path.dirname(os.path.abspath(__file__))
        self.save_dir = save_dir if save_dir else os.path.join(self.current_file_path, "m3u8_download")
        self.video_folder = video_folder if video_folder else get_datetime_num()
        if not os.path.isabs(ffmpeg_path):
            ffmpeg_path = os.path.join(self.current_file_path, ffmpeg_path)
        self.headers = headers if isinstance(headers, dict) else dict()
        self.if_random_ug = if_random_ug if isinstance(if_random_ug, bool) else True
        self.ffmpeg_path = ffmpeg_path
        self.merge_name = merge_name if merge_name else "merge.ts"
        self.file_type = ".ts"
        self.semaphore = BoundedSemaphore(sp_count) if sp_count else None
        self.logger = self.get_logger()
        self.logger.info(f"init info url: {self.m3u8_url}")
        self.logger.info(f"init info if_random_ug: {self.if_random_ug}")
        self.logger.info(f"init info headers: {self.headers}")
        self.logger.info(f"init info save_dir: {self.save_dir}")
        self.logger.info(f"init info video_folder: {self.video_folder}")
        self.logger.info(f"init info current_file_path: {self.current_file_path}")
        self.logger.info(f"init info ffmpeg_path: {self.ffmpeg_path}")
        self.logger.info(f"init info merge_name: {self.merge_name}")

    def get_headers(self):
        headers = self.headers
        if self.if_random_ug:
            headers.update({"User-Agent": get_user_agent()})
        return headers

    def get_logger(self):
        logger = logging.getLogger("M3U8Downloader")
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s-%(filename)s-line:%(lineno)d-%(levelname)s-%(process)s: %(message)s")
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        if not os.path.exists(self.save_dir):
            os.mkdir(self.save_dir)
        file_handler = logging.FileHandler(os.path.join(self.save_dir, "m3u8_download.log"), encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        return logger

    def get_m3u8_info(self):
        m3u8_obj = m3u8.load(self.m3u8_url, timeout=10, headers=self.get_headers())
        keys = m3u8_obj.keys
        if keys and keys[-1]:
            key_alg = keys[-1].method
            if key_alg != "AES-128":
                raise Exception(f"matched key but algorithm ({key_alg}) is not AES-128")
            self.key_method = key_alg
            self.key_iv = keys[-1].iv
            self.get_key(self.normalize_url(keys[-1].absolute_uri))
        self.to_download_url = [self.normalize_url(segment.uri) for segment in m3u8_obj.segments]
        self.logger.info(f"to_download_url: {len(self.to_download_url)} {self.to_download_url[:5]}, ...")
        self.tqdm = tqdm(total=len(self.to_download_url), desc="download progress")
        if self.to_download_url:
            self.file_type = os.path.splitext(self.to_download_url[0])[1]

    def get_key(self, key_url):
        self.logger.info(f"key_url: {key_url}")
        res = requests.get(key_url, headers=self.get_headers(), timeout=10)
        self.key_str = res.text
        if not self.key_str:
            raise Exception("get key error, key: {}".format(self.key_str))
        self.logger.info(f"get_key key_str: {self.key_str}")

    def download_video(self, number, url):
        if self.semaphore:
            self.semaphore.acquire()
        trt_times = 10
        res_content = None
        while trt_times > 0:
            try:
                res = requests.get(url, timeout=10, stream=True)
                if res.status_code == 200:
                    res_content = res.content
                    break
            except Exception as e:
                self.logger.error(f"download failed, will try again: url:{url} ,error:{e}")
                res_content = None
            trt_times -= 1
            time.sleep(1)
        if res_content:
            if self.key_str:
                res_content = decode_video(res_content, self.key_str, self.key_iv)
            path = os.path.join(self.save_dir, self.video_folder, "{0:0>8}".format(number) + str(self.file_type))
            with open(path, "wb+") as f:
                f.write(res_content)
                # self.logger.info(f"download video {path} (total: {len(self.to_download_url)}) success, url: {url}")
            if self.tqdm:
                self.tqdm.update(1)
        else:
            self.logger.warning(f"download video failed, number:{number},url:{url}")
            self.download_failed_dict.update({number: url})
        if self.semaphore:
            self.semaphore.release()

    def merge_videos(self):
        if os.name != "nt":
            self.logger.warning(f"current system {os.name} is not Windows, can't merge.")
            return
        self.logger.info("start merge")
        path = self.save_dir
        if os.path.isabs(path):
            path = self.save_dir + os.sep + self.video_folder
        else:
            path = self.current_file_path + os.sep + os.path.basename(self.save_dir) + os.sep + self.video_folder
        if not os.path.exists(path):
            self.logger.warning(f"merge_videos canceled, the path({path}) is not exist")
            return
        if not os.path.exists(self.ffmpeg_path):
            self.logger.warning("ffmpeg program file is not exist.please fix it")
            return
        with open(path + os.sep + "merge_file_list.txt", "w") as f:
            for file in os.listdir(path):
                if not file.endswith(self.file_type):
                    continue
                f.write("file " + "'" + path + os.sep + file + "'" + "\n")
        cmd = "{} -f concat -safe 0 -i {} -c copy {}".format(
            self.ffmpeg_path, path + os.sep + 'merge_file_list.txt', path + os.sep + self.merge_name)
        self.logger.info(f"merge cmd: {cmd}")
        res = os.system(cmd)
        if res:
            self.logger.error("merge failed")
        else:
            self.logger.info("merge success")

    def mkdir(self):
        if not os.path.exists(self.save_dir):
            os.mkdir(self.save_dir)
        self.logger.info(f"make save_dir({self.save_dir}) success.")
        video_folder = os.path.join(self.save_dir, self.video_folder)
        if not os.path.exists(video_folder):
            os.mkdir(video_folder)
        self.logger.info(f"make video_folder({video_folder}) success.")

    def normalize_url(self, raw_url):
        if raw_url and raw_url.startswith("http") and any([raw_url.endswith(".ts"), raw_url.endswith(".key")]):
            return raw_url
        if raw_url and not str(raw_url).startswith("http"):
            last_find_str = ""
            for i in range(1, len(raw_url) + 1):
                start_str = raw_url[:i]
                if self.base_url.rfind(start_str) == -1:
                    break
                else:
                    last_find_str = start_str
            sep = "" if self.base_url.endswith("/") or raw_url.startswith("/") else "/"
            if self.base_url.endswith(last_find_str):
                raw_url = f"{self.base_url}{sep}{raw_url.replace(last_find_str, '')}"
            else:
                raw_url = f"{self.base_url}{sep}{raw_url}"
        return raw_url

    def run(self):
        start_time = time.time()
        self.get_m3u8_info()
        print(self.key_str)
        print(self.key_method)
        self.mkdir()
        threads = [Thread(target=self.download_video, args=(idx, url)) for idx, url in enumerate(self.to_download_url)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.logger.info(f"all download finish, spent time: {time.time() - start_time:.2f} second")
        self.logger.info(f"total video count: {len(self.to_download_url)}")
        self.logger.info(f"download_failed_dict: {self.download_failed_dict}")
        if self.download_failed_dict:
            self.logger.warning(f"{len(self.download_failed_dict)} video file download failed.")
            raise Exception(f"{len(self.download_failed_dict)} video file download failed.")
        if self.ffmpeg_path:
            self.merge_videos()
        if self.tqdm:
            self.tqdm.close()


if __name__ == '__main__':
    url = "https://xxx/index.m3u8"
    if len(sys.argv) > 1 and str(sys.argv[1]).startswith("http"):
        url = sys.argv[1]
    if not url:
        raise Exception("missing download url")
    params_dict = {
        "m3u8_url": url,
        "save_dir": "",
        "video_folder": "",
        "headers": {
            # "Host": "",
            # "Cookie": "",
            # "Referer": "",
            # "User-Agent": "",
        },
        "if_random_ug": True,
        "ffmpeg_path": "./utils/ffmpeg.exe",
        "merge_name": "",
        "sp_count": 2,
    }
    downloader = M3U8Downloader(**params_dict)
    downloader.run()
