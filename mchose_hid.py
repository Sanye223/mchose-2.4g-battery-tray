# -*- coding: utf-8 -*-
"""MCHOSE（迈从）2.4G / 有线设备的电量读取，无 GUI 依赖。

协议（MCHOSE A7 系，VID 0x5253 / 0x3837，配置接口使用页 0xFF01，特征报告 65B）：
  1. 发特征报告 0x11：0x11 + XOR0xFF(0x06 + 0x00*19)，补零到 65 字节
  2. 睡 ~0.15s 后 get_feature_report(0x11, 65)
  3. 整包 XOR 0xFF，payload = raw[2:]：payload[9]=电量%，payload[10]=充电状态

插线充电时鼠标会切到**有线模式**（另一个 PID），无线那条链路断开但接收器
仍然在 HID 列表里、只是回垃圾包。所以候选设备要放宽到该 VID 下的所有接口，
并且用「快扫 + 深扫」两轮，避免在死设备上把时间预算耗光。
"""
from __future__ import annotations

import threading
import time

try:
    import hid
except Exception as exc:  # pragma: no cover
    hid = None
    HID_ERROR = exc
else:
    HID_ERROR = None

# 已知的 VID/PID 组合。插线后 A7 Pro 会多出一个 0x0010（有线）。
KNOWN_IDS = {
    (0x5253, 0x1021),  # MCHOSE A7 Pro（2.4G 接收器）
    (0x5253, 0x0010),  # MCHOSE A7 Pro（插线 / 有线模式）
    (0x3837, 0x100A),  # 2.4G 接收器
    (0x3837, 0x4018),  # 有线
    (0xA8A5, 0x0001),
    (0xA8A4, 0x0001),
}
KNOWN_VIDS = {0x5253, 0x3837, 0xA8A5, 0xA8A4}
CONFIG_USAGE_PAGE = 0xFF01
REPORT_LEN = 65
READY_REPORTS = (0xE2, 0x1D, 0x13)

CHARGE_TEXT = {0: "未充电", 1: "充电中", 2: "已充满"}

# 上次读成功的接口，下轮优先试它（插线 / 拔线的瞬间能少走弯路）
_LAST_PATH: bytes | None = None

# ---------------- 配置通道（DPI 档位读写，与电量同一条 65B feature 通道）
# 实机逆向（A7 Pro，2026-10-24）：
#   读 = 0x12 报文 + 命令 0x67，GetFeature(0x12) 回 63B payload：
#     [1]=USB(回报率高4位|档位低4位)  [2]=2.4G(同构)  [4..15]=X 六档 u16LE
#     [16]=档位掩码  [17]=传感器位域  [51..62]=Y 六档 u16LE
#   写 = 命令 0x40，布局与读**不同构**：
#     [1]=USB 档位、[2]=2.4G 档位（纯索引 0~5，高 4 位忽略）、[3]=保留、
#     [4..15]=X、[16]=档位掩码、[17]=0xFF、[18..29]=Y
#   ⚠️ 拿读取帧直接改字节回写会整表错位写坏（实测 X 变 26000/8193/16387），
#      FerrisPulse 仓库的 0x57 回写法是 A5 V2 的，对 A7 Pro 不适用。
CMD_CONFIG_READ = 0x67
CMD_CONFIG_WRITE = 0x40
CMD_PROFILE_SELECT = 0x58      # 0x12 长报文通道休眠时用它唤醒
RATES = (125, 500, 1000, 2000, 4000, 8000)
DPI_MIN, DPI_MAX = 100, 26000

_HID_LOCK = threading.RLock()  # 电量轮询 / 配置读写共用一条链路，串行化


def _score(info: dict) -> int:
    """给接口打分：配置接口 > 其它厂商自定义页 > 标准键盘/鼠标接口。"""
    vid = info.get("vendor_id") or 0
    pid = info.get("product_id") or 0
    up = info.get("usage_page") or 0
    s = 0
    if (vid, pid) in KNOWN_IDS:
        s += 6
    if up == CONFIG_USAGE_PAGE:
        s += 10
    elif up >= 0xFF00:
        s += 4
    elif up == 0x0001 and (info.get("usage") or 0) in (0x02, 0x06):
        s += 1
    else:
        s -= 3
    return s


