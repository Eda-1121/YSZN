from flask import Flask, Response, request
import requests

# 云端配置
REMOTE_BASE = "http://138.64.68.102:8898"
BASIC_TOKEN = "RWRhMTEyMTowOTE2"          # 和下载脚本中一样
PHPSESSID = "2c94f845086e4316dc256e17697a4695"         # 同前

# 本地代理监听地址
LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 5000

session = requests.Session()
session.headers.update({
    "Authorization": f"Basic {BASIC_TOKEN}",
    "User-Agent": "Mozilla/5.0 (compatible; MSIE 11.0; Windows NT 6.1)",
    "Accept-Language": "zh-cn",
    "Cache-Control": "no-cache",
    "Connection": "Keep-Alive",
})
session.cookies.set("PHPSESSID", PHPSESSID, domain="138.64.68.102", path="/")

app = Flask(__name__)

def stream_remote(path):
    url = f"{REMOTE_BASE}{path}"
    # 把 Range 头也转发过去，支持拖动进度条
    headers = {}
    if "Range" in request.headers:
        headers["Range"] = request.headers["Range"]

    r = session.get(url, headers=headers, stream=True)
    def generate():
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                yield chunk

    resp = Response(generate(), status=r.status_code)
    # 把关键响应头转回来
    for h in ["Content-Type", "Content-Length", "Accept-Ranges", "Content-Range"]:
        if h in r.headers:
            resp.headers[h] = r.headers[h]
    return resp

@app.route("/media/<path:subpath>")
def media(subpath):
    # 例: /media/public_dir/movie.mp4 -> 云端 /public_dir/movie.mp4
    remote_path = "/" + subpath
    return stream_remote(remote_path)

if __name__ == "__main__":
    app.run(host=LOCAL_HOST, port=LOCAL_PORT, debug=False)
