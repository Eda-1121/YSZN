import base64
import requests

BASE_URL = "http://138.64.68.102:8898"

# 从 Wireshark 的 Authorization 头里复制 Base64 串，粘到这里（不要解码）
BASIC_TOKEN = "RWRhMTEyMTowOTE2"  # 这里只是示例，用你自己的

# 从 Wireshark 的 Cookie 头里复制 PHPSESSID 的值
PHPSESSID = "2c94f845086e4316dc256e17697a4695"  # 换成你自己的

session = requests.Session()
session.headers.update({
    "Authorization": f"Basic {BASIC_TOKEN}",
    "User-Agent": "Mozilla/5.0 (compatible; MSIE 11.0; Windows NT 6.1)",
    "Accept": "text/html, application/xhtml+xml, */*",
    "Accept-Language": "zh-cn",
    "Cache-Control": "no-cache",
    "Connection": "Keep-Alive",
})
session.cookies.set("PHPSESSID", PHPSESSID, domain="138.64.68.102", path="/")

def download_file(remote_path: str, local_path: str):
    url = f"{BASE_URL}{remote_path}"
    with session.get(url, stream=True, timeout=30) as r:
        r.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    print(f"saved -> {local_path}")

if __name__ == "__main__":
    # 远程路径就直接用 Wireshark 里看到的那种形式
    remote = "/public_dir/学习摄影参考书第一辑（吴晓隆）.pdf"
    download_file(remote, "学习摄影参考书第一辑.pdf")
