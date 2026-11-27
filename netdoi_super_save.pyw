"""Netdoi super Save: exchange files between this PC and a phone browser on the same LAN.

The phone browses the shared folder and its subfolders, previews files (images,
video, audio, PDF pages, text), downloads one file or a zip of a selection or a
folder, uploads any file, and captures this PC's screen.

The web UI is in the web/ folder next to this script. Runs without a window; a
tray icon shows that it is running. Settings (PIN, port, share_dir) are in
config.json next to this script and are reloaded when the file changes.
"""

import ctypes
import hashlib
import hmac
import io
import json
import logging
import math
import os
import re
import secrets
import shutil
import socket
import stat
import subprocess
import sys
import threading
import time
import zipfile
from collections import OrderedDict
from ctypes import wintypes
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

import pystray
from PIL import Image, ImageDraw, ImageFont, ImageGrab, ImageOps

APP_DIR = Path(__file__).resolve().parent
WEB_DIR = APP_DIR / "web"
CONFIG_PATH = APP_DIR / "config.json"
LOG_PATH = APP_DIR / "netdoi_super_save.log"
LOGO_PATH = APP_DIR / "logo.jpg"
DEFAULT_PORT = 8765
DEFAULT_SHARE_DIR = Path.home() / "Desktop" / "Netdoi Share"
CHUNK_SIZE = 1024 * 1024
SOCKET_TIMEOUT = 120
MAX_NAME_LENGTH = 180
PART_PREFIX = ".upload-"
PART_SUFFIX = ".part"
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} | {
    f"{device}{n}" for device in ("COM", "LPT") for n in "0123456789\u00b9\u00b2\u00b3"
}
HIDDEN_NAMES = {"desktop.ini", "thumbs.db", ".ds_store"}
HIDDEN_ATTRS = stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM
MAX_FAILS = 5
LOCK_SECONDS = 300
COOKIE_NAME = "ps_session"
THUMB_SIZE = 256
THUMB_CACHE_ITEMS = 600
PDF_MAX_PIXELS = 12_000_000
TEXT_LIMIT = 512 * 1024
SEARCH_LIMIT = 300
SEARCH_SECONDS = 4
ZIP_TOKEN_SECONDS = 900
MAX_JSON_BODY = 1024 * 1024
CLIPS_PATH = APP_DIR / "clips.json"
MAX_CLIPS = 50
MAX_CLIP_CHARS = 100_000

KIND_EXTENSIONS = {
    "image": "jpg jpeg png gif webp bmp avif heic heif tif tiff svg ico",
    "video": "mp4 m4v mov webm mkv avi 3gp wmv flv mpg mpeg ts",
    "audio": "mp3 m4a aac wav ogg oga opus flac wma amr",
    "pdf": "pdf",
    "doc": "doc docx odt rtf pages",
    "sheet": "xls xlsx xlsm ods numbers",
    "slide": "ppt pptx odp key",
    "archive": "zip rar 7z tar gz tgz bz2 xz iso",
    "text": "txt md log csv tsv json xml yaml yml ini cfg conf rsc py js ts css html htm sql bat cmd ps1 sh",
    "apk": "apk xapk",
}
KIND_OF_EXT = {ext: kind for kind, exts in KIND_EXTENSIONS.items() for ext in exts.split()}
# Only these are ever served inline; everything else (html, svg, xml...) is forced to download.
INLINE_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif",
    "webp": "image/webp", "bmp": "image/bmp", "avif": "image/avif",
    "mp4": "video/mp4", "m4v": "video/mp4", "mov": "video/mp4", "webm": "video/webm",
    "mkv": "video/x-matroska", "3gp": "video/3gpp",
    "mp3": "audio/mpeg", "m4a": "audio/mp4", "aac": "audio/aac", "wav": "audio/wav",
    "ogg": "audio/ogg", "oga": "audio/ogg", "opus": "audio/ogg", "flac": "audio/flac",
}
THUMB_EXT = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tif", "tiff", "pdf"}
STATIC_FILES = {
    "/app.js": (WEB_DIR / "app.js", "text/javascript; charset=utf-8"),
    "/app.css": (WEB_DIR / "app.css", "text/css; charset=utf-8"),
    "/manifest.webmanifest": (WEB_DIR / "manifest.webmanifest", "application/manifest+json"),
    "/logo.jpg": (LOGO_PATH, "image/jpeg"),
}
PAGE_CSP = ("default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; "
            "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")

log = logging.getLogger("netdoi_super_save")
capture_lock = threading.Lock()
fail_lock = threading.Lock()
failures = {}  # client ip -> (count, locked_until)
pdf_lock = threading.Lock()  # PyMuPDF is not thread safe
thumb_slots = threading.BoundedSemaphore(2)
thumb_lock = threading.Lock()
thumb_cache = OrderedDict()  # (path, mtime_ns, size) -> jpeg bytes, b"" when it failed
zip_lock = threading.Lock()
zip_jobs = {}  # token -> (expires, [(arcname, path)], filename)
clipboard_lock = threading.Lock()
clips_lock = threading.Lock()
tray = None  # pystray.Icon once the tray is running


def setup_logging():
    handler = RotatingFileHandler(LOG_PATH, maxBytes=200_000, backupCount=1, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)


