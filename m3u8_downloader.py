import os.path
import sys
import time
from threading import Thread

import requests
from Crypto.Cipher import AES
from fake_useragent import UserAgent

import m3u8


# pip install requests
# pip install fake_useragent
# pip install m3u8
# pip install pycryptodome


def decode_video(video_stream, key, iv):
    if iv:
        aes = AES.new(bytes(key, encoding='utf8'), AES.MODE_CBC, bytes(iv, encoding='utf8'))
    else:
        aes = AES.new(bytes(key, encoding='utf8'), AES.MODE_CBC, bytes(key, encoding='utf8'))
    return aes.decrypt(video_stream)


class M3U8Downloader:
    def __init__(self, m3u8_url, save_dir="./save_m3u8"):
        self.m3u8_url = m3u8_url
        self.base_url = str(m3u8_url).rsplit("/", maxsplit=1)[0]
        self.to_download_url = list()
        self.download_failed_dict = dict()
        self.key_method = None
        self.key_iv = None
        self.key_str = None
        self.save_dir = save_dir
        self.merge_name = "merge.ts"
        self.file_type = ".ts"

    def get_m3u8_info(self):
        headers = {
            "User-Agent": UserAgent().random
        }
        m3u8_obj = m3u8.load(self.m3u8_url, timeout=10, headers=headers)
        keys = m3u8_obj.keys
        if keys and keys[-1]:
            key_alg = keys[-1].method
            if key_alg != "AES-128":
                raise Exception(f"matched key but algorithm ({key_alg}) is not AES-128")
            self.key_method = key_alg
            self.key_iv = keys[-1].iv
            self.get_key(self.normalize_url(keys[-1].uri))
        self.to_download_url = [self.normalize_url(segment.uri) for segment in m3u8_obj.segments]
        print("to_download_url:", self.to_download_url[:5])
        if self.to_download_url:
            self.file_type = os.path.splitext(self.to_download_url[0])[1]

    def get_key(self, key_url):
        headers = {
            "User-Agent": UserAgent().random
        }
        res = requests.get(key_url, headers=headers, timeout=10)
        self.key_str = res.text
        if not self.key_str:
            raise Exception("get key error, key: {}".format(self.key_str))
        print(f"get_key key_str: {self.key_str}")

    def download_video(self, number, url):
        headers = {
            "User-Agent": UserAgent().random
        }
        trt_times = 10
        res_content = None
        while trt_times > 0:
            try:
                res = requests.get(url, headers=headers, timeout=10, stream=True)
                if res.status_code == 200:
                    res_content = res.content
                    break
            except Exception as e:
                print(f"download failed, will try again: {e}")
                res_content = None
            trt_times -= 1
            time.sleep(1)
        if res_content:
            if self.key_str:
                res_content = decode_video(res_content, self.key_str, self.key_iv)
            path = os.path.join(self.save_dir, "{0:0>8}".format(number) + str(self.file_type))
            with open(path, "wb+") as f:
                f.write(res_content)
                print(f"download video {path} success, url: {url}")
        else:
            print("download video failed, number:{},url:{}".format(number, url))
            self.download_failed_dict.update({number: url})

    def merge_videos(self):
        print("start merge")
        path = self.save_dir
        if not os.path.isabs(path):
            path = os.getcwd() + os.sep + os.path.basename(self.save_dir)
        if not os.path.exists(path):
            print(f"merge_videos canceled, the path({path}) is not exist")
            return
        cmd = "copy /B {} {}".format(path + os.sep + "*", path + os.sep + self.merge_name)
        print("cmd:", cmd)
        res = os.system(cmd)
        if res:
            print("merge failed")
        else:
            print("merge success")

    def mkdir(self):
        if not os.path.exists(self.save_dir):
            os.mkdir(self.save_dir)
        print("make dir success.")

    def normalize_url(self, url):
        if url and not str(url).startswith("http"):
            url = self.base_url + "/" + url
        return url


def start_download(m_url):
    start_time = time.time()
    downloader = M3U8Downloader(m_url)
    downloader.get_m3u8_info()
    # print(downloader.key_str)
    # print(downloader.key_method)
    downloader.mkdir()
    to_download_url = downloader.to_download_url
    threads = [Thread(target=downloader.download_video, args=(idx, url)) for idx, url in enumerate(to_download_url)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print(f"all download finish, spent time: {time.time() - start_time}")
    print(f"total video count: {len(downloader.to_download_url)}")
    print(f"download_failed_dict: {len(downloader.download_failed_dict)}, {downloader.download_failed_dict}")
    downloader.merge_videos()


if __name__ == '__main__':
    url = "https://xxx/index.m3u8"
    if len(sys.argv) > 1 and str(sys.argv[1]).startswith("http"):
        url = sys.argv[1]
    if not url:
        raise Exception("missing download url")
    start_download(url)
