"""Run the browser's real upload and download code in headless Chrome (390 px) and check the results on disk.

Needs websocket-client in tests/pylib. Creates and deletes `_demo_flow` in the shared folder.
"""
import base64
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "pylib"))
import websocket  # noqa: E402

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
APP = "http://127.0.0.1:8765"
config = json.loads(Path(r"D:\THEKKBox\DEV\netdoi-super-save\config.json").read_text(encoding="utf-8-sig"))
share = Path(config["share_dir"])
demo = share / "_demo_flow"
work = Path(tempfile.mkdtemp(prefix="flow-", dir=HERE))
downloads = work / "downloads"
downloads.mkdir()
failed = []


def check(label, ok, extra=""):
    print("PASS" if ok else "FAIL", label, extra)
    if not ok:
        failed.append(label)


(demo / "ย่อย").mkdir(parents=True)
(demo / "หนึ่ง.txt").write_bytes("ไฟล์หนึ่ง".encode())
(demo / "สอง.txt").write_bytes("ไฟล์สอง".encode())
uploads = [work / "อัปโหลด ภาษาไทย.txt", work / "photo.bin"]
uploads[0].write_bytes("สวัสดี".encode())
uploads[1].write_bytes(bytes(range(256)) * 4000)

proc = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=9334",
                         f"--user-data-dir={work / 'profile'}", "--no-first-run", "--disable-extensions", "about:blank"])
