<p align="center">
  <a href="README.md">简体中文</a> | <b>English</b> | <a href="README.ja.md">日本語</a>
</p>

# MCHOSE 2.4G Battery Tray

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-0078D4" alt="Windows 10/11">
  <img src="https://img.shields.io/badge/python-3.13+-3776AB" alt="Python 3.13+">
  <img src="https://img.shields.io/badge/protocol-HID%20vendor%20page%200xFF01-8A2BE2" alt="HID">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT">
  <img src="https://img.shields.io/badge/verified%20on-MCHOSE%20A7%20Pro-orange" alt="A7 Pro">
</p>

Your MCHOSE mouse's battery, living permanently in the system tray — plus one-click DPI switching and a second-by-second drain log. It speaks the vendor's custom HID protocol directly, so you can throw MCHOSE Center in the bin and never think about it again.

Batteries included. Literally.

<p align="center">
  <img src="docs/panel-dark.png" width="360" alt="dark panel">
  &nbsp;&nbsp;
  <img src="docs/panel-light.png" width="360" alt="light panel">
</p>

## ✨ What you get

**Battery, always visible**
- The tray icon *is* the gauge — a mouse that fills up as it drains, auto-inverts for light/dark taskbars, and goes red when you're running on fumes. Battery / number / ring styles available if mice aren't your thing
- Left-click for a Win11 Fluent flyout: frosted glass, DWM rounded corners, the number in a font size you can actually read
- Hover for the full picture: device, battery, **current DPI**, transport, last seen

**DPI switching without the dance**
- Six stages (400 / 800 / 1600 / 3200 / 6400 / 26000 out of the box) from the right-click menu, flashed straight to the mouse's onboard config
- Covers both the USB and 2.4G paths; every write is read back and verified — if the stage table comes back scrambled, you'll hear about it instead of getting radio silence
- The active stage follows the wire: USB path when wired, 2.4G path when wireless

**A drain log with receipts**
- Every 1% is logged to the second. Plug the cable in and polling quietly speeds up to 10 s; unplug and it backs off to your interval
- Browse it grouped by day, stats on top, one-click wipe
- Garbage packets happen (the 2.4G link once reported 83% → 6% → 83%) — so reads that jump more than 10 points get thrown out, the baseline survives restarts, and nothing bigger than a 5% swing ever lands in the log

**Small print, handled**
- Low-battery threshold (10%–40%), autostart, 30 s–10 min polling
- If a read fails, the last good value sticks around — no grey icon flicker at 3 a.m.

<p align="center">
  <img src="docs/history-window.png" width="420" alt="battery history window">
</p>

## 📦 Grab it

Prebuilt exe in [Releases](https://github.com/Sanye223/mchose-2.4g-battery-tray/releases) — data stays in your user profile, the registry remains untouched.

Prefer to build it yourself? Two minutes:

```bat
git clone https://github.com/Sanye223/mchose-2.4g-battery-tray.git
cd mchose-2.4g-battery-tray

:: Python 3.13+ (tkinter required)
python -m venv tkvenv
tkvenv\Scripts\python -m pip install pyinstaller hidapi pillow
tkvenv\Scripts\python -m PyInstaller --noconfirm --clean "2.4G电量托盘.spec"
```

> `fetch_wheels.py` is for when PyPI is a plane ride away — it mirrors the build deps locally.

## 🚀 Driving it

| Action | What happens |
|---|---|
| **Left-click** the tray icon | Toggle the flyout panel |
| **Right-click → DPI 档位** | Switch DPI stage (radio-checked at the current one) |
| **Right-click → 电量记录…** | The drain log, grouped by day |
| **Right-click → 刷新间隔** | 30 s / 1 / 2 / 5 / 10 min — 10 s while charging, hands-free |
| **Right-click → 低电量阈值** | 10%–40%, red icon below it |
| **Right-click → 图标样式** | Mouse / battery / number / ring |
| **Right-click → 开机自启** | Autostart (HKCU Run key, current user only) |

CLI flags for the curious:

```bat
2.4G电量托盘.exe --cli          :: one read, printed, exit
2.4G电量托盘.exe --panel        :: panel open on launch
2.4G电量托盘.exe --interval 10  :: override the poll interval for this run
```

## 🗂 Where things live

Everything under `%APPDATA%\MchoseBattery\`:

| File | What's in it |
|---|---|
| `tray.json` | Settings — interval, threshold, style, autostart |
| `history.json` | The drain log (rolling, last 800 entries) |
| `tray.log` | Runtime log — failed-read forensics and DPI switch results end up here |

## 🔌 The protocol, war stories included

Byte-level frames are documented in the [`mchose_hid.py`](mchose_hid.py) comments; the full reverse-engineering write-up lives in [`docs/PROTOCOL.md`](docs/PROTOCOL.md). The cliff notes, a.k.a. where the bodies are buried:

- The battery query payload is `0x06`. **`F4 55` is a profile-reload command** — fire it at the mouse and it reloads its onboard config, DPI reset included. Ask me how I know
- On the A7 Pro, the **DPI write frame has a different layout than the read frame**. Echo the read frame back with one byte tweaked and the whole stage table scrambles (observed: X became 26000/8193/16387)
- The 2.4G link will lie to you on occasion — 83% → 6% → 83% was a real afternoon. Display and history both need jump filtering, or your logs fill up with fiction
- Plug the cable in and the mouse switches to wired mode under a different PID. Enumeration has to stay loose or you'll chase ghosts

## ❓ FAQ

**Q: "设备未响应" — device not responding?**
Sleeping or powered-off mice don't answer HID polls. Wiggle it. If it never wakes up, the log's "found N interfaces" line tells you whether the link is even there.

**Q: No battery while charging?**
Plugging in flips the mouse to wired mode under a different PID; the app scans all candidate interfaces for exactly this reason. Still failing? Attach the "读取失败" section of `tray.log` to an issue.

**Q: Switched DPI but the game didn't listen?**
Check the log for "已切换到 XXX DPI". Some engines cache mouse settings — restart the game and it'll stick.

## 🧪 Compatibility

| Device | Status |
|---|---|
| MCHOSE A7 Pro (PAW3395, 2.4G + wired) | ✅ Battle-tested — battery, history, DPI, the charging hand-off, all of it |
| Other MCHOSE A7 / A5 series | Same protocol family; should work out of the box. Reports welcome |

Any interface with a `5253` / `3837` VID gets a shot, so other MCHOSE models may just work.

## 🙏 Credits

- [marsuyone/mchose-battery-tray](https://github.com/marsuyone/mchose-battery-tray) — **where this project started**. The A7 battery protocol (`0x11` + `0x06`, 65-byte XOR frames) comes from their WebHID reverse-engineering of MCHOSE's official web driver; this project grew the panel, the drain log and DPI switching on top of it
- [FerrisPulse](https://github.com/Ferris-echo/FerrisPulse) — the config-channel blueprint and the A5 V2 protocol reference
- [hidapi](https://github.com/libusb/hidapi) · [pystray](https://github.com/moses-palmer/pystray) · [Pillow](https://github.com/python-pillow/Pillow)

## License

[MIT](LICENSE) © 2026