def list_candidates() -> list[dict]:
    """挑出可能是迈从设备的 HID 接口，按可能性从高到低排序。"""
    if hid is None:
        return []
    try:
        infos = hid.enumerate()
    except Exception:
        return []

    out = []
    for d in infos:
        vid = d.get("vendor_id") or 0
        pid = d.get("product_id") or 0
        # 只要 VID 对得上就都算候选：插线后固件可能换 PID、也可能挂在标准 HID 页上。
        # 每个接口的快扫很便宜，宁可多试一个，也不要漏掉充电时的那条链路。
        if vid in KNOWN_VIDS or (vid, pid) in KNOWN_IDS:
            out.append(d)

    out.sort(key=lambda d: (-_score(d),
                            0 if d.get("path") == _LAST_PATH else 1))
    return out


def _xor(data: bytes) -> bytes:
    return bytes(b ^ 0xFF for b in data)


def _decode_payload(buf: bytes) -> dict | None:
    if len(buf) < 13:
        return None
    payload = buf[2:]
    if len(payload) < 11:
        return None
    percent, charge = payload[9], payload[10]
    if not 0 < percent <= 100:
        return None          # 0 / 越界 = 设备休眠或链路断开时回的垃圾包
    # 充电时固件可能回别的状态码（见过 0x45），不能因此把整包丢掉
    return {
        "percent": percent,
        "charging": charge == 1,
        "charge_code": charge,
        "status": CHARGE_TEXT.get(charge, "充电中（状态码 %d）" % charge),
        "raw": buf.hex(" ").upper(),
    }


def _decode_short(buf: bytes) -> dict | None:
    if len(buf) < 10:
        return None
    percent, charge = buf[4], buf[3]
    if not 0 < percent <= 100:
        return None
    return {
        "percent": percent,
        "charging": bool(charge),
        "charge_code": charge,
        "status": "充电中" if charge else "未充电",
        "raw": buf.hex(" ").upper(),
    }


def _frame() -> bytes:
    command = bytes([0x06] + [0x00] * 19)
    frame = bytes([0x11]) + _xor(command)
    return frame + bytes(max(0, REPORT_LEN - len(frame)))


def _probe(info: dict, tries: int, wait: float) -> dict | None:
    """打开一个接口读一次电量。读不到就快速返回 None，不在这里死等。"""
    path = info.get("path")
    if not path:
        return None
    dev = hid.device()
    try:
        dev.open_path(path)
    except Exception:
        return None

    try:
        dev.set_nonblocking(1)
        try:
            dev.send_feature_report(_frame())
        except Exception:
            pass

        time.sleep(wait)
        for _ in range(tries):
            try:
                resp = bytes(dev.get_feature_report(0x11, REPORT_LEN))
            except Exception:
                break
            if len(resp) >= 13 and any(resp):
                for cand in (_xor(resp), resp):
                    parsed = _decode_payload(cand)
                    if parsed:
                        return parsed
            time.sleep(wait * 0.6)
    except Exception:
        pass
    finally:
        try:
            dev.close()
        except Exception:
            pass

    # 有些固件把回包走中断端点，而不是特征报告
    try:
        dev = hid.device()
        dev.open_path(path)
    except Exception:
        return None
    try:
        dev.set_nonblocking(1)
        try:
            dev.send_feature_report(_frame())
        except Exception:
            pass
        deadline = time.time() + max(0.25, wait * tries * 0.7)
        while time.time() < deadline:
            try:
                report = bytes(dev.read(REPORT_LEN, 120))
            except Exception:
                break
            if not report:
                continue
            for cand in (_xor(report), report):
                if cand[0] in READY_REPORTS:
                    parsed = _decode_short(cand)
                    if parsed:
                        return parsed
        return None
    finally:
        try:
            dev.close()
        except Exception:
            pass


def describe(info: dict) -> str:
    """把接口翻译成一句人能看懂的模式说明。"""
    vid = info.get("vendor_id") or 0
    pid = info.get("product_id") or 0
    if (vid, pid) == (0x5253, 0x0010):
        return "有线（充电中）"
    if (vid, pid) == (0x5253, 0x1021):
        return "2.4G 无线"
    if (vid, pid) in ((0x3837, 0x100A),):
        return "2.4G 接收器"
    if (vid, pid) in ((0x3837, 0x4018),):
        return "有线"
    return "迈从设备"


