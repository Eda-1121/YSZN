import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser
from urllib.parse import quote, unquote
import re

import requests

# ========= 按你的环境改这里 =========

BASE_URL = "http://138.64.68.102:8898"
BASIC_AUTH_B64 = "RWRhMTEyMTowOTE2"
PHPSESSID = "2c94f845086e4316dc256e17697a4695"
DOWNLOAD_DIR = r"C:\Users\rikik\Downloads"

COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MSIE 11.0; Windows NT 6.1)",
    "Accept": "text/html, application/xhtml+xml",
    "Accept-Language": "zh-cn",
    "Cache-Control": "no-cache",
    "Connection": "Keep-Alive",
    "Content-Type": "application/x-www-form-urlencoded",
    "Authorization": f"Basic {BASIC_AUTH_B64}",
    "Cookie": f"PHPSESSID={PHPSESSID}",
}

# ========= HTTP 封装 =========

def list_public_files():
    """
    访问 /public_dir 页，解析出文件名列表。
    HTML 目录页中有 href="/public_dir/xxx" 的链接。
    """
    url = f"{BASE_URL}/public_dir"
    resp = requests.get(url, headers=COMMON_HEADERS, timeout=10)
    resp.raise_for_status()
    html = resp.text

    # 调试：保存 HTML（需要时可查看）
    with open("public_dir_debug.html", "w", encoding="utf-8", errors="ignore") as f:
        f.write(html)

    files = []

    # 匹配 href="/public_dir/xxxx"
    pattern = re.compile(r'href="/public_dir/([^"]+)"', re.IGNORECASE)

    for m in pattern.finditer(html):
        encoded = m.group(1)
        if encoded.startswith(".thumb"):
            continue
        name = unquote(encoded).strip()
        if not name:
            continue
        files.append(name)

    print("DEBUG files:", files)
    return files


def download_public_file_stream(name, dst_path, status_cb=None):
    """
    边下载边写入 dst_path。
    status_cb(文本) 用来更新状态栏，可以为 None。
    """
    encoded_name = quote(name.encode("utf-8"))
    # 和目录页一致，从 /public_dir 取文件
    url = f"{BASE_URL}/public_dir/{encoded_name}"

    headers = dict(COMMON_HEADERS)

    with requests.get(url, headers=headers, stream=True, timeout=30) as r:
        r.raise_for_status()
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        total = int(r.headers.get("Content-Length", "0") or "0")
        downloaded = 0

        with open(dst_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 64):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if status_cb and total > 0:
                    percent = downloaded / total * 100
                    status_cb(f"正在下载：{name}  {percent:.1f}%")


# ========= GUI =========

class YSZNViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YSZN Public Viewer")
        self.geometry("600x400")
        self.create_widgets()
        self.refresh_file_list_async()

    def create_widgets(self):
        toolbar = tk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        self.refresh_btn = tk.Button(
            toolbar, text="刷新 /public_dir", command=self.refresh_file_list_async
        )
        self.refresh_btn.pack(side=tk.LEFT, padx=5, pady=5)

        columns = ("name",)
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        self.tree.heading("name", text="/public_dir 文件")
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.tree.bind("<Double-1>", self.on_double_click)

        self.status_var = tk.StringVar(value="准备就绪")
        status_bar = tk.Label(self, textvariable=self.status_var, anchor="w")
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def set_status(self, text):
        self.status_var.set(text)
        self.update_idletasks()

    def refresh_file_list_async(self):
        t = threading.Thread(target=self.refresh_file_list, daemon=True)
        t.start()

    def refresh_file_list(self):
        self.set_status("正在获取 /public_dir 列表...")
        self.refresh_btn.config(state=tk.DISABLED)
        try:
            files = list_public_files()
        except Exception as e:
            self.set_status("获取失败")
            messagebox.showerror("错误", f"获取列表失败：{e}")
            self.refresh_btn.config(state=tk.NORMAL)
            return

        def update_ui():
            self.tree.delete(*self.tree.get_children())
            for name in files:
                self.tree.insert("", tk.END, values=(name,))
            self.set_status(f"共 {len(files)} 个文件")
            self.refresh_btn.config(state=tk.NORMAL)

        self.after(0, update_ui)

    def on_double_click(self, event):
        item = self.tree.selection()
        if not item:
            return
        name = self.tree.item(item[0], "values")[0]
        t = threading.Thread(target=self.download_and_open, args=(name,), daemon=True)
        t.start()

    def download_and_open(self, name):
        dst_path = os.path.join(DOWNLOAD_DIR, name)

        def status_cb(text):
            self.after(0, lambda: self.set_status(text))

        def worker():
            try:
                self.set_status(f"正在开始下载：{name}")
                download_public_file_stream(name, dst_path, status_cb=status_cb)
                self.set_status(f"下载完成：{dst_path}")
            except Exception as e:
                self.set_status("下载失败")
                messagebox.showerror("错误", f"下载失败：{e}")
                return

        # 开始后台下载
        t = threading.Thread(target=worker, daemon=True)
        t.start()

        # 等文件大到可以播放时再自动打开
        def wait_and_open():
            threshold = 1 * 1024 * 1024  # 1MB，可根据网速调整
            tries = 0
            while tries < 40:  # 最长大约 20 秒
                if os.path.exists(dst_path) and os.path.getsize(dst_path) >= threshold:
                    break
                tries += 1
                self.after(500, lambda: None)  # 只是让事件循环跑一下
                # 用睡眠会阻塞主线程，所以这里不用 time.sleep

            try:
                if os.path.exists(dst_path):
                    os.startfile(dst_path)
            except Exception:
                webbrowser.open(dst_path)

        # 用一个线程做等待和打开，避免卡 UI
        open_thread = threading.Thread(target=wait_and_open, daemon=True)
        open_thread.start()

if __name__ == "__main__":
    app = YSZNViewer()
    app.mainloop()
