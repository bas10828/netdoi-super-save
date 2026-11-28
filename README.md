# Netdoi super Save

Exchange files between a Windows PC and a phone over the same Wi-Fi, from the phone's browser. No app to install on the phone.

## Features

- Browse the shared folder and its subfolders, with thumbnails, search, sorting and filters by file type
- Preview before downloading: images, video and audio (with seeking), PDF pages, text files
- Download one file, a zip of several selected files, or a whole folder as a zip
- Upload any file from the phone into the folder you are viewing, with progress for each file
- Capture the PC screen and save it to the phone
- Send text both ways (serial numbers, MAC addresses, links): text from the phone goes straight to the PC clipboard; the PC clipboard can be pulled to the phone
- Pause sharing from the tray (e.g. on a customer's Wi-Fi); the setting survives a restart
- PIN login, tray icon with a QR code for the phone URL

## Setup

Double-click `setup.bat`. It:

1. finds Python 3.12, or installs it (winget, else the python.org installer, per user, quiet)
2. installs the packages from `requirements.txt`
3. adds a Windows Firewall rule for private networks (asks for admin; skip with `setup.ps1 -NoFirewall`)
4. adds a shortcut to the Startup folder so it starts with Windows
5. starts the app (restarts it if it is already running)

Safe to run again. Manual way: Windows, Python 3.12, `pip install -r requirements.txt`.

## Uninstall

Double-click `uninstall.bat`. It stops the app, removes the Startup shortcut and the firewall rule, then asks (default no) whether to remove the Python packages and the local settings/text history/log. It never deletes the shared folder, Python, or the program folder.

## Run

```
pythonw netdoi_super_save.pyw
```

On first start it creates `config.json` with a random PIN, a session secret, port `8765` and the shared folder (`Desktop\Netdoi Share`). Change the PIN from the tray menu (ดู/แก้ตั้งค่า); it applies without a restart.

On the phone, open `http://<PC IP>:8765` or scan the QR code from the tray menu.

## Security

- Plain HTTP: use it only on a network you trust, and never forward the port to the internet.
- Only the shared folder is reachable. Paths are checked so they cannot leave it, and links/junctions are not followed.
- HTML, SVG and other active files are always downloaded, never shown inline.

## Tests

Run against the running app on `127.0.0.1`:

```
python tests/e2e.py      # upload / download / names / PIN change
python tests/e2e2.py     # browsing, previews, range, zip, path safety
python tests/e2e3.py     # text/clipboard + pause (overwrites and restores the clipboard text)
python tests/ui_flow.py  # real browser upload/download (needs: pip install --target tests/pylib websocket-client==1.8.0)
```

`tests/e2e.py` removes files that appear in the shared folder root while it runs, so don't upload at the same time.
