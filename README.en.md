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

A Windows tray app that shows your MCHOSE wireless mouse's battery level right in the system tray — plus one-click DPI stage switching and a full battery drain log. **No vendor bloatware required**: it talks straight to the vendor's custom HID endpoint, so MCHOSE Center never needs to touch your machine.

> Batteries included. Literally.

<p align="center">
  <img src="docs/panel-dark.png" width="360" alt="dark panel">
  &nbsp;&nbsp;
  <img src="docs/panel-light.png" width="360" alt="light panel">
</p>

## ✨ Features

**Battery at a glance**
- Tray icon = battery gauge: a mouse shape that fills up, auto-inverts for light/dark taskbars, turns red below the low-battery threshold. Three more styles (battery / number / ring) if that's your thing
- Left-click for a Win11 Fluent flyout: frosted-glass card, DWM rounded corners, big %, progress bar, charging badge
- Hover tooltip: device · battery · **current DPI** · transport · last updated

**DPI switching**
- Six stages (400 / 800 / 1600 / 3200 / 6400 / 26000 by default) in the right-click menu, written straight to the mouse's onboard config
- Applies to both the USB and 2.4G paths; every write is read back and verified — if the stage table doesn't match, it says so instead of pretending everything is fine
- The active stage follows your connection: wired reads the USB path, wireless reads the 2.4G path

**Battery history**
- Every 1% change is logged to the second; plugging in the cable automatically bumps polling to 10 s, unplugging restores your interval
- Grouped by day with stats, one-click clear
- Three layers of anti-nonsense: glitchy reads (>10% jumps) are discarded, the baseline carries over from the last recorded value across restarts, and single entries larger than 5% never hit the log

**Housekeeping**
- Low-battery threshold (10%–40%), autostart, 30 s–10 min poll interval
- When a read fails, the last good value sticks around so the icon doesn't flash grey

<p align="center">
  <img src="docs/history-window.png" width="420" alt="battery history window">
</p>

## 📦 Getting it

Grab a prebuilt exe from [Releases](https://github.com/Sanye223/mchose-2.4g-battery-tray/releases) — everything lives in your user profile, no registry silliness.

Or roll it from source:

```bat
git clone https://github.com/Sanye223/mchose-2.4g-battery-tray.git
cd mchose-2.4g-battery-tray

:: Python 3.13+ (tkinter required)
python -m venv tkvenv
tkvenv\Scripts\python -m pip install pyinstaller hidapi pillow
tkvenv\Scripts\python -m PyInstaller --noconfirm --clean "2.4G电量托盘.spec"
```

> `fetch_wheels.py` is a helper for pulling build deps when PyPI is out of reach.

## 🚀 Usage

| Action | What it does |
|---|---|
| **Left-click** the tray icon | Toggle the flyout panel |
| **Right-click → DPI 档位** | Switch DPI stage (radio-checked at the current one) |
| **Right-click → 电量记录…** | Battery history, grouped by day |
| **Right-click → 刷新间隔** | 30 s / 1 / 2 / 5 / 10 min (10 s while charging, automatically) |
| **Right-click → 低电量阈值** | 10%–40%, icon turns red below it |
| **Right-click → 图标样式** | Mouse / battery / number / ring |
| **Right-click → 开机自启** | Autostart (HKCU Run key, current user only) |

CLI flags for debugging:

```bat
2.4G电量托盘.exe --cli          :: read the battery once, print, exit
2.4G电量托盘.exe --panel        :: open the panel on launch
2.4G电量托盘.exe --interval 10  :: override the poll interval for this run
```

## 🗂 Where your data lives

Everything is under `%APPDATA%\MchoseBattery\`:

| File | What's inside |
|---|---|
| `tray.json` | Settings (interval / threshold / style / autostart) |
| `history.json` | Battery change log (capped at 800 entries, rolling) |
| `tray.log` | Runtime log — failed-read forensics and DPI switch results land here |

## 🔌 Protocol notes

Byte-level frame formats live in the [`mchose_hid.py`](mchose_hid.py) comments; the full reverse-engineering write-up is in [`docs/PROTOCOL.md`](docs/PROTOCOL.md). The cliff notes:

- The battery query payload is `0x06`. **`F4 55` is a profile-reload command** — send it by accident and the mouse reloads its onboard config, DPI reset included
- On the A7 Pro the **DPI write frame is wired differently from the read frame**: echoing the read frame back with one byte changed scrambles the whole stage table (observed: X became 26000/8193/16387)
- The 2.4G link occasionally serves outright garbage (seen: 83% → 6% → 83%), so both display and history need jump filtering
- Plugging in the cable flips the mouse to wired mode with a different PID — device enumeration has to stay loose to survive that

## ❓ FAQ

**Q: It says "设备未响应" (device not responding)?**
Sleeping or powered-off mice don't answer HID polls — wiggle the mouse. If it never comes back, the log's "found N interfaces" line tells you whether the link is even there.

**Q: No battery while charging?**
Plugging in switches the mouse to wired mode with a different PID; the app scans all candidate interfaces automatically. If it still fails, attach the "读取失败" section of `tray.log` to an issue.

**Q: DPI changed but the game ignores it?**
Check the log for "已切换到 XXX DPI". Some engines cache mouse settings — restart the game.

## 🧪 Compatibility

| Device | Status |
|---|---|
| MCHOSE A7 Pro (PAW3395, 2.4G + wired) | ✅ Fully battle-tested (battery / history / DPI / charging switch) |
| Other MCHOSE A7 / A5 series | Same protocol family — should work, feedback welcome |

Any interface with a `5253` / `3837` VID gets a shot, so other MCHOSE models may just work.

## 🙏 Credits

- [marsuyone/mchose-battery-tray](https://github.com/marsuyone/mchose-battery-tray) — **where this project started**. The A7 battery protocol (`0x11` + `0x06`, 65-byte XOR frames) comes from their WebHID reverse-engineering of MCHOSE's official web driver; this project grew the panel, history and DPI switching on top of it
- [FerrisPulse](https://github.com/Ferris-echo/FerrisPulse) — the config-channel blueprint and the A5 V2 protocol reference
- [hidapi](https://github.com/libusb/hidapi) · [pystray](https://github.com/moses-palmer/pystray) · [Pillow](https://github.com/python-pillow/Pillow)

## License

[MIT](LICENSE) © 2026
