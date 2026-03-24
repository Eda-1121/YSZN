import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
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
    "Authorization": f"Basic {BASIC_AUTH_B64}",
    "Cookie": f"PHPSESSID={PHPSESSID}",
}

session = requests.Session()
session.headers.update(COMMON_HEADERS)

_created_dirs = set()
_created_dirs_lock = threading.Lock()

# ========= HTTP =========

def list_public_entries(cur_dir: str):
    """
    列出当前目录下的条目（文件 + 子目录）。
    size==4096 视为目录。
    href 可能是相对路径 "qqqqq" 或绝对路径 "/public_dir/qqqqq"，统一取最后一段。
    """
    if cur_dir:
        url = f"{BASE_URL}/public_dir/{quote(cur_dir)}"
    else:
        url = f"{BASE_URL}/public_dir"
    resp = session.get(url, timeout=10)
    resp.raise_for_status()
    html = resp.text

    with open("public_dir_debug.html", "w", encoding="utf-8", errors="ignore") as f:
        f.write(html)

    entries = []

    row_pattern = re.compile(
        r'<tr>\s*<td>\s*<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>\s*</td>\s*'
        r'<td>\s*(\d+)\s*</td>',
        re.IGNORECASE,
    )

    for m in row_pattern.finditer(html):
        href = m.group(1)
        display_name = m.group(2).strip()
        size = int(m.group(3))

        # 跳过上级目录和 .thumb
        if href.startswith("..") or display_name == "..":
            continue
        if href.startswith(".thumb") or display_name.startswith(".thumb"):
            continue

        # href 可能是绝对路径（/public_dir/qqqqq）或相对路径（qqqqq）
        # 统一取 "/" 分割后最后一段作为纯文件/目录名
        decoded_href = unquote(href).strip().rstrip("/")
        name = decoded_href.rsplit("/", 1)[-1]
        if not name:
            continue

        is_dir = (size == 4096)
        entries.append({"name": name, "is_dir": is_dir})

    return entries


def download_public_file_stream(cur_dir, name, dst_path, status_cb=None):
    """
    从当前目录下载文件。
    """
    path = f"{cur_dir}/{name}" if cur_dir else name
    encoded = quote(path.encode("utf-8"))
    url = f"{BASE_URL}/public_dir/{encoded}"

    with session.get(url, stream=True, timeout=30) as r:
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
                    status_cb(f"正在下载：{name} {percent:.1f}%")


def _ensure_remote_dir(rel_dir: str):
    if not rel_dir:
        return
    parts = rel_dir.strip("/").split("/")
    cur = ""
    for p in parts:
        cur = f"{cur}/{p}" if cur else p
        with _created_dirs_lock:
            if cur in _created_dirs:
                continue
        url = f"{BASE_URL}/public_dir/{quote(cur)}"
        r = session.request("MKCOL", url, timeout=10)
        if r.status_code in (201, 405):
            with _created_dirs_lock:
                _created_dirs.add(cur)
        else:
            print("MKCOL 失败:", url, r.status_code, r.text)


def upload_single_file(local_path: str, remote_rel_path: str = None, status_cb=None):
    if remote_rel_path is None:
        remote_rel_path = os.path.basename(local_path)

    remote_rel_path = remote_rel_path.replace("\\", "/")

    if "/" in remote_rel_path:
        dir_part, file_name = remote_rel_path.rsplit("/", 1)
    else:
        dir_part, file_name = "", remote_rel_path

    _ensure_remote_dir(dir_part)

    encoded_name = quote(file_name.encode("utf-8"))
    if dir_part:
        url = f"{BASE_URL}/public_dir/{dir_part}/{encoded_name}"
        show_name = f"{dir_part}/{file_name}"
    else:
        url = f"{BASE_URL}/public_dir/{encoded_name}"
        show_name = file_name

    if status_cb:
        status_cb(f"正在上传：{show_name}")

    with open(local_path, "rb") as f:
        r = session.put(url, data=f, timeout=600)
    r.raise_for_status()


def delete_files_from_public_dir(cur_dir, names, status_cb=None):
    for name in names:
        if status_cb:
            status_cb(f"正在删除：{name}")
        path = f"{cur_dir}/{name}" if cur_dir else name
        encoded = quote(path.encode("utf-8"))
        url = f"{BASE_URL}/public_dir/{encoded}"
        r = session.delete(url, timeout=30)
        r.raise_for_status()
    if status_cb:
        status_cb("删除完成")


# ========= GUI =========

class YSZNViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YSZN Public Viewer")
        self.geometry("720x430")
        self.current_dir = ""
        self.create_widgets()
        self.refresh_file_list_async()

    def create_widgets(self):
        toolbar = tk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        self.refresh_btn = tk.Button(
            toolbar, text="刷新 /public_dir", command=self.refresh_file_list_async
        )
        self.refresh_btn.pack(side=tk.LEFT, padx=5, pady=5)

        self.upload_btn = tk.Button(
            toolbar, text="上传（文件/文件夹）", command=self.upload_files_or_dirs
        )
        self.upload_btn.pack(side=tk.LEFT, padx=5, pady=5)

        self.download_btn = tk.Button(
            toolbar, text="下载选中", command=self.download_selected
        )
        self.download_btn.pack(side=tk.LEFT, padx=5, pady=5)

        self.delete_btn = tk.Button(
            toolbar, text="删除选中", command=self.delete_selected
        )
        self.delete_btn.pack(side=tk.LEFT, padx=5, pady=5)

        columns = ("name", "type")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        self.tree.heading("name", text="/public_dir 条目")
        self.tree.heading("type", text="类型")
        self.tree.column("name", width=520)
        self.tree.column("type", width=80, anchor="center")
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
        show_dir = "/public_dir" + ("/" + self.current_dir if self.current_dir else "")
        self.set_status(f"正在获取 {show_dir} 列表...")
        self.refresh_btn.config(state=tk.DISABLED)
        try:
            entries = list_public_entries(self.current_dir)
        except Exception as e:
            self.set_status("获取失败")
            messagebox.showerror("错误", f"获取列表失败：{e}")
            self.refresh_btn.config(state=tk.NORMAL)
            return

        def update_ui():
            self.tree.delete(*self.tree.get_children())
            self.tree.heading("name", text=f"{show_dir} 条目")
            if self.current_dir:
                self.tree.insert("", tk.END, values=("..", "上级"), tags=("updir",))
            for e in entries:
                typ = "目录" if e["is_dir"] else "文件"
                tag = "dir" if e["is_dir"] else "file"
                self.tree.insert("", tk.END, values=(e["name"], typ), tags=(tag,))
            self.set_status(f"{show_dir} 共 {len(entries)} 个条目")
            self.refresh_btn.config(state=tk.NORMAL)

        self.after(0, update_ui)

    def on_double_click(self, event):
        item_id = self.tree.selection()
        if not item_id:
            return
        item_id = item_id[0]
        name, typ = self.tree.item(item_id, "values")

        if name == "..":
            if "/" in self.current_dir:
                self.current_dir = self.current_dir.rsplit("/", 1)[0]
            else:
                self.current_dir = ""
            self.refresh_file_list_async()
            return

        if typ == "目录":
            self.current_dir = f"{self.current_dir}/{name}" if self.current_dir else name
            self.refresh_file_list_async()
        else:
            self.download_and_open(name)

    def download_and_open(self, name):
        subdir = self.current_dir.replace("/", "_")
        dst_path = (
            os.path.join(DOWNLOAD_DIR, subdir, name)
            if subdir
            else os.path.join(DOWNLOAD_DIR, name)
        )

        def status_cb(text):
            self.after(0, lambda: self.set_status(text))

        def worker():
            try:
                self.set_status(f"正在开始下载：{name}")
                download_public_file_stream(self.current_dir, name, dst_path, status_cb=status_cb)
                self.set_status(f"下载完成：{dst_path}")
            except Exception as e:
                self.set_status("下载失败")
                messagebox.showerror("错误", f"下载失败：{e}")

        threading.Thread(target=worker, daemon=True).start()

        def wait_and_open():
            threshold = 1 * 1024 * 1024
            tries = 0
            import time
            while tries < 40:
                if os.path.exists(dst_path) and os.path.getsize(dst_path) >= threshold:
                    break
                tries += 1
                time.sleep(0.5)
            try:
                if os.path.exists(dst_path):
                    os.startfile(dst_path)
            except Exception:
                webbrowser.open(dst_path)

        threading.Thread(target=wait_and_open, daemon=True).start()

    def download_selected(self):
        items = self.tree.selection()
        if not items:
            messagebox.showinfo("提示", "请先在列表中选中要下载的文件")
            return
        for item in items:
            name, typ = self.tree.item(item, "values")
            if typ != "文件":
                continue
            threading.Thread(
                target=self.download_and_open, args=(name,), daemon=True
            ).start()

    def upload_files_or_dirs(self):
        file_paths = filedialog.askopenfilenames(title="选择要上传的文件（可多选，可取消）")
        file_paths = list(file_paths)

        dir_roots = []
        while True:
            root = filedialog.askdirectory(title="选择要上传的根文件夹（取消结束选择）")
            if not root:
                break
            dir_roots.append(os.path.abspath(root))

        if not file_paths and not dir_roots:
            return

        def status_cb(text):
            self.after(0, lambda: self.set_status(text))

        def worker():
            global _created_dirs
            with _created_dirs_lock:
                _created_dirs = set()
            base = self.current_dir
            try:
                for p in file_paths:
                    name = os.path.basename(p)
                    remote_rel = f"{base}/{name}" if base else name
                    upload_single_file(p, remote_rel, status_cb=status_cb)

                for root in dir_roots:
                    root_name = os.path.basename(root.rstrip("\\/"))
                    for dirpath, _, filenames in os.walk(root):
                        for name in filenames:
                            local_path = os.path.join(dirpath, name)
                            rel_path = os.path.relpath(local_path, root).replace("\\", "/")
                            if base:
                                remote_rel = f"{base}/{root_name}/{rel_path}"
                            else:
                                remote_rel = f"{root_name}/{rel_path}"
                            upload_single_file(local_path, remote_rel_path=remote_rel, status_cb=status_cb)

                status_cb("上传完成")
                self.refresh_file_list_async()
            except Exception as e:
                self.set_status("上传失败")
                messagebox.showerror("错误", f"上传失败：{e}")

        threading.Thread(target=worker, daemon=True).start()

    def delete_selected(self):
        items = self.tree.selection()
        if not items:
            messagebox.showinfo("提示", "请先在列表中选中要删除的条目")
            return
        names = []
        for item in items:
            name, typ = self.tree.item(item, "values")
            if name == "..":
                continue
            names.append(name)

        if not names:
            return

        if not messagebox.askyesno(
            "确认删除",
            f"确定要删除选中的 {len(names)} 个条目吗？\n\n"
            + "\n".join(names[:10])
            + ("..." if len(names) > 10 else ""),
        ):
            return

        def status_cb(text):
            self.after(0, lambda: self.set_status(text))

        def worker():
            try:
                delete_files_from_public_dir(self.current_dir, names, status_cb=status_cb)
                self.refresh_file_list_async()
            except Exception as e:
                self.set_status("删除失败")
                messagebox.showerror("错误", f"删除失败：{e}")

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    app = YSZNViewer()
    app.mainloop()