def write_text_atomic(path, text):
    """Write a whole file so a power cut leaves either the old or the new content."""
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load_config():
    config = {}
    if CONFIG_PATH.exists():
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    changed = False
    defaults = {
        "pin": lambda: f"{secrets.randbelow(1_000_000):06d}",
        "port": lambda: DEFAULT_PORT,
        "secret": lambda: secrets.token_hex(32),
        "share_dir": lambda: str(DEFAULT_SHARE_DIR),
    }
    for key, make in defaults.items():
        if not config.get(key):
            config[key] = make()
            changed = True
    if changed:
        write_text_atomic(CONFIG_PATH, json.dumps(config, indent=2, ensure_ascii=False))
    return config


config_lock = threading.Lock()
config_mtime = None


def refresh_config():
    """Reload config.json after it is edited, so a new PIN works without a restart."""
    global config_mtime
    try:
        mtime = CONFIG_PATH.stat().st_mtime_ns
    except OSError:
        return
    with config_lock:
        if mtime == config_mtime:
            return
        try:
            config = load_config()
            share_dir = Path(config["share_dir"])
            share_dir.mkdir(parents=True, exist_ok=True)
            config_mtime = CONFIG_PATH.stat().st_mtime_ns
        except (OSError, ValueError, KeyError):
            log.exception("config.json is invalid, keeping previous settings")
            config_mtime = mtime
            return
        old = Handler.config
        if old and str(old.get("port")) != str(config["port"]):
            log.warning("port change needs a restart")
        if old and str(old.get("pin")) != str(config["pin"]):
            log.info("PIN changed")
        Handler.config = config
        Handler.share_dir = share_dir.resolve()
    update_tray()


def is_paused():
    return bool(Handler.config and Handler.config.get("paused"))


def set_paused(paused):
    """Turn sharing off/on. Stored in config.json so it survives a restart."""
    with config_lock:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
        config["paused"] = bool(paused)
        write_text_atomic(CONFIG_PATH, json.dumps(config, indent=2, ensure_ascii=False))
    refresh_config()
    log.info("sharing %s", "paused" if paused else "resumed")


