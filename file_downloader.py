import logging
import os.path
import sys
import threading
import time
from contextlib import closing

import requests

from utils.singleton_utils import singleton


class MultiDownloader:

    def __init__(self, url, save_path=None, file_name=None, thread_count=10, headers=None, retry_times=5,
                 log_sys_out=None):
        self.url = url
        self.headers = headers if isinstance(headers, dict) else dict()
        current_file_path = os.path.dirname(os.path.abspath(__file__))
        self.save_path = save_path if save_path else os.path.join(current_file_path, "multi_download")
        self.total_range = None
        log_sys_out = sys.stdout if log_sys_out == "sys.stdout" else None
        self.logger = self.get_logger(log_sys_out)
        self.get_resp_header_info()
        if file_name:
            self.file_name = file_name
        if not self.file_name:
            self.file_name = os.path.split(url)[1]
        self.retry_times = retry_times
        self.file_lock = threading.Lock()
        self.thread_count = thread_count
        self.failed_thread_list = list()
        self.finished_thread_count = 0
        self.chunk_size = 1024 * 100
        self.logger.info(f"init multi task, url:{self.url}")
        self.logger.info(f"init multi task, sava_path:{self.save_path}")
        self.logger.info(f"init multi task, file_name:{self.file_name}")
        self.logger.info(f"init multi task, thread_count:{self.thread_count}")
        self.logger.info(f"init multi task, headers:{self.headers}")

    @singleton
    def get_logger(self, stream=None):
        logger = logging.getLogger("MultiDownloader")
        logger.setLevel(logging.INFO)
        print_fmt = logging.Formatter("%(asctime)s-%(levelname)s-%(process)s: %(message)s")
        console_handler = logging.StreamHandler(stream)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(print_fmt)
        if not os.path.exists(self.save_path):
            os.mkdir(self.save_path)
        file_handler = logging.FileHandler(os.path.join(self.save_path, "download.log"), encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_fmt = logging.Formatter("%(asctime)s-%(filename)s-line:%(lineno)d-%(levelname)s-%(process)s: %(message)s")
        file_handler.setFormatter(file_fmt)
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        return logger

    def get_resp_header_info(self):
        res = requests.head(self.url, headers=self.headers, allow_redirects=True)
        res_header = res.headers
        self.logger.info(f"get_resp_header_info() res_header: {res_header}")
        content_range = res_header.get("Content-Length", "0")
        self.total_range = int(content_range)
        self.file_name = res_header.get("Content-Disposition", "").replace("attachment;filename=", "").replace('"', '')
        self.url = res.url

    def page_dispatcher(self, content_size):
        page_size = content_size // self.thread_count
        start_pos = 0
        while start_pos + page_size < content_size:
            yield {
                'start_pos': start_pos,
                'end_pos': start_pos + page_size
            }
            start_pos += page_size + 1
        yield {
            'start_pos': start_pos,
            'end_pos': content_size - 1
        }

    def download_range(self, thread_name, page, file_handler):
        self.logger.info(f"thread {thread_name} start to download")
        range_headers = {"Range": f'bytes={page["start_pos"]}-{page["end_pos"]}'}
        range_headers.update(self.headers)
        try:
            start_time = time.time()
            is_success = False
            for i in range(self.retry_times):
                try:
                    with closing(requests.get(url=self.url, headers=range_headers, stream=True, timeout=30)) as res:
                        self.logger.info(f"thread {thread_name} download length: {len(res.content)}")
                        if res.status_code == 206:
                            for data in res.iter_content(chunk_size=self.chunk_size):
                                with self.file_lock:
                                    file_handler.seek(page["start_pos"])
                                    file_handler.write(data)
                                page["start_pos"] += len(data)
                            is_success = True
                            break
                except Exception as e:
                    self.logger.error(f"download_range() request error: {e}")
            self.finished_thread_count += 1
            spent_time = time.time() - start_time
            if is_success:
                self.logger.info("thread {} download success, spent_time: {}, progress: {}/{}".format(
                    thread_name, spent_time, self.finished_thread_count, self.thread_count
                ))
            else:
                self.logger.error(f"thread {thread_name} download {self.retry_times} times but failed")
                self.failed_thread_list.append(thread_name)
        except Exception as e:
            self.logger.error(f"thread {thread_name} download failed: {e}")
            self.failed_thread_list.append(thread_name)

    def run(self, ):
        self.logger.info(f"run() get file total range: {self.total_range}")
        if not self.total_range or self.total_range < 1024:
            raise Exception("get file total size failed")
        thread_list = list()
        full_path = os.path.join(self.save_path, self.file_name)
        self.logger.info(f"ready to download, full_path: {full_path}")
        if os.path.exists(full_path):
            self.logger.warning(f"file already exists, remove, full_path:{full_path}")
            os.remove(full_path)
        start_time = time.time()
        with open(full_path, "wb+") as f:
            for i, page in enumerate(self.page_dispatcher(self.total_range)):
                self.logger.info("page: {}, page difference: {}".format(page, page["end_pos"] - page["start_pos"]))
                thread_list.append(threading.Thread(target=self.download_range, args=(i, page, f)))
            for thread in thread_list:
                thread.start()
            for thread in thread_list:
                thread.join()
        try:
            actual_size = os.path.getsize(full_path)
        except Exception as e:
            actual_size = 0
            self.logger.warning(f"get actual file size failed:, full_path: {full_path}, error: {e}")
        if os.path.exists(full_path) and os.path.getsize(full_path) == 0:
            self.logger.warning(f"file size is 0, remove, full_path:{full_path}")
            os.remove(full_path)
        total_time = time.time() - start_time
        self.logger.info("download finishing..........")
        self.logger.info("total size %d Bytes (%.2f MB), actual file size %d Bytes, are they equal? %s" % (
            self.total_range, self.total_range / (1024 * 1024), actual_size, self.total_range == actual_size,
        ))
        self.logger.info("total spent time: %.2f second, average download speed: %.2f MB/s" % (
            total_time, actual_size / (1024 * 1024) / total_time
        ))
        if self.failed_thread_list:
            self.logger.info(f"failed_thread_list: {self.failed_thread_list}")
        final_result = "download success!" if self.total_range == actual_size else "download failed"
        self.logger.info(final_result)


if __name__ == '__main__':
    params = {
        "url": "https://dldir1.qq.com/qqfile/qq/PCQQ9.6.9/QQ9.6.9.28878.exe",
        "save_path": "",
        # "file_name": "QQ9.6.9.28878.exe",
        "headers": {
            # "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36",
        },
        "thread_count": 10,
        "retry_times": 10,
    }

    downloader = MultiDownloader(**params)
    downloader.run()
