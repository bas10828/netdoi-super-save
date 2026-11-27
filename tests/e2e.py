"""End-to-end test against the running app on 127.0.0.1. Removes only files it creates."""
import hashlib
import http.client
import json
import os
import socket
import sys
import time
from pathlib import Path
from urllib.parse import quote, urlencode

APP = Path(r"D:\THEKKBox\DEV\netdoi-super-save")
config = json.loads((APP / "config.json").read_text(encoding="utf-8-sig"))
share = Path(config["share_dir"])
port = config["port"]
before = {p.name for p in share.iterdir()}
failed = []


def check(label, ok, extra=""):
    print("PASS" if ok else "FAIL", label, extra)
    if not ok:
        failed.append(label)


def request(method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=120)
    c.request(method, path, body, headers or {})
    r = c.getresponse()
    data = r.read()
    c.close()
    return r, data


r, _ = request("POST", "/login", urlencode({"pin": config["pin"]}),
               {"Content-Type": "application/x-www-form-urlencoded"})
check("login", r.status == 303)
auth = {"Cookie": r.getheader("Set-Cookie").split(";")[0]}

r, data = request("GET", "/", headers=auth)
check("main page", r.status == 200 and b'id="pick"' in data)

big = os.urandom(1024 * 1024) * 400
digest = hashlib.sha256(big).hexdigest()
name = "ทดสอบ ไฟล์ใหญ่ #1 100%.bin"
start = time.time()
r, saved = request("POST", "/upload?name=" + quote(name), big, auth)
check("upload 400MB", r.status == 200 and saved.decode() == name, f"{time.time() - start:.1f}s")
check("hash on disk", hashlib.sha256((share / name).read_bytes()).hexdigest() == digest)
r, data = request("GET", "/files/" + quote(name, safe=""), headers=auth)
check("download hash", r.status == 200 and hashlib.sha256(data).hexdigest() == digest)
check("thai disposition", quote(name, safe="") in r.getheader("Content-Disposition"))

r, saved = request("POST", "/upload?name=" + quote(name), b"second", auth)
check("duplicate renamed", saved.decode() == "ทดสอบ ไฟล์ใหญ่ #1 100% (1).bin", saved.decode())
check("original kept", (share / name).stat().st_size == len(big))

for raw, expect in [("..\\..\\e2e_x.txt", "e2e_x.txt"), ("../../e2e_y.txt", "e2e_y.txt"),
                    ("CON.txt", "_CON.txt"), ('e2e<a>:b?.txt', "e2e_a__b_.txt"), ("e2e_empty.txt", "e2e_empty.txt")]:
    r, saved = request("POST", "/upload?name=" + quote(raw, safe=""), b"" if "empty" in raw else b"x", auth)
    check("name " + raw, r.status == 200 and saved.decode() == expect and (share / expect).is_file(), saved.decode())
r, _ = request("POST", "/upload?name=..", b"x", auth)
check("name '..' rejected", r.status == 400)

for path in ["/files/..%5C..%5Cconfig.json", "/files/..%2Fx", "/files/..", "/files/C%3A%5CWindows%5Cwin.ini"]:
    r, _ = request("GET", path, headers=auth)
    check("traversal " + path, r.status == 404)

r, _ = request("POST", "/upload?name=e2e_noauth.txt", b"x" * 5_000_000)
check("upload without cookie", r.status == 401 and not (share / "e2e_noauth.txt").exists())
for path in ["/api/list", "/files/e2e_x.txt"]:
    r, _ = request("GET", path)
    check("no cookie " + path, r.status == 401)

s = socket.create_connection(("127.0.0.1", port))
s.sendall(f"POST /upload?name=e2e_cut.bin HTTP/1.1\r\nHost: x\r\nCookie: {auth['Cookie']}\r\n"
          "Content-Length: 1000000\r\n\r\n".encode() + b"x" * 1000)
s.close()
time.sleep(2)
check("cut upload leaves nothing", not (share / "e2e_cut.bin").exists() and not list(share.glob(".upload-*")))

r, data = request("GET", "/api/list?path=", headers=auth)
names = [f["name"] for f in json.loads(data)["items"]]
check("list", name in names and "e2e_x.txt" in names)

r, data = request("POST", "/capture", headers=auth)
check("capture", r.status == 200 and data.startswith(b"\x89PNG"), str(r.status))

cfg_path = APP / "config.json"
original = cfg_path.read_bytes()
try:
    changed = dict(config, pin="909090")
    time.sleep(0.05)
    cfg_path.write_text(json.dumps(changed, indent=2, ensure_ascii=False), encoding="utf-8")
    r, _ = request("GET", "/api/list", headers=auth)
    check("old cookie rejected after PIN change", r.status == 401)
    r, _ = request("POST", "/login", "pin=909090", {"Content-Type": "application/x-www-form-urlencoded"})
    check("new PIN works without restart", r.status == 303)
finally:
    cfg_path.write_bytes(original)
    time.sleep(0.05)
    os.utime(cfg_path)
r, _ = request("GET", "/api/list", headers=auth)
check("original PIN restored", r.status == 200)

for p in share.iterdir():
    if p.name not in before and p.is_file():
        p.unlink()
check("cleanup", {p.name for p in share.iterdir()} == before)
sys.exit(1 if failed else 0)
