import os.path

import PySimpleGUI as sg

import time
import threading

from m3u8_downloader import M3U8Downloader


def task_decorator(fn):
    def inner(*args, **kwargs):
        print("任务准备开始...")
        start_time = time.time()
        window = kwargs.get("window")
        window["key_start"].update(disabled=True)
        window["key_quit"].update(disabled=True)
        try:
            fn(*args, **kwargs)
        except Exception as e:
            print(f"任务执行出错：{e}")
        finally:
            window["key_start"].update(disabled=False)
            window["key_quit"].update(disabled=False)
        print(f"任务结束,总耗时{int(time.time() - start_time)}秒")

    return inner


@task_decorator
def long_time_work(window):
    for i in range(10):
        time.sleep(1)
        if i == 3:
            raise Exception("故意报错")
        window.write_event_value('任务进度', i)
    window.write_event_value('任务结束', '')


@task_decorator
def start_download_task(params_dict, *args, **kwargs):
    downloader = M3U8Downloader(**params_dict)
    downloader.run()


def get_layout():
    text_and_button_size = (20, 1)
    input_text_size = (50, 1)
    multiline_size = (50, 10)
    log_output_size = (80, 25)
    pad_size = (20, 20)
    inner_pad_size = (10, 10)
    left_layout = [
        [
            sg.Text("请选择M3U8类型", size=text_and_button_size, justification="center", border_width=3),
            sg.Radio(text="URL链接", group_id="radio_m3u8_type", size=(10, 1), enable_events=True, default=True,
                     key="key_m3u8_type_radio1"),
            sg.Radio(text="本地文件", group_id="radio_m3u8_type", size=(10, 1), enable_events=True, default=False,
                     key="key_m3u8_type_radio2"),
        ],
        [
            sg.Text("请输入URL", size=text_and_button_size, justification="center", border_width=3),
            sg.InputText(key="key_m3u8_url", size=input_text_size)
        ],
        [
            sg.Text("请输入BASE_URL", size=text_and_button_size, justification="center", border_width=3),
            sg.InputText(key="key_base_url", size=input_text_size, disabled=True)
        ],
        [
            sg.FileBrowse(
                button_text="请选择m3u8文件",
                target="key_m3u8_file_path",
                file_types=(("All Files", "*.m3u8"),),
                size=text_and_button_size,
                disabled=True,
                key="key_file_browse_m3u8_file_path",
            ),
            sg.InputText(key="key_m3u8_file_path", size=input_text_size, disabled=True),
        ],
        [
            sg.FolderBrowse(
                button_text="请选择文件保存路径",
                target="key_save_dir",
                size=text_and_button_size
            ),
            sg.InputText(key="key_save_dir", size=input_text_size)
        ],
        [
            sg.FileBrowse(
                button_text="请选择FFmpeg程序",
                target="key_ffmpeg_path",
                file_types=(("All Files", "*.exe"),),
                size=text_and_button_size
            ),
            sg.InputText(key="key_ffmpeg_path", size=input_text_size),
        ],
        [
            sg.Text("自定义请求头", size=text_and_button_size, justification="center", border_width=3),
            sg.Multiline(size=multiline_size, key="key_headers")
        ],
        [
            sg.Text("是否随机用户代理", size=text_and_button_size, justification="center", border_width=3, ),
            sg.Radio(text="是", group_id="if_random_ug", size=(5, 1), default=True, key="key_if_random_ug_radio1"),
            sg.Radio(text="否", group_id="if_random_ug", size=(5, 1), default=False, key="key_if_random_ug_radio2"),
        ],
        [
            sg.Text("同时下载线程数", size=text_and_button_size, justification="center", border_width=3, ),
            sg.Combo(values=[0, 1, 2, 5, 10, 100, 1000], default_value=2, size=text_and_button_size, key="key_sp_count")
        ],
    ]

    return [
        [
            sg.Frame(
                title="参数",
                pad=pad_size,
                layout=left_layout,
            ),
            sg.Frame(
                title="日志",
                pad=(50, 10),
                layout=[
                    [sg.Output(size=log_output_size, key="_output_", pad=inner_pad_size, echo_stdout_stderr=True)], ],
            ),
        ],
        [sg.Frame(
            title="操作",
            relief=sg.RELIEF_GROOVE,
            size=(1110, 60),
            pad=pad_size,
            element_justification="center",
            layout=[
                [
                    sg.Button('开始', size=text_and_button_size, key="key_start"),
                    sg.Button('说明', size=text_and_button_size, key="key_instruction"),
                    sg.Button('清屏', size=text_and_button_size, key="key_clear"),
                    sg.Button('退出', size=text_and_button_size, key="key_quit"),
                ]
            ]
        )],
        [
            sg.Text("made by 冰冷的希望", size=(1110, 20), justification="center", font=(None, 10))
        ]
    ]


