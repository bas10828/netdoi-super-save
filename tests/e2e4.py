"""Tests for delete (Recycle Bin), rename and new folder.

Works inside `_e2e4 ลบ` in the share folder and removes it afterwards.
Items deleted by the test land in the PC Recycle Bin (small, named _e2e4*).
"""
import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote, urlencode

APP = Path(__file__).resolve().parent.parent
config = json.loads((APP / "config.json").read_text(encoding="utf-8-sig"))
port = config["port"]
share = Path(config["share_dir"])
ROOT = "_e2e4 ลบ"
failed = []


def check(label, ok, extra=""):
    print("PASS" if ok else "FAIL", label, extra)
    if not ok:
        failed.append(label)


def request(method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
    c.request(method, path, body, headers or {})
    r = c.getresponse()
    data = r.read()
    c.close()
    return r, data


r, _ = request("POST", "/login", urlencode({"pin": config["pin"]}),
               {"Content-Type": "application/x-www-form-urlencoded"})
auth = {"Cookie": r.getheader("Set-Cookie").split(";")[0]}
jhead = dict(auth, **{"Content-Type": "application/json"})


def post(path, data, headers=jhead):
    r, body = request("POST", path, json.dumps(data), headers)
    try:
        return r.status, json.loads(body)
    except ValueError:
        return r.status, body


def upload(dir_rel, name, data=b"hello"):
    r, body = request("POST", f"/upload?{urlencode({'dir': dir_rel, 'name': name})}", data,
                      dict(auth, **{"Content-Type": "application/octet-stream"}))
    return r.status, body.decode("utf-8", "replace")


root = share / ROOT
outside = Path(tempfile.mkdtemp(prefix="nss_outside_"))
(outside / "keep.txt").write_text("keep", encoding="utf-8")
try:
    # ---- auth
    for path in ("/api/delete", "/api/rename", "/api/mkdir"):
        r, _ = request("POST", path, "{}", {"Content-Type": "application/json"})
        check(f"401 {path}", r.status == 401)

    # ---- new folder
    status, body = post("/api/mkdir", {"dir": "", "name": ROOT})
    check("mkdir root test folder", status == 200 and root.is_dir(), body)
    status, _ = post("/api/mkdir", {"dir": "", "name": ROOT})
    check("mkdir existing -> 409", status == 409)
    status, body = post("/api/mkdir", {"dir": ROOT, "name": "ย่อย"})
    check("mkdir Thai subfolder", status == 200 and (root / "ย่อย").is_dir(), body)
    for bad in ["..", ".", "a/b", "a\\b", "", "   ", ".upload-x.part", "desktop.ini", "~$x"]:
        status, _ = post("/api/mkdir", {"dir": ROOT, "name": bad})
        check(f"mkdir bad name {bad!r} refused", status == 400)
    status, _ = post("/api/mkdir", {"dir": ROOT + "/nope", "name": "x"})
    check("mkdir in missing folder -> 404", status == 404)
    status, _ = post("/api/mkdir", {"dir": "../", "name": "x"})
    check("mkdir traversal dir -> 404", status == 404)
    status, body = post("/api/mkdir", {"dir": ROOT, "name": "a:b?"})
    check("mkdir sanitizes : ?", status == 200 and body["name"] == "a_b_", body)

    # ---- rename
    upload(ROOT, "photo.jpg", b"jpgdata")
    upload(ROOT, "other.jpg", b"other")
    status, body = post("/api/rename", {"dir": ROOT, "name": "photo.jpg", "new": "รูปใหม่.jpg"})
    check("rename file (Thai)", status == 200 and (root / "รูปใหม่.jpg").read_bytes() == b"jpgdata", body)
    status, _ = post("/api/rename", {"dir": ROOT, "name": "รูปใหม่.jpg", "new": "other.jpg"})
    check("rename onto existing -> 409", status == 409 and (root / "other.jpg").read_bytes() == b"other")
    status, body = post("/api/rename", {"dir": ROOT, "name": "other.jpg", "new": "OTHER.jpg"})
    check("case-only rename", status == 200 and "OTHER.jpg" in os.listdir(root), body)
    status, _ = post("/api/rename", {"dir": ROOT, "name": "ย่อย", "new": "ย่อย2"})
    check("rename folder", status == 200 and (root / "ย่อย2").is_dir())
    status, _ = post("/api/rename", {"dir": ROOT, "name": "OTHER.jpg", "new": "../escape.jpg"})
    check("rename to ../ refused", status == 400 and not (share / "escape.jpg").exists())
    status, _ = post("/api/rename", {"dir": ROOT, "name": "OTHER.jpg", "new": "sub/x.jpg"})
    check("rename with slash refused", status == 400)
    status, _ = post("/api/rename", {"dir": "", "name": "", "new": "x"})
    check("rename share root refused", status == 404 and share.is_dir())
    status, _ = post("/api/rename", {"dir": ROOT, "name": "../" + ROOT, "new": "x"})
    check("rename traversal source refused", status == 404 and root.is_dir())
    status, _ = post("/api/rename", {"dir": ROOT, "name": "missing.jpg", "new": "x.jpg"})
    check("rename missing -> 404", status == 404)

    # ---- delete
    status, body = post("/api/delete", {"dir": ROOT, "names": ["รูปใหม่.jpg"]})
    check("delete file -> recycle bin", status == 200 and body["deleted"] == ["รูปใหม่.jpg"]
          and not (root / "รูปใหม่.jpg").exists(), body)
    upload(ROOT + "/ย่อย2", "inner.txt")
    status, body = post("/api/delete", {"dir": ROOT, "names": ["ย่อย2"]})
    check("delete folder with contents", status == 200 and not (root / "ย่อย2").exists(), body)
    upload(ROOT, "a.txt")
    upload(ROOT, "b.txt")
    status, body = post("/api/delete", {"dir": ROOT, "names": ["a.txt", "missing.txt", "b.txt"]})
    check("delete partial: 2 ok, 1 missing", status == 200 and sorted(body["deleted"]) == ["a.txt", "b.txt"]
          and body["failed"] == ["missing.txt"], body)
    status, body = post("/api/delete", {"dir": "", "names": [""]})
    check("delete share root refused", status == 409 and share.is_dir(), body)
    status, body = post("/api/delete", {"dir": ROOT, "names": [".."]})
    check("delete .. refused", status == 409 and share.is_dir(), body)
    status, _ = post("/api/delete", {"dir": ROOT, "names": []})
    check("delete empty list -> 400", status == 400)
    status, _ = post("/api/delete", {"dir": ROOT, "names": "a.txt"})
    check("delete names not list -> 400", status == 400)

    # locked file: Python's open() does not share delete access
    upload(ROOT, "locked.txt")
    with open(root / "locked.txt", "rb"):
        status, body = post("/api/delete", {"dir": ROOT, "names": ["locked.txt"]})
    check("delete locked file reports failure", status == 409 and body["failed"] == ["locked.txt"]
          and (root / "locked.txt").exists(), body)

    # junction to a folder outside the share must never be followed
    junction = root / "junc"
    subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(outside)], capture_output=True, check=True)
    status, body = post("/api/delete", {"dir": ROOT, "names": ["junc"]})
    check("delete via junction refused", (outside / "keep.txt").exists() and body.get("deleted") == [], body)
    status, _ = post("/api/delete", {"dir": ROOT + "/junc", "names": ["keep.txt"]})
    check("delete inside junction refused", (outside / "keep.txt").exists())
    status, _ = post("/api/rename", {"dir": ROOT + "/junc", "name": "keep.txt", "new": "gone.txt"})
    check("rename inside junction refused", status == 404 and (outside / "keep.txt").exists())
    status, _ = post("/api/mkdir", {"dir": ROOT + "/junc", "name": "x"})
    check("mkdir inside junction refused", status == 404 and not (outside / "x").exists())
    os.rmdir(junction)

    # ---- still usable after all the refusals
    status, _ = post("/api/mkdir", {"dir": ROOT, "name": "while-ok"})
    check("mkdir still works", status == 200)
finally:
    if (root / "junc").exists():
        os.rmdir(root / "junc")
    shutil.rmtree(root, ignore_errors=True)
    shutil.rmtree(outside, ignore_errors=True)
    check("cleanup", not root.exists())

print(f"\n{'ALL PASS' if not failed else 'FAILED: ' + ', '.join(failed)}")
sys.exit(1 if failed else 0)
