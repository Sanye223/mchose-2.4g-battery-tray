<p align="center">
  <a href="README.md">简体中文</a> | <b>English</b> | <a href="README.ja.md">日本語</a> | <a href="README.es.md">Español</a> | <a href="README.ru.md">Русский</a>
</p>

# MCHOSE 2.4G Battery Tray

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-0078D4" alt="Windows 10/11">
  <img src="https://img.shields.io/badge/python-3.13+-3776AB" alt="Python 3.13+">
  <img src="https://img.shields.io/badge/protocol-HID%20vendor%20page%200xFF01-8A2BE2" alt="HID">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT">
  <img src="https://img.shields.io/badge/verified%20on-MCHOSE%20A7%20Pro-orange" alt="A7 Pro">
</p>

A Windows tray application that **works without the vendor suite**: it permanently displays the battery level of your MCHOSE wireless mouse in the taskbar notification area, supports switching DPI stages directly, and records every battery change. All communication goes through the vendor-defined HID channel of the official firmware — MCHOSE M HUB is not required.

<p align="center">
  <img src="docs/panel-dark.png" width="360" alt="dark panel">
  &nbsp;&nbsp;
  <img src="docs/panel-light.png" width="360" alt="light panel">
</p>

## ✨ Features

**Battery display**
- The tray icon is the battery gauge: a mouse shape that fills from the bottom, automatically inverted for light/dark taskbars, turning red below the threshold. Three other styles are also available (battery / number / ring)
- Left-click opens a Win11 Fluent-style panel: frosted-glass card, DWM rounded corners, large battery percentage, progress bar, and a charging badge
- Hover tooltip: device name · battery · current DPI · connection mode · last updated

**DPI switching**
- Six DPI stages in the right-click menu (400 / 800 / 1600 / 3200 / 6400 / 26000 by default), written to the mouse's onboard configuration in real time
- Takes effect on both the USB and 2.4G channels simultaneously; every write is read back and verified. If the stage table doesn't match, you get an explicit error instead of a silent "success"
- The active stage is determined by the connection mode: wired mode reads the USB channel, wireless mode reads the 2.4G channel

