import requests

BASE_URL = "http://138.64.68.102:8899"
API_URL = f"{BASE_URL}/api/"

PHPSESSID = "a9e11f8416abadd4e34da6ae2242f802"  # 用你自己的值

session = requests.Session()
session.cookies.set("PHPSESSID", PHPSESSID, domain="138.64.68.102", path="/")

def call_api(payload: dict):
    r = session.post(API_URL, json=payload, timeout=10)
    r.raise_for_status()
    print("status:", r.status_code)
    print("raw:", r.text)

if __name__ == "__main__":
    call_api({"type": "get_sysinfo"})
