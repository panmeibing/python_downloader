import os.path
import sys
import traceback
from threading import Thread
from tkinter.filedialog import askdirectory
from tkinter.messagebox import askyesno, showerror

import ttkbootstrap as ttkb
from ttkbootstrap.scrolled import ScrolledText
from ttkbootstrap.tooltip import ToolTip

from file_downloader import MultiDownloader


class RedirectStdout:
    def __init__(self, scroll_text):
        self.scroll_text = scroll_text
        self.sdt_out = sys.stdout
        sys.stdout = self

    def write(self, message):
        self.sdt_out.write(f"{message}")
        self.scroll_text.insert("end", message)
        self.scroll_text.see("end")

    def flush(self):
        self.sdt_out.flush()

    def restore(self):
        sys.stdout = self.sdt_out


class FileDownloader:
    def __init__(self, master=None):
        if not master:
            master = ttkb.Window(title="多线程文件下载器", resizable=(False, False))
        self.root = master
        self.root.iconbitmap("./images/ico/file_downloader.ico")
        self.target_url = ttkb.StringVar()
        self.target_ua = ttkb.StringVar()
        self.target_save_path = ttkb.StringVar()
        self.target_file_name = ttkb.StringVar()
        self.target_thread_count = ttkb.StringVar(value="3")
        self.target_retry_times = ttkb.StringVar(value="3")

        self.container_frame = ttkb.Frame(self.root, padding=(100, 10, 100, 30))
        self.main_frame = ttkb.Frame(self.container_frame)
        self.params_frame = ttkb.Frame(self.main_frame)
        self.logs_frame = ttkb.Frame(self.main_frame)
        self.logs_red_sdt = None
        self.download_btn = None
        self.init_params()
        self.create_view()
        self.center_window()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

    def init_params(self):
        default_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        self.target_ua.set(default_ua)
        current_dir = os.path.dirname(__file__)
        self.target_save_path.set(os.path.join(current_dir, "download"))

    def create_view(self):
        entry_width = 50
        entry_pady = (7, 18)
        ttkb.Label(self.root, text="多线程文件下载器", font=(None, 20, "bold")).pack(pady=20)
        url_lb = ttkb.Label(self.params_frame, text="下载链接 *")
        url_lb.pack(anchor="w")
        ToolTip(url_lb, text="下载链接（URL），暂时只支持http协议的链接")
        ttkb.Entry(self.params_frame, textvariable=self.target_url, width=entry_width).pack(pady=entry_pady)
        save_path_lb = ttkb.Label(self.params_frame, text="保存路径 *")
        save_path_lb.pack(anchor="w")
        ToolTip(save_path_lb, text="文件夹不存在则尝试创建，所以请确保路径是合法的")
        dir_frame = ttkb.Frame(self.params_frame)
        ttkb.Entry(dir_frame, textvariable=self.target_save_path).pack(side="left", fill="x", expand=1, pady=entry_pady)
        ttkb.Button(dir_frame, text=" 浏览 ", command=lambda: self.target_save_path.set(askdirectory())).pack(
            side="right", padx=(10, 0), fill="x", pady=entry_pady)
        dir_frame.pack(side="top", fill="x", expand=1)
        save_name_lb = ttkb.Label(self.params_frame, text="保存文件名（可选）")
        save_name_lb.pack(anchor="w")
        ToolTip(save_name_lb, text="1.若为空，先从远程获取文件名，不行再从下载链接截取\n2.若文件已存在则会删除重新下载")
        ttkb.Entry(self.params_frame, textvariable=self.target_file_name, width=entry_width).pack(pady=entry_pady)
        ua_lb = ttkb.Label(self.params_frame, text="用户代理（UA）")
        ua_lb.pack(anchor="w")
        ToolTip(ua_lb, text="默认使用Chrome浏览器的UA，如果不是有特殊要求，建议保持默认UA")
        ttkb.Entry(self.params_frame, textvariable=self.target_ua, width=entry_width).pack(pady=entry_pady)
        thread_count_lb = ttkb.Label(self.params_frame, text="线程数 *")
        thread_count_lb.pack(anchor="w")
        ToolTip(thread_count_lb, text="同时开启多个线程进行分段下载，建议不超过8个，小文件建议1个")
        ttkb.Entry(self.params_frame, textvariable=self.target_thread_count, width=entry_width).pack(pady=entry_pady)
        retry_count_lb = ttkb.Label(self.params_frame, text="重试次数")
        retry_count_lb.pack(anchor="w")
        ToolTip(retry_count_lb, text="如果服务器没有响应数据则尝试再次发起请求")
        ttkb.Entry(self.params_frame, textvariable=self.target_retry_times, width=entry_width).pack(pady=entry_pady)
        log_st = ScrolledText(self.logs_frame, width=70, autohide=True, padding=0)
        log_st.pack(expand=1, fill="y", padx=20, pady=20)
        self.logs_red_sdt = RedirectStdout(log_st)
        self.params_frame.grid(row=0, column=0, padx=20)
        self.logs_frame.grid(row=0, column=1, padx=20)
        self.main_frame.pack(pady=10)
        self.download_btn = ttkb.Button(self.container_frame, text="下载", width=30, command=self.on_lick_start)
        self.download_btn.pack(pady=30)
        self.container_frame.pack()
        ttkb.Label(self.root, text="made by 冰冷的希望", font=(None, 10), bootstyle="secondary").pack(pady=10)

    def on_lick_start(self):
        is_ok, data = self.check_params()
        if not is_ok:
            showerror("提示", data)
            return
        thread = Thread(target=self.download_task, args=(data,))
        thread.start()

    def check_params(self):
        target_url = self.target_url.get()
        if not target_url:
            return False, "请输入下载链接"
        if not target_url.startswith("http"):
            return False, "请检查下载链接格式是否正确"
        target_save_path = self.target_save_path.get()
        if not target_save_path:
            return False, "请设置保存路径"
        target_file_name = self.target_file_name.get()
        target_ua = self.target_ua.get()
        target_thread_count = self.target_thread_count.get()
        if not target_thread_count.isdigit():
            return False, "线程数应为整数"
        target_retry_times = self.target_retry_times.get()
        target_retry_times = target_retry_times if target_retry_times else "1"
        if not target_retry_times.isdigit():
            return False, "重试次数应为整数"
        param_dict = {
            "url": target_url, "save_path": target_save_path,
            "thread_count": int(target_thread_count), "retry_times": int(target_retry_times),
            "log_sys_out": "sys.stdout",
        }
        if target_file_name:
            param_dict.update({"file_name": target_file_name})
        if target_ua:
            param_dict.update({"headers": {"user-agent": target_ua}})
        return True, param_dict

    def download_task(self, params: dict):
        self.download_btn["state"] = "disable"
        try:
            downloader = MultiDownloader(**params)
            self.target_file_name.set(downloader.file_name)
            if os.path.exists(os.path.join(self.target_save_path.get(), self.target_file_name.get())):
                result = askyesno("提示", "同名文件已存在，是否重新下载？")
                if not result:
                    print("task canceled")
                    del downloader
                    return
            downloader.run()
        except Exception as e:
            print(f"start_task() meets error: {e}, detail: \n{traceback.format_exc()}")
        finally:
            self.download_btn["state"] = "normal"

    def on_closing(self):
        result = askyesno("提示", "确定要退出吗？")
        if result:
            if self.logs_red_sdt:
                self.logs_red_sdt.restore()
            self.root.destroy()

    def center_window(self):
        try:
            self.root.update()
            width, height = self.root.winfo_width(), self.root.winfo_height()
            geometry_str = "+{}+{}".format(
                (self.root.winfo_screenwidth() - width) // 2,
                (self.root.winfo_screenheight() - height) // 2
            )
            self.root.geometry(geometry_str)
        except Exception as e:
            print(f"center_window() error: {e}")


def run_gui():
    FileDownloader()


if __name__ == '__main__':
    run_gui()
