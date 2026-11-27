"""Tests for pause sharing and text/clipboard exchange.

Restores config.json, clips.json and the PC clipboard text afterwards
(a non-text clipboard, e.g. an image, is not restored).
"""
import http.client
import json
import sys
import time
from importlib.machinery import SourceFileLoader
from pathlib import Path
from urllib.parse import urlencode

APP = Path(__file__).resolve().parent.parent
app = SourceFileLoader("nss_app", str(APP / "netdoi_super_save.pyw")).load_module()
CONFIG = APP / "config.json"
CLIPS = APP / "clips.json"
config = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
port = config["port"]
failed = []


def check(label, ok, extra=""):
    print("PASS" if ok else "FAIL", label, extra)
    if not ok:
        failed.append(label)


def request(method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    c.request(method, path, body, headers or {})
    r = c.getresponse()
    data = r.read()
    c.close()
    return r, data


config_backup = CONFIG.read_bytes()
clips_backup = CLIPS.read_bytes() if CLIPS.exists() else None
clipboard_backup = app.get_clipboard_text()
try:
    r, _ = request("POST", "/login", urlencode({"pin": config["pin"]}),
                   {"Content-Type": "application/x-www-form-urlencoded"})
    auth = {"Cookie": r.getheader("Set-Cookie").split(";")[0]}
    jhead = dict(auth, **{"Content-Type": "application/json"})

    # ---- text phone -> PC
    text = "S/N: ZAT309N118941\nMAC 38:6F:AA:BB:CC:DD ไทย"
    r, data = request("POST", "/api/clips", json.dumps({"text": text}), jhead)
    body = json.loads(data)
    check("send text", r.status == 200 and body["copied"] is True)
    check("PC clipboard has text (CRLF)", app.get_clipboard_text() == text.replace("\n", "\r\n"))
    r, data = request("GET", "/api/clips", headers=auth)
    items = json.loads(data)["items"]
    check("history newest first", items[0]["text"] == text and items[0]["from"] == "phone")
    r, _ = request("POST", "/api/clips", json.dumps({"text": text}), jhead)
    r, data = request("GET", "/api/clips", headers=auth)
    check("double send not duplicated", len(json.loads(data)["items"]) == len(items))
    r, _ = request("POST", "/api/clips", json.dumps({"text": "   "}), jhead)
    check("empty text refused", r.status == 400)

    # ---- text PC -> phone
    app.set_clipboard_text("https://example.com/คู่มือ ทดสอบ")
    r, data = request("POST", "/api/clips/pull", b"", auth)
    item = json.loads(data).get("item", {})
    check("pull PC clipboard", r.status == 200 and item.get("from") == "pc"
          and item.get("text") == "https://example.com/คู่มือ ทดสอบ")

    r, data = request("POST", "/api/clips/clear", b"", auth)
    r, data = request("GET", "/api/clips", headers=auth)
    check("clear history", json.loads(data)["items"] == [])

    for method, path in [("GET", "/api/clips"), ("POST", "/api/clips"), ("POST", "/api/clips/pull"),
                         ("POST", "/api/clips/clear")]:
        r, _ = request(method, path, b"{}" if method == "POST" else None)
        check(f"401 {method} {path}", r.status == 401)

    # ---- pause sharing
    paused = dict(config, paused=True)
    time.sleep(0.05)
    CONFIG.write_text(json.dumps(paused, indent=2, ensure_ascii=False), encoding="utf-8")
    r, data = request("GET", "/")
    check("paused page", r.status == 503 and "ปิดการแชร์อยู่".encode() in data)
    r, _ = request("GET", "/api/list?path=", headers=auth)
    check("paused blocks API even with cookie", r.status == 503)
    r, _ = request("POST", "/login", urlencode({"pin": config["pin"]}),
                   {"Content-Type": "application/x-www-form-urlencoded"})
    check("paused blocks login", r.status == 503)
    r, _ = request("POST", "/upload?name=x.txt", b"x" * 1000, auth)
    check("paused blocks upload", r.status == 503)
    r, _ = request("GET", "/app.css")
    check("paused still serves css for the page", r.status == 200)
    CONFIG.write_bytes(config_backup)
    time.sleep(0.05)
    r, _ = request("GET", "/api/list?path=", headers=auth)
    check("resume works with same cookie", r.status == 200)
finally:
    CONFIG.write_bytes(config_backup)
    if clips_backup is None:
        CLIPS.unlink(missing_ok=True)
    else:
        CLIPS.write_bytes(clips_backup)
    if clipboard_backup is not None:
        app.set_clipboard_text(clipboard_backup)

sys.exit(1 if failed else 0)
