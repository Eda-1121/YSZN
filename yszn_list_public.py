import requests
from bs4 import BeautifulSoup
from urllib.parse import unquote

BASE_URL = "http://138.64.68.102:8898"
BASIC_TOKEN = "RWRhMTEyMTowOTE2"          # 和前面脚本一样
PHPSESSID = "2c94f845086e4316dc256e17697a4695"         # 同上

session = requests.Session()
session.headers.update({
    "Authorization": f"Basic {BASIC_TOKEN}",
    "User-Agent": "Mozilla/5.0 (compatible; MSIE 11.0; Windows NT 6.1)",
    "Accept": "text/html, */*",
    "Accept-Language": "zh-cn",
    "Cache-Control": "no-cache",
    "Connection": "Keep-Alive",
})
session.cookies.set("PHPSESSID", PHPSESSID, domain="138.64.68.102", path="/")

def list_public_dir():
    url = f"{BASE_URL}/public_dir/"
    r = session.get(url, timeout=10)
    r.raise_for_status()
    html = r.text

    soup = BeautifulSoup(html, "html.parser")
    names = set()

    for a in soup.find_all("a"):
        href = a.get("href") or ""
        if href in ("../", "./", "/", ".thumb", "/public_dir/.thumb"):
            continue
        href = href.split("?", 1)[0]
        name = href.split("/")[-1]
        if not name:
            continue
        # URL 解码成正常文字
        name = unquote(name)
        if name == ".thumb":
            continue
        names.add(name)

    print("=== /public_dir ===")
    for name in sorted(names, key=lambda x: x.lower()):
        print(name)

if __name__ == "__main__":
    list_public_dir()