def lan_ip():
    # Connecting a UDP socket sends no packet; it only selects the outgoing interface.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def show_qr(url):
    """Save a QR code of the phone URL next to the script and open it in the image viewer."""
    import segno  # imported here so the server still runs if segno is missing

    buffer = io.BytesIO()
    segno.make(url, error="m").save(buffer, kind="png", scale=12, border=4)
    code = Image.open(io.BytesIO(buffer.getvalue())).convert("RGB")
    font = ImageFont.load_default(size=34)
    width = max(code.width, int(font.getlength(url)) + 60)
    image = Image.new("RGB", (width, code.height + 70), "white")
    image.paste(code, ((width - code.width) // 2, 0))
    draw = ImageDraw.Draw(image)
    draw.text((image.width // 2, code.height + 20), url, fill="black", font=font, anchor="mt")
    path = APP_DIR / "qr.png"
    image.save(path)
    os.startfile(path)


def capture_png():
    with capture_lock:
        image = ImageGrab.grab(all_screens=True)
        buffer = io.BytesIO()
        image.save(buffer, "PNG", compress_level=3)
    return buffer.getvalue()


# ------------------------------------------------------------------ clipboard

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_user32.OpenClipboard.argtypes = [wintypes.HWND]
_user32.OpenClipboard.restype = wintypes.BOOL
_user32.CloseClipboard.restype = wintypes.BOOL
_user32.EmptyClipboard.restype = wintypes.BOOL
_user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
_user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
_user32.GetClipboardData.argtypes = [wintypes.UINT]
_user32.GetClipboardData.restype = wintypes.HANDLE
_user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
_user32.SetClipboardData.restype = wintypes.HANDLE
_kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
_kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
_kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
_kernel32.GlobalLock.restype = ctypes.c_void_p
_kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
_kernel32.GlobalUnlock.restype = wintypes.BOOL
_kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
_kernel32.GlobalFree.restype = wintypes.HGLOBAL


class _Clipboard:
    """Open the Windows clipboard, retrying while another program holds it."""

    def __enter__(self):
        clipboard_lock.acquire()
        for _ in range(40):
            if _user32.OpenClipboard(None):
                return self
            time.sleep(0.05)
        clipboard_lock.release()
        raise OSError("clipboard is busy")

    def __exit__(self, *exc):
        _user32.CloseClipboard()
        clipboard_lock.release()


def get_clipboard_text():
    with _Clipboard():
        if not _user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return None
        handle = _user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        pointer = _kernel32.GlobalLock(handle)
        if not pointer:
            return None
        try:
            return ctypes.wstring_at(pointer)
        finally:
            _kernel32.GlobalUnlock(handle)


def set_clipboard_text(text):
    data = text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-16-le") + b"\0\0"
    with _Clipboard():
        _user32.EmptyClipboard()
        handle = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            raise OSError("GlobalAlloc failed")
        pointer = _kernel32.GlobalLock(handle)
        ctypes.memmove(pointer, data, len(data))
        _kernel32.GlobalUnlock(handle)
        if not _user32.SetClipboardData(CF_UNICODETEXT, handle):
            _kernel32.GlobalFree(handle)  # still ours only when SetClipboardData failed
            raise OSError("SetClipboardData failed")


def load_clips():
    try:
        clips = json.loads(CLIPS_PATH.read_text(encoding="utf-8"))
        return clips if isinstance(clips, list) else []
    except (OSError, ValueError):
        return []


def add_clip(text, source):
    """Store a text message (newest first). source is 'phone' or 'pc'."""
    text = text.replace("\r\n", "\n")[:MAX_CLIP_CHARS]
    with clips_lock:
        clips = load_clips()
        if clips and clips[0]["text"] == text and clips[0]["from"] == source:
            return clips[0]  # pressing the button twice adds nothing
        clip = {"id": secrets.token_hex(6), "text": text, "from": source, "time": time.time()}
        clips = [clip] + clips[: MAX_CLIPS - 1]
        write_text_atomic(CLIPS_PATH, json.dumps(clips, ensure_ascii=False))
    return clip


def clear_clips():
    with clips_lock:
        write_text_atomic(CLIPS_PATH, "[]")


def notify(message, title="Netdoi super Save"):
    try:
        if tray is not None:
            tray.notify(message[:200], title)
    except Exception:
        log.info("tray notification failed", exc_info=True)


# ---------------------------------------------------------------- file system


def safe_name(raw):
    """Turn a client supplied file name into a plain Windows file name, or None."""
    name = raw.replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join("_" if c in '<>:"|?*' else c for c in name if c.isprintable() or c == "\u200d")
    name = name.strip().rstrip(". ")
    if not name:
        return None
    if name.split(".", 1)[0].rstrip().upper() in RESERVED_NAMES:
        name = "_" + name
    if len(name) > MAX_NAME_LENGTH:
        suffix = Path(name).suffix[:20]
        name = name[: MAX_NAME_LENGTH - len(suffix)] + suffix
    return name


def extension(name):
    return Path(name).suffix.lower().lstrip(".")


def kind_of(name):
    return KIND_OF_EXT.get(extension(name), "other")


def preview_of(name):
    """How the web page can show this file: image, video, audio, pdf, text or None."""
    ext = extension(name)
    kind = kind_of(name)
    if ext in INLINE_TYPES:
        return kind
    if kind in ("pdf", "text"):
        return kind
    return None


def is_hidden_name(name):
    lower = name.lower()
    partial = lower.startswith(PART_PREFIX) and lower.endswith(PART_SUFFIX)
    return partial or lower in HIDDEN_NAMES or name.startswith("~$")


def is_link(entry):
    try:
        return entry.is_symlink() or entry.is_junction()
    except OSError:
        return True


def is_visible(entry):
    """Plain, non-hidden files and folders. Links and junctions are never shown or followed."""
    if is_hidden_name(entry.name) or is_link(entry):
        return False
    try:
        return not entry.stat(follow_symlinks=False).st_file_attributes & HIDDEN_ATTRS
    except OSError:
        return False


def split_rel(rel):
    """Split a '/'-separated relative path into checked parts, or None if not allowed."""
    rel = rel.strip("/")
    parts = rel.split("/") if rel else []
    for part in parts:
        if part in ("", ".", "..") or any(c in part for c in "\\:\0") or is_hidden_name(part):
            return None
    return parts


def resolve_rel(share_dir, rel, want=None):
    """Map a path relative to the shared folder onto disk; None if missing or outside it."""
    parts = split_rel(rel)
    if parts is None:
        return None
    try:
        real = share_dir.joinpath(*parts).resolve(strict=True)
        if real != share_dir:
            if not real.is_relative_to(share_dir):
                return None  # escaped through a link or a device name
            if os.stat(real).st_file_attributes & HIDDEN_ATTRS:
                return None
        if want == "dir" and not real.is_dir():
            return None
        if want == "file" and not real.is_file():
            return None
    except (OSError, ValueError):
        return None
    return real


def join_rel(*parts):
    return "/".join(p.strip("/") for p in parts if p and p.strip("/"))


def count_children(path, cap=9999):
    count = 0
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                if is_visible(entry):
                    count += 1
                    if count >= cap:
                        break
    except OSError:
        return None
    return count


def describe(entry):
    info = entry.stat(follow_symlinks=False)
    if entry.is_dir(follow_symlinks=False):
        return {"name": entry.name, "kind": "folder", "mtime": info.st_mtime,
                "count": count_children(entry.path)}
    return {"name": entry.name, "kind": kind_of(entry.name), "preview": preview_of(entry.name),
            "thumb": extension(entry.name) in THUMB_EXT, "size": info.st_size, "mtime": info.st_mtime}


def list_dir(path):
    items = []
    with os.scandir(path) as entries:
        for entry in entries:
            try:
                if is_visible(entry):
                    items.append(describe(entry))
            except OSError:
                continue  # removed or unreadable while listing
    return items


def walk(root):
    """Yield (entry, relative parent parts) for every visible entry below root."""
    stack = [(root, ())]
    while stack:
        folder, rel = stack.pop()
        try:
            with os.scandir(folder) as it:
                entries = [e for e in it if is_visible(e)]
        except OSError:
            continue
        for entry in entries:
            yield entry, rel
            try:
                if entry.is_dir(follow_symlinks=False):
                    stack.append((entry.path, rel + (entry.name,)))
            except OSError:
                pass


def move_without_overwrite(source, folder, name):
    stem, suffix = Path(name).stem, Path(name).suffix
    target = folder / name
    number = 0
    while True:
        try:
            os.rename(source, target)  # on Windows this fails if the target exists
            return target
        except FileExistsError:
            number += 1
            target = folder / f"{stem} ({number}){suffix}"


def remove_stale_parts(root):
    stack = [root]
    while stack:
        folder = stack.pop()
        try:
            with os.scandir(folder) as it:
                entries = list(it)
        except OSError:
            continue
        for entry in entries:
            if is_link(entry):
                continue
            name = entry.name.lower()
            try:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)
                elif name.startswith(PART_PREFIX) and name.endswith(PART_SUFFIX):
                    os.unlink(entry.path)
            except OSError:
                log.warning("cannot clean %s", entry.path)


def disposition(name, kind="attachment"):
    fallback = "".join(c if " " <= c <= "~" and c not in '"\\' else "_" for c in name)
    return f"{kind}; filename=\"{fallback}\"; filename*=UTF-8''{quote(name, safe='')}"


def parse_range(header, size):
    """Return (start, end) for a single byte range, None to send everything, False if unsatisfiable."""
    match = re.fullmatch(r"\s*bytes=(\d*)-(\d*)\s*", header or "")
    if not match or not (match[1] or match[2]):
        return None
    if match[1]:
        start = int(match[1])
        end = min(int(match[2]), size - 1) if match[2] else size - 1
    else:
        start, end = max(0, size - int(match[2])), size - 1
    if start >= size or start > end:
        return False
    return start, end


# ----------------------------------------------------------- previews / thumbs


def flatten(image):
    if image.mode in ("RGBA", "LA", "P", "PA"):
        image = image.convert("RGBA")
        background = Image.new("RGB", image.size, "white")
        background.paste(image, mask=image.getchannel("A"))
        return background
    return image.convert("RGB")


def jpeg_bytes(image, quality=82):
    buffer = io.BytesIO()
    flatten(image).save(buffer, "JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def render_pdf_page(path, page_no, width):
    """Return (page_count, PIL image) for one PDF page rendered about `width` pixels wide."""
    import pymupdf  # imported lazily so the server starts even without it

    with pdf_lock, pymupdf.open(path) as doc:
        count = doc.page_count
        if not 0 <= page_no < count:
            raise IndexError(page_no)
        page = doc[page_no]
        rect = page.rect
        zoom = min(width / rect.width, math.sqrt(PDF_MAX_PIXELS / (rect.width * rect.height)), 6)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return count, image


def pdf_page_count(path):
    import pymupdf

    with pdf_lock, pymupdf.open(path) as doc:
        if doc.needs_pass:
            raise ValueError("encrypted")
        return doc.page_count


def make_thumb(path):
    if extension(path.name) == "pdf":
        _, image = render_pdf_page(path, 0, THUMB_SIZE * 1.5)
    else:
        with Image.open(path) as source:
            source.draft("RGB", (THUMB_SIZE * 2, THUMB_SIZE * 2))
            image = ImageOps.exif_transpose(source)
            image.thumbnail((THUMB_SIZE * 1.5, THUMB_SIZE * 1.5))
    image.thumbnail((THUMB_SIZE * 1.5, THUMB_SIZE * 1.5))
    return jpeg_bytes(image, 78)


def cached_thumb(path):
    info = path.stat()
    key = (str(path), info.st_mtime_ns, info.st_size)
    with thumb_lock:
        if key in thumb_cache:
            thumb_cache.move_to_end(key)
            return thumb_cache[key]
    with thumb_slots:
        try:
            data = make_thumb(path)
        except Exception:
            log.info("no thumbnail for %s", path, exc_info=True)
            data = b""
    with thumb_lock:
        thumb_cache[key] = data
        while len(thumb_cache) > THUMB_CACHE_ITEMS:
            thumb_cache.popitem(last=False)
    return data


def read_text(path):
    with path.open("rb") as source:
        data = source.read(TEXT_LIMIT + 1)
    truncated = len(data) > TEXT_LIMIT
    data = data[:TEXT_LIMIT]
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", "replace"), "utf-16", truncated
    try:
        return data.decode("utf-8-sig"), "utf-8", truncated
    except UnicodeDecodeError as error:
        if truncated and error.start >= len(data) - 3:
            return data[: error.start].decode("utf-8-sig", "replace"), "utf-8", truncated
    try:
        return data.decode("cp874"), "cp874", truncated
    except UnicodeDecodeError:
        return data.decode("utf-8", "replace"), "utf-8", truncated


# ------------------------------------------------------------------- web pages


def web_file(name):
    return (WEB_DIR / name).read_text(encoding="utf-8")


class Handler(BaseHTTPRequestHandler):
    timeout = SOCKET_TIMEOUT
    config = None
    share_dir = None

    # ---- helpers

    def session_token(self):
        key = bytes.fromhex(self.config["secret"])
        return hmac.new(key, str(self.config["pin"]).encode(), hashlib.sha256).hexdigest()

    def is_authorized(self):
        refresh_config()
        try:
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
        except CookieError:
            return False
        item = cookie.get(COOKIE_NAME)
        return bool(item) and hmac.compare_digest(item.value.encode(), self.session_token().encode())

    def start(self, status, content_type, length=None, headers=None, cache="no-store"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()

    def reply(self, status, body=b"", content_type="text/plain; charset=utf-8", headers=None, cache="no-store"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.start(status, content_type, len(body), headers, cache)
        self.wfile.write(body)

    def reply_json(self, data, status=200):
        self.reply(status, json.dumps(data, ensure_ascii=False), "application/json; charset=utf-8")

    def query(self):
        pairs = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
        return {key: values[0] for key, values in pairs.items()}

    def read_body(self, limit):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if not 0 <= length <= limit:
            return None
        return self.rfile.read(length)

    def login_page(self, status=200, message=""):
        page = web_file("login.html").replace("__MESSAGE__", message)
        self.reply(status, page, "text/html; charset=utf-8", {"Content-Security-Policy": PAGE_CSP})

    def log_message(self, fmt, *args):
        pass  # no console under pythonw

    # ---- routing

    @staticmethod
    def sharing_paused():
        refresh_config()  # pick up a pause set from the tray or by editing config.json
        return is_paused()

    def paused_reply(self, path):
        if path == "/":
            self.reply(503, web_file("paused.html"), "text/html; charset=utf-8",
                       {"Content-Security-Policy": PAGE_CSP})
        else:
            self.reply(503, "ปิดการแชร์อยู่ เปิดได้จากไอคอนที่คอม")

    def do_GET(self):
        path = urlsplit(self.path).path
        try:
            if path in STATIC_FILES:
                file, content_type = STATIC_FILES[path]
                self.reply(200, file.read_bytes(), content_type, cache="no-cache")
            elif self.sharing_paused():
                self.paused_reply(path)
            elif path == "/":
                if self.is_authorized():
                    self.reply(200, web_file("index.html"), "text/html; charset=utf-8",
                               {"Content-Security-Policy": PAGE_CSP})
                else:
                    self.login_page()
            elif not self.is_authorized():
                self.reply(401, "unauthorized")
            elif path == "/api/list":
                self.handle_list()
            elif path == "/api/search":
                self.handle_search()
            elif path == "/api/thumb":
                self.handle_thumb()
            elif path == "/api/pdfinfo":
                self.handle_pdf_info()
            elif path == "/api/pdfpage":
                self.handle_pdf_page()
            elif path == "/api/text":
                self.handle_text()
            elif path.startswith("/files/"):
                self.handle_download(unquote(path[len("/files/"):]))
            elif path.startswith("/zip/"):
                self.handle_zip_download(path[len("/zip/"):])
            elif path == "/api/clips":
                self.reply_json({"items": load_clips()})
            else:
                self.reply(404, "not found")
        except ConnectionError:
            pass  # the phone went away

    def do_POST(self):
        path = urlsplit(self.path).path
        try:
            if self.sharing_paused():
                if path == "/upload":
                    self.refuse_upload(503, "ปิดการแชร์อยู่ เปิดได้จากไอคอนที่คอม")
                else:
                    self.paused_reply(path)
            elif path == "/login":
                self.handle_login()
            elif path == "/upload":
                self.handle_upload()
            elif not self.is_authorized():
                self.reply(401, "unauthorized")
            elif path == "/capture":
                self.handle_capture()
            elif path == "/api/zip":
                self.handle_zip_request()
            elif path == "/api/clips":
                self.handle_clip_send()
            elif path == "/api/clips/pull":
                self.handle_clip_pull()
            elif path == "/api/clips/clear":
                clear_clips()
                self.reply_json({"items": []})
            else:
                self.reply(404, "not found")
        except ConnectionError:
            pass

    # ---- login and screen

    def handle_login(self):
        ip = self.client_address[0]
        body = self.read_body(1024)
        if body is None:
            self.reply(400, "bad request")
            return
        form = parse_qs(body.decode("utf-8", "replace"))
        pin = form.get("pin", [""])[0].strip()
        refresh_config()
        with fail_lock:
            count, locked_until = failures.get(ip, (0, 0))
            locked = time.monotonic() < locked_until
            correct = not locked and hmac.compare_digest(pin.encode(), str(self.config["pin"]).encode())
            if correct:
                failures.pop(ip, None)
            elif not locked:
                count += 1
                if count >= MAX_FAILS:
                    failures[ip] = (0, time.monotonic() + LOCK_SECONDS)
                    log.warning("login locked for %s", ip)
                else:
                    failures[ip] = (count, 0)
        if locked:
            self.login_page(429, "ใส่ผิดหลายครั้ง รอ 5 นาที")
        elif correct:
            cookie = f"{COOKIE_NAME}={self.session_token()}; Max-Age=2592000; Path=/; HttpOnly; SameSite=Strict"
            self.reply(303, headers={"Location": "/", "Set-Cookie": cookie})
        else:
            self.login_page(401, "PIN ไม่ถูกต้อง")

    def handle_capture(self):
        try:
            data = capture_png()
        except Exception:
            log.exception("capture failed")
            self.reply(503, "บันทึกจอไม่ได้ (จอคอมอาจ lock หรือมีหน้าต่าง UAC เปิดอยู่)")
            return
        self.reply(200, data, "image/png")

    # ---- text / clipboard

    def handle_clip_send(self):
        body = self.read_body(MAX_JSON_BODY)
        try:
            text = json.loads(body or b"")["text"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError
        except (ValueError, KeyError, TypeError):
            self.reply_json({"error": "ไม่มีข้อความ"}, 400)
            return
        clip = add_clip(text, "phone")
        try:
            set_clipboard_text(clip["text"])
            copied = True
        except OSError:
            log.warning("cannot set clipboard", exc_info=True)
            copied = False
        notify(("Copy แล้ว กด Ctrl+V วางได้เลย\n" if copied else "") + clip["text"], "ข้อความจากโทรศัพท์")
        log.info("text from %s (%d chars)", self.client_address[0], len(clip["text"]))
        self.reply_json({"item": clip, "copied": copied})

    def handle_clip_pull(self):
        try:
            text = get_clipboard_text()
        except OSError:
            self.reply_json({"error": "คลิปบอร์ดคอมไม่ว่าง ลองใหม่อีกครั้ง"}, 503)
            return
        if not text or not text.strip():
            self.reply_json({"error": "คอมยังไม่ได้ copy ข้อความไว้ (copy ที่คอมก่อน แล้วกดใหม่)"}, 404)
            return
        self.reply_json({"item": add_clip(text, "pc")})

    # ---- browsing

    def handle_list(self):
        rel = self.query().get("path", "")
        folder = resolve_rel(self.share_dir, rel, "dir")
        if folder is None:
            self.reply_json({"error": "ไม่พบโฟลเดอร์นี้"}, 404)
            return
        try:
            items = list_dir(folder)
        except OSError:
            log.exception("cannot list %s", folder)
            self.reply_json({"error": "เปิดโฟลเดอร์ไม่ได้"}, 503)
            return
        self.reply_json({"path": join_rel(*split_rel(rel)), "items": items})

    def handle_search(self):
        needle = self.query().get("q", "").strip().casefold()
        results, truncated = [], False
        if needle:
            deadline = time.monotonic() + SEARCH_SECONDS
            for entry, rel in walk(self.share_dir):
                if time.monotonic() > deadline:
                    truncated = True
                    break
                if needle not in entry.name.casefold():
                    continue
                try:
                    item = describe(entry)
                except OSError:
                    continue
                item["dir"] = "/".join(rel)
                results.append(item)
                if len(results) >= SEARCH_LIMIT:
                    truncated = True
                    break
        self.reply_json({"items": results, "truncated": truncated})

    def handle_thumb(self):
        path = resolve_rel(self.share_dir, self.query().get("path", ""), "file")
        if path is None or extension(path.name) not in THUMB_EXT:
            self.reply(404, "not found")
            return
        data = cached_thumb(path)
        if not data:
            self.reply(415, "no thumbnail")
            return
        self.reply(200, data, "image/jpeg", cache="private, max-age=604800")

    def handle_pdf_info(self):
        path = resolve_rel(self.share_dir, self.query().get("path", ""), "file")
        if path is None or extension(path.name) != "pdf":
            self.reply_json({"error": "ไม่พบไฟล์"}, 404)
            return
        try:
            pages = pdf_page_count(path)
        except Exception:
            log.info("cannot open pdf %s", path, exc_info=True)
            self.reply_json({"error": "เปิด PDF นี้ไม่ได้ (อาจมีรหัสผ่านหรือไฟล์เสีย)"}, 415)
            return
        self.reply_json({"pages": pages})

    def handle_pdf_page(self):
        query = self.query()
        path = resolve_rel(self.share_dir, query.get("path", ""), "file")
        try:
            page_no = int(query.get("page", "0"))
            width = max(200, min(2400, int(query.get("w", "1200"))))
        except ValueError:
            path = None
        if path is None or extension(path.name) != "pdf":
            self.reply(404, "not found")
            return
        try:
            _, image = render_pdf_page(path, page_no, width)
            data = jpeg_bytes(image, 85)
        except Exception:
            log.info("cannot render pdf %s page %s", path, page_no, exc_info=True)
            self.reply(415, "cannot render")
            return
        self.reply(200, data, "image/jpeg", cache="private, max-age=604800")

    def handle_text(self):
        path = resolve_rel(self.share_dir, self.query().get("path", ""), "file")
        if path is None or preview_of(path.name) != "text":
            self.reply_json({"error": "ไม่พบไฟล์"}, 404)
            return
        try:
            text, encoding, truncated = read_text(path)
        except OSError:
            self.reply_json({"error": "อ่านไฟล์ไม่ได้ (อาจถูกเปิดค้างในโปรแกรมอื่น)"}, 503)
            return
        self.reply_json({"text": text, "encoding": encoding, "truncated": truncated})

    # ---- downloads

    def handle_download(self, rel):
        path = resolve_rel(self.share_dir, rel, "file")
        if path is None:
            self.reply(404, "not found")
            return
        try:
            source = path.open("rb")
        except OSError:
            self.reply(409, "เปิดไฟล์ไม่ได้ (อาจถูกเปิดค้างในโปรแกรมอื่น)")
            return
        query = self.query()
        with source:
            size = os.fstat(source.fileno()).st_size
            ext = extension(path.name)
            headers = {"Accept-Ranges": "bytes"}
            if query.get("inline") == "1" and ext in INLINE_TYPES:
                content_type = INLINE_TYPES[ext]
                headers["Content-Disposition"] = disposition(path.name, "inline")
                headers["Content-Security-Policy"] = "sandbox"
                cache = "private, max-age=3600" if "v" in query else "no-store"
            else:
                content_type = "application/octet-stream"
                headers["Content-Disposition"] = disposition(path.name)
                cache = "no-store"
            status, start, end = 200, 0, size - 1
            wanted = parse_range(self.headers.get("Range"), size)
            if wanted is False:
                self.reply(416, "", headers={"Content-Range": f"bytes */{size}"})
                return
            if wanted:
                status, (start, end) = 206, wanted
                headers["Content-Range"] = f"bytes {start}-{end}/{size}"
            left = end - start + 1
            self.start(status, content_type, left, headers, cache)
            source.seek(start)
            try:
                while left > 0:
                    chunk = source.read(min(left, CHUNK_SIZE))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
            except OSError:
                pass  # phone stopped reading, normal for video seeking

    def handle_zip_request(self):
        body = self.read_body(MAX_JSON_BODY)
        try:
            request = json.loads(body or b"")
            base_rel = str(request.get("dir", ""))
            names = request["names"]
            if not isinstance(names, list) or not 1 <= len(names) <= 10000:
                raise ValueError
        except (ValueError, KeyError, TypeError, AttributeError):
            self.reply_json({"error": "คำขอไม่ถูกต้อง"}, 400)
            return
        base = resolve_rel(self.share_dir, base_rel, "dir")
        items = []
        for name in names:
            path = None
            # A name may be a path below base (search results come from many folders).
            if base is not None and isinstance(name, str) and split_rel(name):
                path = resolve_rel(self.share_dir, join_rel(base_rel, name))
            if path is None:
                self.reply_json({"error": f"ไม่พบ {name}"}, 404)
                return
            items.append((join_rel(*split_rel(name)), path))
        stamp = time.strftime("%Y%m%d_%H%M%S")
        if len(items) == 1:
            single = Path(items[0][0])
            filename = f"{single.stem if items[0][1].is_file() else single.name}.zip"
        else:
            folder_name = base.name if base != self.share_dir else "Netdoi Share"
            filename = f"{folder_name}_{len(items)}files_{stamp}.zip"
        token = secrets.token_urlsafe(18)
        now = time.monotonic()
        with zip_lock:
            for old in [t for t, job in zip_jobs.items() if job[0] < now]:
                del zip_jobs[old]
            zip_jobs[token] = (now + ZIP_TOKEN_SECONDS, items, filename)
        self.reply_json({"url": f"/zip/{token}", "filename": filename})

    def handle_zip_download(self, token):
        with zip_lock:
            job = zip_jobs.get(token)
        if job is None or job[0] < time.monotonic():
            self.reply(410, "ลิงก์หมดอายุ กดโหลดใหม่อีกครั้ง")
            return
        _, items, filename = job
        self.start(200, "application/zip", None, {"Content-Disposition": disposition(filename)})
        added = skipped = 0
        try:
            with zipfile.ZipFile(self.wfile, "w", zipfile.ZIP_STORED, allowZip64=True) as archive:
                for arcname, path in items:
                    if path.is_dir():
                        archive.mkdir(arcname)
                        for entry, rel in walk(path):
                            name = "/".join((arcname, *rel, entry.name))
                            if entry.is_dir(follow_symlinks=False):
                                archive.mkdir(name)
                            elif self.add_to_zip(archive, entry.path, name):
                                added += 1
                            else:
                                skipped += 1
                    elif self.add_to_zip(archive, path, arcname):
                        added += 1
                    else:
                        skipped += 1
        except OSError:
            log.info("zip download interrupted: %s", filename)
            return
        log.info("zip %s sent to %s (%d files, %d skipped)", filename, self.client_address[0], added, skipped)

    @staticmethod
    def add_to_zip(archive, path, arcname):
        try:
            archive.write(path, arcname)
            return True
        except PermissionError:
            log.warning("skipped locked file %s", path)
            return False

    # ---- upload

    def refuse_upload(self, status, message):
        self.reply(status, message)
        # Drain a limited part of the body so the browser can read the reply.
        try:
            left = min(int(self.headers.get("Content-Length", "0")), 32 * CHUNK_SIZE)
            self.connection.settimeout(5)
            while left > 0:
                chunk = self.rfile.read1(min(left, CHUNK_SIZE))
                if not chunk:
                    break
                left -= len(chunk)
        except (OSError, ValueError):
            pass

    def handle_upload(self):
        if not self.is_authorized():
            self.refuse_upload(401, "unauthorized")
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            length = -1
        query = self.query()
        name = safe_name(query.get("name", ""))
        folder = resolve_rel(self.share_dir, query.get("dir", ""), "dir")
        if length < 0 or name is None:
            self.refuse_upload(400, "ชื่อไฟล์หรือข้อมูลไม่ถูกต้อง")
            return
        if folder is None:
            self.refuse_upload(404, "ไม่พบโฟลเดอร์ปลายทาง")
            return
        part = folder / f"{PART_PREFIX}{secrets.token_hex(8)}{PART_SUFFIX}"
        try:
            if length > shutil.disk_usage(folder).free:
                self.refuse_upload(507, "พื้นที่ในคอมไม่พอ")
                return
            with part.open("xb") as out:
                left = length
                while left > 0:
                    chunk = self.rfile.read(min(left, CHUNK_SIZE))
                    if not chunk:
                        raise ConnectionError("client disconnected")
                    out.write(chunk)
                    left -= len(chunk)
            saved = move_without_overwrite(part, folder, name)
        except ConnectionError:
            log.info("upload cancelled: %r", name)
            return
        except OSError:
            log.exception("upload failed: %r", name)
            try:
                self.reply(500, "บันทึกไฟล์ในคอมไม่สำเร็จ")
            except OSError:
                pass  # the client is gone
            return
        finally:
            try:
                part.unlink(missing_ok=True)
            except OSError:
                log.warning("cannot remove %s", part)
        log.info("received %r (%d bytes) from %s", str(saved.relative_to(self.share_dir)), length,
                 self.client_address[0])
        self.reply(200, saved.name)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    # On Windows address reuse would let a second instance bind the same port.
    allow_reuse_address = False

    def handle_error(self, request, client_address):
        # pythonw has no stderr, so unexpected handler errors go to the log file.
        log.exception("error while handling a request from %s", client_address[0])


def tray_image():
    try:
        # Upper part of the logo is the mountain mark; the text is unreadable at tray size.
        logo = Image.open(LOGO_PATH).convert("L")
        top = logo.crop((0, 0, logo.width, int(logo.height * 0.52)))
        mark = top.crop(top.point(lambda v: 255 if v < 128 else 0).getbbox())
        side = int(max(mark.size) * 1.08)
        square = Image.new("L", (side, side), 255)
        square.paste(mark, ((side - mark.width) // 2, (side - mark.height) // 2))
        return square.resize((64, 64), Image.LANCZOS).convert("RGBA")
    except Exception:
        log.exception("cannot load logo, using default icon")
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((4, 8, 60, 46), radius=6, fill=(37, 99, 235), outline=(255, 255, 255), width=3)
    draw.rectangle((26, 46, 38, 54), fill=(255, 255, 255))
    draw.rectangle((16, 54, 48, 58), fill=(255, 255, 255))
    return image


tray_images = {}


def paused_image(image):
    """Grey version of the tray icon with a red pause badge."""
    grey = ImageOps.grayscale(image.convert("RGB")).convert("RGBA")
    grey = Image.blend(Image.new("RGBA", grey.size, (255, 255, 255, 255)), grey, 0.45)
    draw = ImageDraw.Draw(grey)
    draw.ellipse((30, 30, 63, 63), fill=(220, 38, 38, 255), outline=(255, 255, 255, 255), width=2)
    draw.rectangle((40, 39, 44, 54), fill=(255, 255, 255, 255))
    draw.rectangle((49, 39, 53, 54), fill=(255, 255, 255, 255))
    return grey


def tray_title():
    return "Netdoi super Save (หยุดแชร์อยู่)" if is_paused() else "Netdoi super Save (กำลังแชร์)"


def update_tray():
    if tray is None or not tray_images:
        return
    try:
        tray.icon = tray_images["paused" if is_paused() else "on"]
        tray.title = tray_title()
        tray.update_menu()
    except Exception:
        log.info("cannot update tray", exc_info=True)


def main():
    global tray
    setup_logging()
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # capture at physical resolution
        refresh_config()
        config = Handler.config
        if config is None:
            raise RuntimeError("cannot load config.json")
        server = Server(("0.0.0.0", int(config["port"])), Handler)
    except Exception:
        log.exception("startup failed (already running?)")
        return 1
    # Clean up only after the port is bound and before serving, so no live upload is touched.
    remove_stale_parts(Handler.share_dir)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log.info("listening on port %s", config["port"])

    def stop(icon, _item):
        log.info("exit from tray")
        icon.stop()

    def open_qr():
        try:
            show_qr(f"http://{lan_ip()}:{config['port']}")
        except Exception:
            log.exception("cannot show QR code")

    def open_config():
        subprocess.Popen(["notepad.exe", str(CONFIG_PATH)])

    def toggle_pause():
        try:
            set_paused(not is_paused())
        except (OSError, ValueError):
            log.exception("cannot change sharing state")
            return
        notify("หยุดแชร์แล้ว โทรศัพท์เข้าไม่ได้จนกว่าจะเปิดอีกครั้ง" if is_paused() else "เปิดแชร์แล้ว")

    def push_clipboard():
        try:
            text = get_clipboard_text()
        except OSError:
            notify("คลิปบอร์ดไม่ว่าง ลองใหม่อีกครั้ง")
            return
        if not text or not text.strip():
            notify("ยังไม่ได้ copy ข้อความไว้")
            return
        add_clip(text, "pc")
        notify("ส่งแล้ว เปิดหน้า \"ข้อความ\" ในโทรศัพท์\n" + text)

    menu = pystray.Menu(
        pystray.MenuItem("แสดง QR code ให้โทรศัพท์สแกน", lambda: open_qr()),
        pystray.MenuItem("ส่งข้อความที่ copy ไว้ไปโทรศัพท์", lambda: push_clipboard()),
        pystray.MenuItem("เปิด folder แชร์", lambda: os.startfile(Handler.share_dir), default=True),
        pystray.MenuItem("หยุดแชร์ชั่วคราว", lambda: toggle_pause(), checked=lambda _: is_paused()),
        pystray.MenuItem(lambda _: f"http://{lan_ip()}:{config['port']}", None, enabled=False),
        pystray.MenuItem("ดู/แก้ตั้งค่า (config.json)", lambda: open_config()),
        pystray.MenuItem("ปิดโปรแกรม", stop),
    )
    tray_images["on"] = tray_image()
    tray_images["paused"] = paused_image(tray_images["on"])
    tray = pystray.Icon("netdoi_super_save", tray_images["paused" if is_paused() else "on"], tray_title(), menu)
    tray.run()
    server.shutdown()
    server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