**Battery history**
- One entry for every 1% change, with second-level timestamps. While charging, polling automatically speeds up to 10 seconds; unplugging restores the original interval
- Browsable by day (with weekday headers and statistics), with one-click clearing
- Three layers of protection against dirty data: glitch filtering (reads jumping more than 10% are not trusted), the recording baseline carries over from the last recorded value (restarts don't lose track), and single changes larger than 5% are not recorded

**Other**
- Low-battery threshold (10%–40%, adjustable), autostart, refresh interval from 30 seconds to 10 minutes
- On abnormal reads, the last battery level is kept so the icon doesn't flicker grey; plugging in the cable automatically switches to the wired link for reading

<p align="center">
  <img src="docs/history-window.png" width="420" alt="battery history window">
</p>

## 📦 Get it

Download the packaged exe from [Releases](https://github.com/Sanye223/mchose-2.4g-battery-tray/releases) and double-click to run (data is stored in your user directory; the registry is not touched).

Or build from source:

```bat
git clone https://github.com/Sanye223/mchose-2.4g-battery-tray.git
cd mchose-2.4g-battery-tray

:: Python 3.13+ (tkinter required)
python -m venv tkvenv
tkvenv\Scripts\python -m pip install pyinstaller hidapi pillow
tkvenv\Scripts\python -m PyInstaller --noconfirm --clean "2.4G电量托盘.spec"
```

> `fetch_wheels.py` is a helper script: it fetches the build dependencies offline when PyPI is not directly reachable.

## 🚀 Usage

| Action | Function |
|---|---|
| **Left-click** the tray icon | Show / hide the battery panel |
| **Right-click → DPI 档位** | Switch DPI stage (the radio dot marks the current stage) |
| **Right-click → 电量记录…** | View battery changes grouped by day |
| **Right-click → 刷新间隔** | 30 s / 1 / 2 / 5 / 10 min (automatically raised to 10 s while charging) |
| **Right-click → 低电量阈值** | 10%–40%; the icon turns red below the threshold |
| **Right-click → 图标样式** | Mouse / battery / number / ring |
| **Right-click → 开机自启** | Autostart (writes the HKCU Run key, current user only) |

Command-line flags (for troubleshooting):

```bat
2.4G电量托盘.exe --cli          :: read the battery once, print it, and exit
2.4G电量托盘.exe --panel        :: open the panel right after launch (useful when the tray icon is collapsed)
2.4G电量托盘.exe --interval 10  :: temporarily override the refresh interval
```

## 🖱 DPI stage adaptation

Right-click the tray icon → **DPI 档位**: the six stages show their actual values (400–26000), the radio dot marks the current stage, and a single click writes it back to the mouse's onboard configuration:

![DPI stage menu](docs/dpi-menu.png)

The tray tooltip shows the currently active DPI in sync. Stage selection follows the connection mode: wired mode reads the USB channel, wireless mode reads the 2.4G channel. If the X / Y sensitivities differ, it displays as `800/400`:

![DPI tooltip](docs/dpi-tooltip.png)

**Switching procedure**: read the onboard configuration (with command-byte validation and all-zero echo filtering) → write it back in the A7 Pro write-frame format → wait 250 ms and read back to verify "stage applied + stage table intact" → refresh the menu and tooltip. The whole process takes about one second; if any step fails, it is logged and the original configuration is kept — the stage table is never silently corrupted.

> On the A7 Pro, the write-frame layout is **not isomorphic** to the read frame; writing the read frame back directly corrupts the whole table. This is the key difference from the FerrisPulse implementation — see [docs/PROTOCOL.md](docs/PROTOCOL.md) for details.

## 🗂 Data location

All data lives in `%APPDATA%\MchoseBattery\`:

| File | Contents |
|---|---|
| `tray.json` | Settings (interval / threshold / style / autostart) |
| `history.json` | Battery change log (up to 800 entries, rolling) |
| `tray.log` | Runtime log (failed-read forensics and DPI switch results are all here) |

## 🔌 Protocol and reverse-engineering notes

The complete frame formats are documented in the [`mchose_hid.py`](mchose_hid.py) source comments; the full reverse-engineering process and pitfalls are described in [`docs/PROTOCOL.md`](docs/PROTOCOL.md). The most important conclusions:

- The battery query payload is `0x06`; **`F4 55` is a profile-reload command** — sending it makes the mouse reload its onboard configuration and resets the DPI
- On the A7 Pro, the **DPI write frame is not isomorphic to the read frame**: echoing the read frame back with modified bytes corrupts the whole table (in testing, X became 26000/8193/16387)
- The 2.4G link occasionally delivers garbage packets (observed: 83% → 6% → 83%); both display and history need jump filtering
- Plugging in the cable switches the mouse to wired mode under a different PID, so the device enumeration must accept loose candidate conditions

## ❓ FAQ

**Q: It shows "设备未响应" (device not responding)?**
When the mouse is asleep or powered off, the firmware doesn't answer. This is normal — move the mouse and it recovers. If it stays unresponsive, the "found N interfaces" line in the log tells you whether the link is even up.

**Q: No battery reading while charging?**
Plugging in the cable switches the mouse to wired mode (different PID); the program automatically scans all candidate interfaces. If it still fails, open an issue with the "读取失败" section of `tray.log`.

**Q: Switched DPI but nothing changed in my game?**
Check the log for "已切换到 XXX DPI". Some game engines cache mouse settings — restarting the game resolves it.

## 🧪 Compatibility

| Device | Status |
|---|---|
| MCHOSE A7 Pro (PAW3395, 2.4G + wired) | ✅ Fully verified (battery / history / DPI / charging hand-off) |
| Other MCHOSE A7 / A5 series | Same protocol family; should work in theory — feedback welcome |

Any interface whose VID starts with `5253` / `3837` is tried, so more MCHOSE models may work out of the box.

## 🙏 Credits

- [marsuyone/mchose-battery-tray](https://github.com/marsuyone/mchose-battery-tray) — **the starting point of this project**. The A7 battery protocol (`0x11` + `0x06`, 65-byte XOR frames, the 65 bytes must be fully padded or the call fails with error 87) comes from its reverse-engineering of MCHOSE's official web driver (WebHID); this project built the panel, the history log, and DPI switching on top of that protocol
- [FerrisPulse](https://github.com/Ferris-echo/FerrisPulse) — reference for the config channel framework and the A5 V2 protocol
- [hidapi](https://github.com/libusb/hidapi) · [pystray](https://github.com/moses-palmer/pystray) · [Pillow](https://github.com/python-pillow/Pillow)

## License

[MIT](LICENSE) © 2026
