# MCHOSE 2.4G 电量托盘

在 Windows 任务栏通知区域显示迈从（MCHOSE）无线鼠标电量的托盘程序，支持 **DPI 档位切换**、**电量变化记录**，无需厂商套件常驻。

![深色面板](docs/panel-dark.png)
![浅色面板](docs/panel-light.png)

## 功能

- **托盘电量图标**：鼠标造型按电量涨满，深/浅色任务栏自动反色，低电量变红，四种样式可切换
- **Win11 风格面板**：左键弹出毛玻璃卡片（大号电量、进度条、充电角标、120ms 淡入）
- **DPI 档位切换**：右键菜单直接切换 6 档 DPI（实时写回鼠标板载配置，写后读回校验），悬停提示显示当前 DPI
- **电量变化记录**：每变化 1% 记录一条（精确到秒），按天分组查看；插线充电时自动切换 10 秒快轮询，拔线恢复原间隔
- **读数防抖**：垃圾包过滤（单次跳变 >10% 不采信）+ 记录基准沿用上次记录值（重启不掉档），大跨度跳变不写脏数据
- **省电**：单线程轮询（30 秒~10 分钟可调），面板懒加载

![电量记录](docs/history-window.png)

## 下载 / 构建

Releases 提供 PyInstaller 打包好的 exe；也可以自行构建：

```bat
:: 需要 Python 3.13（带 tkinter）
python -m venv tkvenv
tkvenv\Scripts\python -m pip install pyinstaller hidapi pillow
tkvenv\Scripts\python -m PyInstaller --noconfirm --clean "2.4G电量托盘.spec"
```

`fetch_wheels.py` 用于在无法直连 PyPI 的环境下离线拉取 wheel。

## 使用

| 操作 | 功能 |
|---|---|
| 左键托盘图标 | 弹出 / 收起电量面板 |
| 右键 → DPI 档位 | 切换 DPI（USB / 2.4G 通道同时生效） |
| 右键 → 电量记录… | 查看按天分组的电量变化记录 |
| 右键 → 刷新间隔 | 30 秒 ~ 10 分钟；插线充电时自动提为 10 秒 |

配置与数据保存在 `%APPDATA%\MchoseBattery\`（`tray.json` 设置、`history.json` 记录、`tray.log` 日志）。

## 兼容性

已在 **MCHOSE A7 Pro**（PAW3395）实机验证：

| 场景 | VID:PID |
|---|---|
| 2.4G 接收器 | `5253:1021` / `3837:100A` |
| 有线（含充电中） | `5253:0010` / `3837:4018` |

配置接口为 usage page `0xFF01` 的厂商自定义 HID，65 字节特征报告。

## 协议要点（逆向）

完整帧格式见 `mchose_hid.py` 源码注释，这里记录几条踩坑结论，给同类设备适配做参考：

- **电量查询**：`0x11` 报文 + 载荷 `0x06`，整帧逐字节 XOR `0xFF` 并补满 65 字节。⚠️ 载荷 `F4 55` 是 profile 重载命令，发出去会导致鼠标重载板载配置、DPI 被重置
- **DPI 配置读**：`0x12` + `0x67`，回包命令字必须是 `0x67^0xFF`，全零 payload 是主机请求回显要丢弃
- **DPI 配置写**：`0x12` + `0x40`，**写帧布局与读帧不同构**（USB/2.4G 档位为纯索引、Y 表前移到 `[18..29]`、`[17]=0xFF`）。⚠️ 直接拿读取帧改字节回写会整表错位写坏（X 变 26000/8193/16387），FerrisPulse 中 A5 V2 的 `0x57` 回写法对 A7 Pro 不适用
- **防抖**：2.4G 链路偶发垃圾包（实测 83% → 6% → 83%），显示与记录都要做跳变过滤
- 插线充电时鼠标切到有线模式（换 PID），必须放宽候选设备条件才能两栖读取

## 致谢

- [FerrisPulse](https://github.com/Ferris-echo/FerrisPulse) —— 配置通道框架与 A5 V2 协议参考
- [hidapi](https://github.com/libusb/hidapi) / [pystray](https://github.com/moses-palmer/pystray) / [Pillow](https://github.com/python-pillow/Pillow)

## License

MIT