try:
    for _ in range(50):
        try:
            page = next(t for t in json.load(urllib.request.urlopen("http://127.0.0.1:9334/json/list")) if t["type"] == "page")
            browser_ws = json.load(urllib.request.urlopen("http://127.0.0.1:9334/json/version"))["webSocketDebuggerUrl"]
            break
        except Exception:
            time.sleep(0.2)
    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=30)
    bws = websocket.create_connection(browser_ws, timeout=30)
    counter = [0]
    errors = []
    downloads_done = []

    def call(sock, method, **params):
        counter[0] += 1
        sock.send(json.dumps({"id": counter[0], "method": method, "params": params}))
        while True:
            msg = json.loads(sock.recv())
            if msg.get("method") == "Runtime.exceptionThrown":
                errors.append(msg["params"]["exceptionDetails"].get("exception", {}).get("description"))
            if msg.get("method") == "Browser.downloadProgress" and msg["params"]["state"] == "completed":
                downloads_done.append(msg["params"]["guid"])
            if msg.get("id") == counter[0]:
                return msg.get("result", {})

    cdp = lambda method, **p: call(ws, method, **p)  # noqa: E731

    def js(expr):
        return cdp("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True).get("result", {}).get("value")

    def wait_downloads(n, seconds=20):
        end = time.time() + seconds
        bws.settimeout(0.5)
        while len(downloads_done) < n and time.time() < end:
            try:
                msg = json.loads(bws.recv())
                if msg.get("method") == "Browser.downloadProgress" and msg["params"]["state"] == "completed":
                    downloads_done.append(msg["params"]["guid"])
            except websocket.WebSocketTimeoutException:
                pass
        bws.settimeout(30)

    call(bws, "Browser.setDownloadBehavior", behavior="allow", downloadPath=str(downloads), eventsEnabled=True)
    cdp("Runtime.enable")
    cdp("Page.enable")
    cdp("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=1, mobile=True)
    cdp("Page.navigate", url=APP + "/")
    time.sleep(1)
    js(f"document.querySelector('input[name=pin]').value = {json.dumps(config['pin'])}; document.querySelector('form').submit()")
    time.sleep(1.5)

    # ---- upload through the real file picker into a subfolder
    cdp("Page.navigate", url=APP + "/#/_demo_flow/ย่อย")
    time.sleep(1.5)
    root = cdp("DOM.getDocument")["root"]["nodeId"]
    node = cdp("DOM.querySelector", nodeId=root, selector="#pick")["nodeId"]
    cdp("DOM.setFileInputFiles", nodeId=node, files=[str(p) for p in uploads])
    for _ in range(40):
        time.sleep(0.25)
        if (js("document.getElementById('upTitle').textContent") or "").startswith("ส่งครบ"):
            break
    time.sleep(0.6)
    data = cdp("Page.captureScreenshot", format="png")["data"]
    (HERE / "shot_upload.png").write_bytes(base64.b64decode(data))
    check("upload sheet says done", js("document.getElementById('upTitle').textContent") == "ส่งครบ 2 ไฟล์",
          js("document.getElementById('upTitle').textContent"))
    for p in uploads:
        check("uploaded into subfolder: " + p.name, (demo / "ย่อย" / p.name).read_bytes() == p.read_bytes())
    check("list refreshed after upload", js("document.querySelectorAll('#list .row').length") == 2)

    # ---- single file via the row download icon
    js("[...document.querySelectorAll('.row')].find(r => r.textContent.includes('อัปโหลด')).querySelector('a.more').click()")
    wait_downloads(1)
    got = downloads / "อัปโหลด ภาษาไทย.txt"
    check("row download keeps Thai name", got.exists() and got.read_bytes() == uploads[0].read_bytes(),
          str([p.name for p in downloads.iterdir()]))

    # ---- select two rows + download zip
    cdp("Page.navigate", url=APP + "/#/_demo_flow")
    time.sleep(1.5)
    js("""const rows = [...document.querySelectorAll('.row')];
          rows.find(r => r.textContent.includes('หนึ่ง')).querySelector('.thumb').click();
          rows.find(r => r.textContent.includes('ย่อย')).querySelector('.thumb').click();""")
    time.sleep(0.3)
    check("selection bar", js("document.getElementById('selCount').textContent") == "เลือก 2")
    js("document.getElementById('selDownload').click()")
    wait_downloads(2)
    zips = list(downloads.glob("*.zip"))
    names = set(zipfile.ZipFile(zips[0]).namelist()) if zips else set()
    check("zip via selection", {"หนึ่ง.txt", "ย่อย/อัปโหลด ภาษาไทย.txt", "ย่อย/photo.bin"} <= names, str(names))
    check("selection closed after download", js("document.body.classList.contains('selecting')") is False)

    # ---- screen capture to the phone
    js("document.getElementById('screenBtn').click()")
    time.sleep(0.3)
    js("document.getElementById('sGrab').click()")
    for _ in range(40):
        time.sleep(0.25)
        if js("!document.getElementById('sSaveBig').hidden"):
            break
    data = cdp("Page.captureScreenshot", format="png")["data"]
    (HERE / "shot_screen.png").write_bytes(base64.b64decode(data))
    check("save-to-phone button shown", js("!document.getElementById('sSaveBig').hidden") is True)
    js("document.getElementById('sSaveBig').click()")
    wait_downloads(3)
    pngs = list(downloads.glob("screen_*.png"))
    check("screenshot saved as png", bool(pngs) and pngs[0].read_bytes()[:4] == b"\x89PNG", str([p.name for p in downloads.iterdir()]))

    # ---- text panel (restores PC clipboard text and clips.json afterwards)
    from importlib.machinery import SourceFileLoader
    app = SourceFileLoader("nss_app", str(HERE.parent / "netdoi_super_save.pyw")).load_module()
    clips_file = HERE.parent / "clips.json"
    clips_backup = clips_file.read_bytes() if clips_file.exists() else None
    clipboard_backup = app.get_clipboard_text()
    try:
        js("history.back()")
        time.sleep(0.4)
        js("document.getElementById('textBtn').click()")
        time.sleep(0.5)
        js("document.getElementById('tInput').value = 'S/N ZAT309N118941 https://example.com'; document.getElementById('tSend').click()")
        time.sleep(1.2)
        check("text sent from page", app.get_clipboard_text() == "S/N ZAT309N118941 https://example.com")
        check("text listed with link button", js("document.querySelectorAll('#tList .clip').length") == 1
              and js("!!document.querySelector('#tList a.btn')"))
        data = cdp("Page.captureScreenshot", format="png")["data"]
        (HERE / "shot_text.png").write_bytes(base64.b64decode(data))
    finally:
        if clips_backup is None:
            clips_file.unlink(missing_ok=True)
        else:
            clips_file.write_bytes(clips_backup)
        if clipboard_backup is not None:
            app.set_clipboard_text(clipboard_backup)
    check("no JS errors", not errors, str(errors))
    ws.close()
    bws.close()
finally:
    proc.terminate()
    proc.wait(10)
    shutil.rmtree(demo)
    shutil.rmtree(work, ignore_errors=True)

sys.exit(1 if failed else 0)
