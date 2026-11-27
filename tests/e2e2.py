"""Tests for browsing, preview, range, zip and path safety. Creates and removes its own test folder."""
import hashlib
import http.client
import io
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.parse import quote, urlencode

APP = Path(r"D:\THEKKBox\DEV\netdoi-super-save")
SCRATCH = Path(__file__).resolve().parent
config = json.loads((APP / "config.json").read_text(encoding="utf-8-sig"))
share = Path(config["share_dir"])
port = config["port"]
T = "_e2e ทดสอบ"
root = share / T
outside = SCRATCH / "outside_target"
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


def enc(rel):
    return quote(rel, safe="")


def furl(rel):
    return "/files/" + "/".join(quote(p, safe="") for p in rel.split("/"))


# ---------- fixtures
if root.exists():
    raise SystemExit("test folder already exists")
outside.mkdir(exist_ok=True)
(outside / "secret.txt").write_text("SECRET", encoding="utf-8")
(root / "ย่อย").mkdir(parents=True)
from PIL import Image
import pymupdf

Image.new("RGB", (1200, 800), (200, 30, 30)).save(root / "รูป ทดสอบ.jpg", quality=90)
Image.new("RGBA", (300, 300), (0, 0, 255, 128)).save(root / "alpha.png")
doc = pymupdf.open()
for i in range(3):
    doc.new_page().insert_text((72, 72), f"Page {i + 1}")
