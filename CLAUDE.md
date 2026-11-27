# Netdoi super Save — notes

User rule: notes/memory about this program live in this folder (not in the global memory dir).

## What it is
- Python stdlib HTTP server + pystray tray icon: `netdoi_super_save.pyw`, run by `pythonw.exe` (Python 3.12). Web UI in `web/` (index.html, app.js, app.css, login.html, manifest.webmanifest) — part of the app, served from disk per request (UI edits need no restart; .pyw edits do).
- Phone (Android, same Wi-Fi) opens `http://<PC LAN IP>:8765` (tray → แสดง QR code) → PIN → file manager for the shared folder.
- Autostart: `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Netdoi super Save.lnk`.
- Moved here from `D:\THEKKBox\si\claude\netdoi-super-save` on 2026-11-27.

## Config (`config.json`)
- `pin`, `port` (8765), `secret` (HMAC key for session cookie), `share_dir` (default `C:\Users\Dell\Desktop\Netdoi Share`).
- Reloaded on each request when mtime changes: new PIN works without restart, old cookies invalid. Port change needs restart.

## Features (v3 "file manager", 2026-11-27)
- Browse share_dir + subfolders (hash route `#/a/b`), breadcrumbs, folders first, list/grid view, sort (date/name/size), kind filter chips, recursive name search (`/api/search`, max 300 results / 4 s).
- Thumbnails (jpg/png/gif/webp/bmp/tif + PDF page 1) via Pillow/PyMuPDF, in-memory LRU 600, 2 concurrent.
- Preview: image (inline), video/audio (inline + HTTP Range/206 for seeking), PDF (server renders pages to JPEG via PyMuPDF — Android Chrome can't show PDF inline), text (UTF-8 → cp874 fallback, 512 KB cap), others = info card + download. Swipe/arrows between files.
- Select: tap thumbnail or long-press; selection bar shows count + size (+N โฟลเดอร์); 1 file = direct download, else zip. Folder row zip button + "โหลดทั้งโฟลเดอร์".
- Zip: POST `/api/zip` {dir, names} → token (15 min) → GET `/zip/<token>` streamed ZIP_STORED, UTF-8 names, locked files skipped.
- Upload to current folder, per-file progress, cancel. Same name → `name (1).ext`.
- Android back closes preview/selection first (history layers), then goes up a folder.
- Screen capture: labeled pill "ภาพจอคอม" in header → modal with big "บันทึกภาพจอคอม" + green "เก็บรูปลงโทรศัพท์" (user missed the icon-only version, 2026-11-27).
- Pause sharing (2026-11-27): tray checkbox "หยุดแชร์ชั่วคราว" → `config.json` `"paused": true` (survives restart; editable by hand). While paused every route except static files returns 503 (`web/paused.html` for `/`), incl. login and upload. Tray icon turns grey with red pause badge.
- Text / clipboard (2026-11-27): header pill "ข้อความ" → panel. Phone → PC: POST `/api/clips` stores + sets Windows clipboard (ctypes, CRLF) (+ tray notification only if enabled, see below). PC → phone: button "ดึงข้อความที่ copy ไว้ในคอม" (POST `/api/clips/pull`) or tray "ส่งข้อความที่ copy ไว้ไปโทรศัพท์". History = `clips.json` (last 50, gitignored, user data). Each message has a red "ลบ" button (POST `/api/clips/delete` {id}); header button "ลบทั้งหมด" (tap twice). Page copies via execCommand fallback (navigator.clipboard needs https). Panel polls every 3 s.
- WARNING: share_dir now holds the user's real files. `tests/e2e.py` deletes every file that appears in share root during its run — don't run it while the user is uploading.
- Delete / rename / new folder (2026-11-27): POST `/api/delete` {dir, names} → Recycle Bin via `SHFileOperationW` (FOF_ALLOWUNDO; FOF_WANTNUKEWARNING pops a dialog on the PC if an item is too big for the bin), per-item result `{deleted, failed}` (409 when nothing deleted; locked files fail). POST `/api/rename` {dir, name, new} (409 if target exists; case-only rename ok). POST `/api/mkdir` {dir, name}. New names via `new_name_or_none()` (no `/` `\`, safe_name, not hidden). Share root itself can never be deleted/renamed. UI: selection bar 2nd row = เปลี่ยนชื่อ (1 item) / ลบ (red) / โหลด; chip "โฟลเดอร์ใหม่" next to โหลดทั้งโฟลเดอร์; one `<dialog id=ask>` for confirm + name input (errors shown inside, dialog stays).
- Tray notifications OFF by default (user: too annoying, 2026-11-27). `notify()` only fires when config.json has `"notify": true`.

## Security rules (keep)
- Every path goes through `resolve_rel()`: rejects `..`, `.`, `\`, `:`, NUL, hidden names; `resolve()` must stay inside share_dir. Junctions/symlinks hidden from listing, walk, zip, search.
- Inline only for raster images/video/audio (`INLINE_TYPES`); html/svg/xml etc. always `attachment`. Inline responses get `CSP: sandbox`. Page CSP: script-src 'self'.
- All endpoints except `/`, `/login`, static files need the cookie.
- HTTP only (no TLS); current PIN is weak — user informed.
- Git: public repo https://github.com/bas10828/netdoi-super-save (branch main). `.gitignore` keeps config.json (PIN + secret), log, qr.png, backups, tests/pylib out. Never commit config.json or write the PIN into tracked files.

## Testing
- `tests/e2e.py` (upload/download/dedupe/names/PIN change, 28 checks) + `tests/e2e2.py` (browse, traversal, junction, range, inline policy, thumbs, PDF, cp874, zip, 401 on all endpoints, 71 checks) — both pass 2026-11-27. They run against the live app on 127.0.0.1 and clean up after themselves.
- `tests/e2e3.py` = clips + pause (17 checks, pass 2026-11-27). Overwrites the PC clipboard during the run and restores text only (an image on the clipboard is lost); restores config.json + clips.json. (Tray notifications only if `"notify": true`.)
- `tests/ui_flow.py` = real browser JS path in headless Chrome: file-picker upload into subfolder, row download (Thai name), select 2 → zip, new folder / rename (incl. duplicate-name error) / delete with cancel + confirm, screen capture, text panel; 27 checks pass 2026-11-27. Note: Runtime.evaluate keeps top-level `const` between calls — wrap snippets in `{}`. Uses `tests/pylib` (websocket-client, installed).
- `Server.handle_error` logs unexpected handler exceptions to the log file (pythonw has no stderr).
- `tests/ui_shots.py` = headless Chrome over CDP at 390 px, needs `websocket-client` (`pip install --target tests/pylib websocket-client==1.8.0`) and demo files in share `_demo_ui` (delete after). Claude-in-Chrome extension was not connected.
- `tests/e2e4.py` = delete/rename/mkdir API (41 checks: bad names, traversal, share root, locked file, junction to outside, 401). Deleted test items go to the PC Recycle Bin (tiny, `_e2e4*`).
- Always `compile()` before restart: pythonw hides syntax errors. Restart = kill pythonw with `netdoi_super_save` in cmdline, start the .lnk; check port 8765 + log.
- Backups: `.bak_20261127` (screenshot-only), `.bak_20261127b` (before file manager).
- Deps: Pillow 13, pystray, segno 1.6.6, PyMuPDF (user site-packages, imported lazily as `pymupdf`).

## Status (end of 2nd session 2026-11-27)
- 2026-11-27: pushed to GitHub up to the text-panel delete commit (user said "บันทึก push เลย"). Ask before each future push; never push config.json/clips.json.
- User is already using it for real (phone → PC photo uploads seen in share_dir).
- Backups: `.bak_20261127c` = before pause/clipboard, `.bak_20261127d` = before atomic writes.
- 2026-11-27 afternoon (after a power cut, no damage): config.json/clips.json now written via `write_text_atomic()` (tmp + fsync + os.replace); `*.tmp` gitignored. Pause/clipboard + this committed locally as `e5b1873`, later pushed. Then delete/rename/mkdir + notifications-off + per-message delete, pushed too. Backup `.bak_20261127e` = before delete/rename.
- Run tests with `C:\Users\Dell\AppData\Local\Programs\Python\Python312\python.exe` — plain `python` on PATH is the WindowsApps stub without pystray (e2e3 imports the .pyw).
- Share folder was empty at 16:30 (earlier phone photos gone — user moved them? not confirmed).
- Suggested but not chosen yet: resumable chunked upload for big videos, auto-clean old files, package as .exe (PyInstaller), stronger PIN (shown in tray). Offered: notify only for incoming phone text (not chosen). Skipped on purpose: video thumbnails (ffmpeg), HEIC, HTTPS.
- User feedback: icon-only buttons get missed — use labeled buttons for main actions. Tray toasts are annoying — keep them off. Wants to delete things (text messages one by one) — a list that only grows is a problem.
- User confirmed the clipboard behaviour they need: phone text is set once; next Ctrl+C on PC replaces it (the app never re-sets/locks the clipboard). Keep it that way.
- Tests can leave the test string `S/N ZAT309N118941…` on the PC clipboard; a later phone "pull" then stores it in clips.json (found + removed once, 2026-11-27).

## Open
- Not yet tested on the real Android phone over Wi-Fi (a phone at 192.168.114.113 did send text at 11:31, so LAN access works).
- Crumb row is crowded at 390 px since "โฟลเดอร์ใหม่" was added (current folder name gets cut) — offered to rearrange.
- Video thumbnails: none (no ffmpeg). HEIC: no preview.