def read_battery(attempts: int = 2, budget: float = 6.0) -> dict:
    """读一次电量。返回 ok / percent / status / charging / device / detail。

    两轮策略：先给每个候选接口一次机会（快扫），全都没读到再做深扫重试。
    插线充电时无线那条链路会回垃圾包，这样才不会把预算耗在死接口上。
    与配置读写共用一把锁，避免两条链路同时发特征报告互相干扰。
    """
    with _HID_LOCK:
        return _read_battery_impl(attempts, budget)


def _read_battery_impl(attempts: int = 2, budget: float = 6.0) -> dict:
    global _LAST_PATH

    if hid is None:
        return {"ok": False, "percent": None, "status": "不可用",
                "device": "", "detail": f"缺少 hidapi：{HID_ERROR}"}

    deadline = time.time() + max(1.5, budget)
    devices = list_candidates()
    if not devices:
        return {"ok": False, "percent": None, "status": "未连接", "device": "",
                "detail": "未找到 2.4G 接收器或鼠标"}

    def take(info, result):
        global _LAST_PATH
        _LAST_PATH = info.get("path")
        name = info.get("product_string") or "2.4G 设备"
        result.update({"ok": True, "device": name, "mode": describe(info)})
        return result

    # 第一轮：每个接口只试一次，快速排除断链的那个
    for info in devices:
        if time.time() > deadline:
            break
        r = _probe(info, tries=2, wait=0.09)
        if r:
            return take(info, r)

    # 第二轮：还有时间就深扫，覆盖设备刚唤醒 / 刚插线的情况
    for _ in range(max(1, attempts)):
        for info in devices:
            if time.time() > deadline:
                break
            r = _probe(info, tries=5, wait=0.16)
            if r:
                return take(info, r)
        if time.time() > deadline:
            break
        time.sleep(0.2)

    # 都没读到时，尽量把"现在到底看到了什么"告诉调用方
    modes = "、".join(sorted({describe(d) for d in devices})) or "未知"
    return {"ok": False, "percent": None, "status": "设备未响应",
            "device": devices[0].get("product_string") or "",
            "mode": modes,
            "detail": f"找到 {len(devices)} 个接口（{modes}），但都没回有效电量"}


def scan() -> list[dict]:
    """诊断用：列出所有候选接口及其原始回包。"""
    rows = []
    for info in list_candidates():
        row = {
            "mode": describe(info),
            "vid": f"0x{(info.get('vendor_id') or 0):04X}",
            "pid": f"0x{(info.get('product_id') or 0):04X}",
            "usage_page": f"0x{(info.get('usage_page') or 0):04X}",
            "if": info.get("interface_number"),
            "product": info.get("product_string") or "",
        }
        r = _probe(info, tries=3, wait=0.14)
        if r:
            row.update({"percent": r["percent"], "status": r["status"], "raw": r["raw"]})
        else:
            row.update({"percent": None, "status": "无有效回包", "raw": ""})
        rows.append(row)
    return rows


# ===================================================================== 配置通道
def _cfg_frame(body: bytes) -> bytes:
    """0x12 报文：reportId + XOR(body)，补齐 65 字节。body[0] 是命令字。"""
    frame = bytes([0x12]) + _xor(body)
    return frame + bytes(max(0, REPORT_LEN - len(frame)))


def _wake_long_channel(dev) -> None:
    """0x12 长报文通道休眠时，用 0x11 短报文选一下 0 号 profile 唤醒。"""
    try:
        frame = bytes([0x11]) + _xor(bytes([CMD_PROFILE_SELECT, 0x00]))
        dev.send_feature_report(frame + bytes(max(0, REPORT_LEN - len(frame))))
    except Exception:
        pass