def check_params(values: dict):
    # print("check_params:", values)
    m3u8_url = values.get("key_m3u8_url")  # type: str
    base_url = values.get("key_base_url")  # type: str
    m3u8_file_path = values.get("key_m3u8_file_path")
    save_dir = values.get("key_save_dir")
    ffmpeg_path = values.get("key_ffmpeg_path")
    headers = values.get("key_headers")
    if_random_ug = values.get("key_if_random_ug_radio1")
    sp_count = values.get("key_sp_count")
    if not m3u8_url and not m3u8_file_path:
        sg.popup("请输入m3u8链接或者选m3u8文件", title="警告")
        return False
    if m3u8_url:
        if not m3u8_url.startswith("http") or not m3u8_url.split("?")[0].endswith("m3u8"):
            sg.popup("请确认m3u8_url链接是否正确", title="警告")
            return False
    if m3u8_file_path:
        if not os.path.exists(m3u8_file_path):
            sg.popup("请确认m3u8文件路径是否存在", title="警告")
            return False
        if not base_url:
            sg.popup("请输入base_url", title="警告")
            return False
        if not base_url.startswith("http"):
            sg.popup("请确认base_url链接是否正确", title="警告")
            return False
    if save_dir and not os.path.exists(save_dir):
        sg.popup("请确认文件保存路径是否存在", title="警告")
        return False
    if ffmpeg_path and not os.path.exists(ffmpeg_path):
        sg.popup("请确认ffmpeg程序路径是否正确", title="警告")
        return False
    if headers:
        try:
            if not isinstance(eval(headers), dict):
                sg.popup("请确认请求头是否正确", title="警告")
                return False
        except Exception as _:
            sg.popup("请确认请求头是否正确", title="警告")
            return False

    if not sp_count or not str(sp_count).isdigit():
        sg.popup("请确认线程数是整数类型", title="警告")
        return False
    return {
        "m3u8_url": m3u8_url if m3u8_url else m3u8_file_path,
        "base_url": base_url,
        "save_dir": save_dir,
        "video_folder": "",
        "headers": eval(headers) if headers else {},
        "if_random_ug": if_random_ug,
        "ffmpeg_path": ffmpeg_path if ffmpeg_path else "./utils/ffmpeg.exe",
        "merge_name": "",
        "sp_count": int(sp_count),
        "if_tqdm": False,
    }


def run():
    window = sg.Window('M3U8下载器', get_layout(), size=(1200, 620), )

    instructions = """1.若使用M3U8链接，确保url有效；
2.若使用本地M3U8文档，需要填写正确的base_url；
3.若不指定文档保存路径，默认保存在程序所以文件夹；
4.本程序自带FFmpeg程序，一般无需指定路径；
5.若要自定义请求头需要填写一个JSON；
6.建议设置随机代理减少触发反爬机制的概率；
7.若遇到不能同时下载多个文件可以适当调小线程数（0是不限制）；
该程序完全免费且开源，请勿用于商业用途
GitHub：https://github.com/panmeibing/python_downloader
"""

    while True:
        event, values = window.read()

        if event == sg.WIN_CLOSED:
            break
        if event == 'key_quit':
            res = sg.popup_yes_no("确定要退出吗？", title="警告")
            if res == "Yes":
                break
        if event == 'key_start':
            params_dict = check_params(values)
            if params_dict:
                print(params_dict)
                # threading.Thread(target=long_time_work, kwargs={"window": window}, daemon=True).start()
                threading.Thread(target=start_download_task, args=(params_dict,), kwargs={"window": window},
                                 daemon=True).start()
        elif event == "key_instruction":
            sg.popup_ok(instructions, title="使用说明")
        elif event == "key_clear":
            print(values)
            window["_output_"].update('')
        elif event == '任务结束':
            print('任务已结束')
        elif event == 'key_m3u8_type_radio1' or event == "key_m3u8_type_radio2":
            if values["key_m3u8_type_radio1"]:
                window["key_m3u8_url"].update(disabled=False, visible=True)
                window["key_base_url"].update("", disabled=True, visible=False)
                window["key_file_browse_m3u8_file_path"].update(disabled=True)
                window["key_m3u8_file_path"].update("", disabled=True, visible=False)
            else:
                window["key_m3u8_url"].update("", disabled=True, visible=False)
                window["key_base_url"].update(disabled=False, visible=True)
                window["key_file_browse_m3u8_file_path"].update(disabled=False)
                window["key_m3u8_file_path"].update(disabled=False, visible=True)
        else:
            pass
    window.close()


if __name__ == '__main__':
    run()