doc.save(root / "เอกสาร.pdf")
doc.close()
thai = "สวัสดีครับ ภาษาไทย cp874\n"
(root / "ไทย874.txt").write_bytes(thai.encode("cp874"))
(root / "utf8.log").write_bytes("UTF-8 ไทย ✓\n".encode("utf-8"))
(root / "evil.html").write_text("<script>alert(1)</script>", encoding="utf-8")
(root / "evil.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', encoding="utf-8")
blob = os.urandom(300_000)
(root / "ย่อย" / "data.bin").write_bytes(blob)
(root / "ย่อย" / ".upload-deadbeef.part").write_bytes(b"x")
subprocess.run(["cmd", "/c", "mklink", "/J", str(root / "junc"), str(outside)], check=True, capture_output=True)

try:
    r, _ = request("POST", "/login", urlencode({"pin": config["pin"]}),
                   {"Content-Type": "application/x-www-form-urlencoded"})
    auth = {"Cookie": r.getheader("Set-Cookie").split(";")[0]}

    # ---------- static + pages
    for path in ["/app.js", "/app.css", "/manifest.webmanifest", "/logo.jpg"]:
        r, _ = request("GET", path)
        check("static " + path, r.status == 200)
    r, data = request("GET", "/")
    check("login page", r.status == 200 and b'name="pin"' in data)
    r, data = request("GET", "/", headers=auth)
    check("index page + CSP", r.status == 200 and b"app.js" in data and "script-src 'self'" in r.getheader("Content-Security-Policy"))

    # ---------- listing
    r, data = request("GET", "/api/list?path=", headers=auth)
    root_items = {i["name"]: i for i in json.loads(data)["items"]}
    check("root lists test folder", root_items.get(T, {}).get("kind") == "folder")
    r, data = request("GET", "/api/list?path=" + enc(T), headers=auth)
    items = {i["name"]: i for i in json.loads(data)["items"]}
    check("subfolder listing", {"รูป ทดสอบ.jpg", "เอกสาร.pdf", "ย่อย"} <= set(items), str(sorted(items)))
    check("junction hidden", "junc" not in items)
    check("kinds", items["รูป ทดสอบ.jpg"]["kind"] == "image" and items["เอกสาร.pdf"]["preview"] == "pdf"
          and items["evil.html"]["preview"] == "text" and items["ย่อย"]["count"] == 1)
    r, data = request("GET", "/api/list?path=" + enc(T + "/ย่อย"), headers=auth)
    check(".part hidden in subfolder", [i["name"] for i in json.loads(data)["items"]] == ["data.bin"])

    # ---------- traversal / junction
    bad_lists = [T + "/../..", "..", "../", T + "/junc", "C:\\Windows", T + "\\..\\..", "%2e%2e"]
    for rel in bad_lists:
        r, _ = request("GET", "/api/list?path=" + enc(rel), headers=auth)
        check("list refused " + rel, r.status == 404, str(r.status))
    for path in [furl(T + "/junc/secret.txt"), "/files/" + enc(T) + "/..%2F..%2Fconfig.json",
                 "/files/%2e%2e/config.json", "/files/" + enc(T) + "%5C..%5C..%5Cconfig.json",
                 furl(T + "/ย่อย/.upload-deadbeef.part")]:
        r, data = request("GET", path, headers=auth)
        check("download refused " + path, r.status == 404 and b"SECRET" not in data, str(r.status))
    r, data = request("GET", "/api/search?q=secret", headers=auth)
    check("search skips junction", not json.loads(data)["items"])

    # ---------- search
    r, data = request("GET", "/api/search?q=" + enc("ทดสอบ"), headers=auth)
    found = {(i["dir"], i["name"]) for i in json.loads(data)["items"]}
    check("search thai", ("", T) in found and (T, "รูป ทดสอบ.jpg") in found, str(found))

    # ---------- upload into subfolder
    payload = os.urandom(2_000_000)
    r, saved = request("POST", "/upload?dir=" + enc(T + "/ย่อย") + "&name=" + enc("อัป.bin"), payload, auth)
    check("upload to subfolder", r.status == 200 and (root / "ย่อย" / "อัป.bin").read_bytes() == payload)
    r, data = request("GET", furl(T + "/ย่อย/อัป.bin"), headers=auth)
    check("download from subfolder", hashlib.sha256(data).digest() == hashlib.sha256(payload).digest())
    for d in ["ไม่มี", "..", T + "/junc", T + "/รูป ทดสอบ.jpg"]:
        r, _ = request("POST", "/upload?dir=" + enc(d) + "&name=x.bin", b"x", auth)
        check("upload dir refused " + d, r.status == 404, str(r.status))
    check("nothing written outside", sorted(p.name for p in outside.iterdir()) == ["secret.txt"])

    # ---------- range
    rel = T + "/ย่อย/data.bin"
    r, data = request("GET", furl(rel), headers=dict(auth, Range="bytes=10-19"))
    check("range 10-19", r.status == 206 and data == blob[10:20] and r.getheader("Content-Range") == f"bytes 10-19/{len(blob)}")
    r, data = request("GET", furl(rel), headers=dict(auth, Range="bytes=-5"))
    check("range suffix", r.status == 206 and data == blob[-5:])
    r, data = request("GET", furl(rel), headers=dict(auth, Range="bytes=299990-"))
    check("range open end", r.status == 206 and data == blob[299990:])
    r, _ = request("GET", furl(rel), headers=dict(auth, Range="bytes=999999999-"))
    check("range 416", r.status == 416)

    # ---------- inline policy
    r, _ = request("GET", furl(T + "/รูป ทดสอบ.jpg") + "?inline=1&v=1", headers=auth)
    check("jpg inline", r.getheader("Content-Type") == "image/jpeg" and r.getheader("Content-Disposition").startswith("inline")
          and "max-age" in r.getheader("Cache-Control"))
    for name in ["evil.html", "evil.svg"]:
        r, _ = request("GET", furl(T + "/" + name) + "?inline=1", headers=auth)
        check(name + " forced download", r.getheader("Content-Type") == "application/octet-stream"
              and r.getheader("Content-Disposition").startswith("attachment"))

    # ---------- thumbs / pdf / text
    for name in ["รูป ทดสอบ.jpg", "alpha.png", "เอกสาร.pdf"]:
        r, data = request("GET", "/api/thumb?path=" + enc(T + "/" + name) + "&v=1", headers=auth)
        ok = r.status == 200 and data[:2] == b"\xff\xd8"
        if ok:
            im = Image.open(io.BytesIO(data))
            ok = max(im.size) <= 384
        check("thumb " + name, ok, str(r.status))
    r, _ = request("GET", "/api/thumb?path=" + enc(T + "/ไทย874.txt"), headers=auth)
    check("no thumb for txt", r.status == 404)
    r, data = request("GET", "/api/pdfinfo?path=" + enc(T + "/เอกสาร.pdf"), headers=auth)
    check("pdf info", json.loads(data).get("pages") == 3)
    r, data = request("GET", "/api/pdfpage?path=" + enc(T + "/เอกสาร.pdf") + "&page=1&w=900", headers=auth)
    check("pdf page render", r.status == 200 and Image.open(io.BytesIO(data)).width in range(880, 920))
    r, _ = request("GET", "/api/pdfpage?path=" + enc(T + "/เอกสาร.pdf") + "&page=9", headers=auth)
    check("pdf bad page", r.status == 415)
    r, data = request("GET", "/api/text?path=" + enc(T + "/ไทย874.txt"), headers=auth)
    body = json.loads(data)
    check("text cp874", body["text"] == thai and body["encoding"] == "cp874", body.get("encoding"))
    r, data = request("GET", "/api/text?path=" + enc(T + "/utf8.log"), headers=auth)
    check("text utf8", json.loads(data)["text"] == "UTF-8 ไทย ✓\n")

    # ---------- zip
    def get_zip(dir_, names):
        r, data = request("POST", "/api/zip", json.dumps({"dir": dir_, "names": names}),
                          dict(auth, **{"Content-Type": "application/json"}))
        if r.status != 200:
            return r.status, None, None
        job = json.loads(data)
        r, data = request("GET", job["url"], headers=auth)
        return r.status, zipfile.ZipFile(io.BytesIO(data)), r.getheader("Content-Disposition")

    status, z, disp = get_zip(T, ["รูป ทดสอบ.jpg", "ย่อย"])
    names = set(z.namelist()) if z else set()
    check("zip selection", status == 200 and {"รูป ทดสอบ.jpg", "ย่อย/data.bin", "ย่อย/อัป.bin"} <= names, str(names))
    check("zip content hash", z and z.read("ย่อย/data.bin") == blob and z.testzip() is None)
    status, z, disp = get_zip("", [T])
    names = z.namelist() if z else []
    check("zip whole folder", status == 200 and f"{T}/เอกสาร.pdf" in names and not any("junc" in n or "secret" in n for n in names)
          and not any(".part" in n for n in names), str(len(names)))
    check("zip folder filename", disp and quote(T + ".zip", safe="") in disp)
    status, z, _ = get_zip("", [T + "/ย่อย/data.bin", T + "/alpha.png"])
    check("zip mixed folders", status == 200 and set(z.namelist()) == {T + "/ย่อย/data.bin", T + "/alpha.png"})
    for bad in [["../config.json"], [T + "/junc"], [T + "/junc/secret.txt"], ["..\\config.json"], []]:
        status, _, _ = get_zip("", bad)
        check("zip refused " + str(bad), status in (400, 404), str(status))
    r, _ = request("GET", "/zip/notatoken", headers=auth)
    check("zip bad token", r.status == 410)

    # ---------- auth on every endpoint
    for path in ["/api/list", "/api/search?q=a", "/api/thumb?path=x", "/api/pdfinfo?path=x",
                 "/api/pdfpage?path=x", "/api/text?path=x", "/zip/x", furl(rel)]:
        r, _ = request("GET", path)
        check("401 GET " + path, r.status == 401)
    for path in ["/api/zip", "/capture"]:
        r, _ = request("POST", path, b"{}")
        check("401 POST " + path, r.status == 401)
finally:
    os.rmdir(root / "junc")  # removes only the junction, never its target
    assert not (root / "junc").exists()
    shutil.rmtree(root)
    check("outside target intact", (outside / "secret.txt").read_text(encoding="utf-8") == "SECRET")
    shutil.rmtree(outside)

sys.exit(1 if failed else 0)