def _parse_config(payload: bytes) -> dict | None:
    """解析 63B 配置 payload；全零（主机请求回显）或数值离谱的包直接判废。"""
    if len(payload) < 63 or not any(payload):
        return None
    xs = [payload[4 + i * 2] | (payload[5 + i * 2] << 8) for i in range(6)]
    ys = [payload[51 + i * 2] | (payload[52 + i * 2] << 8) for i in range(6)]
    for v in xs + ys:
        if v != 0 and not DPI_MIN <= v <= DPI_MAX:
            return None
    if not any(xs):
        return None
    return {
        "wired_rate": (payload[1] >> 4) & 0xF,
        "wired_stage": payload[1] & 0xF,
        "wireless_rate": (payload[2] >> 4) & 0xF,
        "wireless_stage": payload[2] & 0xF,
        "enabled": payload[16],
        "dpi_x": xs,
        "dpi_y": ys,
    }


def _pick_config_device() -> dict | None:
    infos = list_candidates()
    if not infos:
        return None
    for d in infos:                       # 优先上次读电量成功的接口
        if d.get("path") == _LAST_PATH:
            return d
    return infos[0]


def read_config(attempts: int = 3) -> dict | None:
    """读 DPI 配置。返回 None 或 {wired_stage, wireless_stage, dpi_x, dpi_y, ...}。"""
    global _LAST_PATH

    with _HID_LOCK:
        info = _pick_config_device()
        if info is None or hid is None:
            return None
        path = info.get("path")
        dev = hid.device()
        try:
            dev.open_path(path)
        except Exception:
            return None
        try:
            for attempt in range(attempts):
                try:
                    dev.send_feature_report(_cfg_frame(bytes([CMD_CONFIG_READ])))
                except Exception:
                    _wake_long_channel(dev)
                    time.sleep(0.13)
                    continue
                time.sleep(0.12 + attempt * 0.04)
                try:
                    resp = bytes(dev.get_feature_report(0x12, REPORT_LEN))
                except Exception:
                    resp = b""
                # 命令字校验：回显 / 其它报文直接重试
                if len(resp) >= 65 and resp[1] == (CMD_CONFIG_READ ^ 0xFF):
                    parsed = _parse_config(_xor(resp[2:REPORT_LEN]))
                    if parsed:
                        _LAST_PATH = path
                        return parsed
                _wake_long_channel(dev)
                time.sleep(0.13)
        finally:
            try:
                dev.close()
            except Exception:
                pass
    return None


def set_dpi_stage(stage_idx: int) -> tuple[bool, str]:
    """切 DPI 档位（0~5），USB / 2.4G 两条通道一起切。写完读回校验。"""
    idx = max(0, min(5, int(stage_idx)))
    with _HID_LOCK:
        cfg = read_config()
        if cfg is None:
            return False, "读取配置失败（设备未响应）"

        body = bytearray(64)
        body[0] = CMD_CONFIG_WRITE
        body[1] = idx                          # USB 档位（纯索引）
        body[2] = idx                          # 2.4G 档位
        # body[3] 保留
        for i, v in enumerate(cfg["dpi_x"]):
            body[4 + i * 2] = v & 0xFF
            body[5 + i * 2] = (v >> 8) & 0xFF
        body[16] = cfg["enabled"]
        body[17] = 0xFF
        for i, v in enumerate(cfg["dpi_y"]):
            body[18 + i * 2] = v & 0xFF
            body[19 + i * 2] = (v >> 8) & 0xFF

        info = _pick_config_device()
        if info is None:
            return False, "设备未连接"
        dev = hid.device()
        try:
            dev.open_path(info.get("path"))
        except Exception:
            return False, "打开设备失败"
        try:
            try:
                dev.send_feature_report(_cfg_frame(bytes(body)))
            except Exception as exc:
                return False, f"写入失败：{exc}"
        finally:
            try:
                dev.close()
            except Exception:
                pass

        time.sleep(0.25)                       # 固件落盘需要点时间
        after = read_config()
        if after is None:
            return False, "写入后读回失败，请手动确认档位"
        took = (after["wired_stage"] == idx) or (after["wireless_stage"] == idx)
        intact = after["dpi_x"] == cfg["dpi_x"] and after["dpi_y"] == cfg["dpi_y"]
        if took and intact:
            return True, f"已切换到 {cfg['dpi_x'][idx]} DPI"
        if took and not intact:
            return False, "档位已切换但 DPI 表读回不一致，请检查"
        return False, "写入未生效"
