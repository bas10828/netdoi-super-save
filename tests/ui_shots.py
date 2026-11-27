"""Drive headless Chrome over CDP at phone size and save screenshots of the UI."""
import base64
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "pylib"))
import websocket  # noqa: E402

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
APP = "http://127.0.0.1:8765"
PIN = json.loads(Path(r"D:\THEKKBox\DEV\netdoi-super-save\config.json").read_text(encoding="utf-8-sig"))["pin"]
OUT = HERE / "shots"
OUT.mkdir(exist_ok=True)
dark = "--dark" in sys.argv

profile = tempfile.mkdtemp(prefix="cdp-profile-", dir=HERE)
proc = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=9333", f"--user-data-dir={profile}",
                         "--no-first-run", "--disable-extensions", "about:blank"])
try:
    for _ in range(50):
        try:
            targets = json.load(urllib.request.urlopen("http://127.0.0.1:9333/json/list"))
            page = next(t for t in targets if t["type"] == "page")
            break
        except Exception:
            time.sleep(0.2)
    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=30)
    counter = [0]
    errors = []

    def cdp(method, **params):
        counter[0] += 1
        ws.send(json.dumps({"id": counter[0], "method": method, "params": params}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("method") == "Runtime.exceptionThrown":
                errors.append(msg["params"]["exceptionDetails"].get("exception", {}).get("description"))
            elif msg.get("method") == "Runtime.consoleAPICalled" and msg["params"]["type"] in ("error", "warning"):
                errors.append(str([a.get("value", a.get("description")) for a in msg["params"]["args"]]))
            elif msg.get("method") == "Log.entryAdded" and msg["params"]["entry"]["level"] == "error":
                errors.append(msg["params"]["entry"]["text"])
            if msg.get("id") == counter[0]:
                return msg.get("result", {})

    def js(expr):
        r = cdp("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        return r.get("result", {}).get("value")

    def shot(name, wait=1.2):
        time.sleep(wait)
        data = cdp("Page.captureScreenshot", format="png")["data"]
        (OUT / f"{name}{'_dark' if dark else ''}.png").write_bytes(base64.b64decode(data))

    cdp("Runtime.enable")
    cdp("Log.enable")
    cdp("Page.enable")
    cdp("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=1, mobile=True)
    cdp("Emulation.setTouchEmulationEnabled", enabled=True)
    cdp("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "dark" if dark else "light"}])

    cdp("Page.navigate", url=APP + "/")
    time.sleep(1)
    shot("01_login", 0.3)
    js(f"document.querySelector('input[name=pin]').value = {json.dumps(PIN)}; document.querySelector('form').submit()")
    time.sleep(1.5)
    cdp("Page.navigate", url=APP + "/#/_demo_ui")
    shot("02_list", 2)
    print("width check:", js("[document.documentElement.scrollWidth, window.innerWidth]"))
    js("document.getElementById('viewBtn').click()")
    shot("03_grid")
    js("document.getElementById('viewBtn').click()")
    js("[...document.querySelectorAll('.row')].find(r => r.textContent.includes('IMG_')).click()")
    shot("04_image_viewer")
    js("history.back()")
    time.sleep(0.5)
    js("[...document.querySelectorAll('.row')].find(r => r.textContent.includes('.pdf')).click()")
    shot("05_pdf_viewer", 2.5)
    js("history.back()")
    time.sleep(0.5)
    js("[...document.querySelectorAll('.row')].find(r => r.textContent.includes('.rsc')).click()")
    shot("06_text_viewer", 1.5)
    js("history.back()")
    time.sleep(0.5)
    js("[...document.querySelectorAll('.row')].find(r => r.textContent.includes('.docx')).click()")
    shot("07_other_viewer")
    js("history.back()")
    time.sleep(0.5)
    print("viewer closed by back:", js("document.getElementById('viewer').hidden"))
    js("""const rows = [...document.querySelectorAll('.row')];
          rows[0].querySelector('.thumb').click(); rows[2].querySelector('.thumb').click(); rows[3].click();""")
    shot("08_selection")
    js("history.back()")
    time.sleep(0.5)
    print("selection closed by back:", js("!document.body.classList.contains('selecting')"))
    js("document.querySelector('#chips [data-kind=image]').click()")
    shot("09_filter_image")
    js("document.querySelector('#chips [data-kind=all]').click()")
    js("const i = document.getElementById('q'); i.value = 'หน้างาน'; i.dispatchEvent(new Event('input'))")
    shot("10_search", 1.5)
    js("const i = document.getElementById('q'); i.value = ''; i.dispatchEvent(new Event('input'))")
    js("[...document.querySelectorAll('.row')].find(r => r.textContent.includes('รูปหน้างาน')).click()")
    shot("11_subfolder")
    print("hash:", js("decodeURIComponent(location.hash)"))
    js("history.back()")
    time.sleep(0.8)
    print("back to parent:", js("decodeURIComponent(location.hash)"))
    js("document.getElementById('screenBtn').click()")
    shot("12_screen", 0.5)
    print("errors:", errors)
    ws.close()
finally:
    proc.terminate()
    proc.wait(10)
