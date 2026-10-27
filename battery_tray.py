# -*- coding: utf-8 -*-
"""2.4G 电量托盘 —— 在任务栏通知区域显示鼠标/接收器电量。

- 图标：圆润的鼠标造型，内部按电量从底部涨满（也可切电池条 / 纯数字），
  深/浅色任务栏自动反色；只有电量低于阈值才变红
- 左键：弹出 Win11 风格小卡片（无边框圆角、大号电量、胶囊按钮）；再点一次或按 Esc 收起
- 悬停：提示里显示设备名、精确电量、充电状态、更新时间
- 右键：打开面板 / 立即刷新 / 刷新间隔 / 低电量阈值 / 图标样式 / 开机自启 / 退出
- 省电：单线程 sleep 轮询（默认 60 秒），电量没变化就不重绘图标；面板不开就不建窗口

命令行参数（排查用）：
    --cli        打印一次读数后退出
    --panel      启动后直接把面板打开（看不到托盘图标时用）
    --interval N 覆盖本次运行的刷新秒数
"""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time
import traceback

import pystray

import mchose_hid
from tray_icon import mouse_art, render as render_icon, tray_size, _bolt_poly

APP_NAME = "2.4G 电量托盘"
APP_ID = "MchoseBatteryTray"
MUTEX_NAME = "MchoseBatteryTray_SingleInstance_v1"

CFG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "MchoseBattery")
CFG_PATH = os.path.join(CFG_DIR, "tray.json")

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "MchoseBatteryTray"

INTERVALS = [(30, "30 秒"), (60, "1 分钟"), (120, "2 分钟"), (300, "5 分钟"), (600, "10 分钟")]
THRESHOLDS = [(10, "10%"), (20, "20%"), (30, "30%"), (40, "40%")]
STYLES = [("mouse", "鼠标样式"), ("battery", "电池样式"), ("number", "数字样式"), ("ring", "圆环样式")]

MAX_JUMP = 10          # 单次读数跳变超过这个百分点视为垃圾包，不采信也不显示
RECORD_MAX_DELTA = 5   # 相对「最后一次记录的电量」，5% 以内的变化才落表（大幅跳变不记）

DEFAULTS = {"interval": 60, "low": 20, "style": "mouse"}

LOG_PATH = os.path.join(CFG_DIR, "tray.log")


def log(msg: str) -> None:
    try:
        os.makedirs(CFG_DIR, exist_ok=True)
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > 200_000:
            os.replace(LOG_PATH, LOG_PATH + ".1")
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [{os.getpid()}] {msg}\n")
    except Exception:
        pass


# --------------------------------------------------------------------- 电量变化记录
HISTORY_PATH = os.path.join(CFG_DIR, "history.json")
MAX_HISTORY = 800                 # 约几百次变化，够看几个月
_hist_lock = threading.Lock()


def load_history() -> list:
    try:
        with open(HISTORY_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_history(rows: list) -> None:
    try:
        os.makedirs(CFG_DIR, exist_ok=True)
        tmp = HISTORY_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(rows[-MAX_HISTORY:], fh, ensure_ascii=False, indent=1)
        os.replace(tmp, HISTORY_PATH)
    except Exception:
        log(f"电量记录写入失败：{traceback.format_exc(limit=1)}")


# --------------------------------------------------------------------- 配置
def load_config() -> dict:
    cfg = dict(DEFAULTS)
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        if isinstance(saved, dict):
            for k in DEFAULTS:
                if k in saved:
                    cfg[k] = saved[k]
    except Exception:
        pass
    return cfg


def save_config(cfg: dict) -> None:
    try:
        os.makedirs(CFG_DIR, exist_ok=True)
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# --------------------------------------------------------------------- 开机自启
def _startup_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pyw if os.path.exists(pyw) else sys.executable
    return f'"{exe}" "{os.path.abspath(__file__)}"'


def autostart_enabled() -> bool:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, RUN_VALUE)
        return bool(value)
    except Exception:
        return False


def set_autostart(enable: bool) -> None:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, _startup_command())
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE)
                except FileNotFoundError:
                    pass
    except Exception:
        pass


# --------------------------------------------------------------------- 任务栏主题
def taskbar_is_light() -> bool:
    """浅色任务栏要用深色图标，深色任务栏用白色图标。"""
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
        return bool(value)
    except Exception:
        return False


# --------------------------------------------------------------------- 单实例
_MUTEX_HANDLE = None


def acquire_single_instance() -> bool:
    """用当前会话命名空间下的互斥量做单实例锁（不用 Global\\，普通权限建不了）。

    句柄必须留在模块级变量里，否则被 GC 掉锁就没了。
    """
    global _MUTEX_HANDLE
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        err = kernel32.GetLastError()
        if not handle:
            return True              # 建不出来就别拦着自己
        _MUTEX_HANDLE = handle
        return err != 183            # ERROR_ALREADY_EXISTS
    except Exception:
        return True


# --------------------------------------------------------------------- 固定到任务栏
def promote_tray_icon() -> None:
    """Win11 默认把新图标塞进「隐藏的图标」面板，这里把本程序的图标设为常驻显示。"""
    try:
        import winreg

        exe = os.path.normcase(os.path.abspath(sys.executable))
        base = r"Control Panel\NotifyIconSettings"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base) as root:
            for i in range(winreg.QueryInfoKey(root)[0]):
                sub = winreg.EnumKey(root, i)
                try:
                    with winreg.OpenKey(root, sub) as key:
                        path, _ = winreg.QueryValueEx(key, "ExecutablePath")
                        if os.path.normcase(os.path.abspath(path)) != exe:
                            continue
                        try:
                            if winreg.QueryValueEx(key, "IsPromoted")[0] == 1:
                                return
                        except FileNotFoundError:
                            pass
                except Exception:
                    continue
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, f"{base}\\{sub}", 0, winreg.KEY_SET_VALUE
                ) as key:
                    winreg.SetValueEx(key, "IsPromoted", 0, winreg.REG_DWORD, 1)
                return
    except Exception:
        pass


# --------------------------------------------------------------------- 小面板
class Panel:
    """左键点托盘图标弹出的 Win11 风格小卡片（亚克力 / 毛玻璃）。

    - 无边框窗口 + DWM 8px 圆角；弹出前把将要覆盖的屏幕区域截下来做高斯模糊，
      再叠一层半透明色，得到 Win11 亚克力的观感（不依赖 DWM 模糊 API，任意壁纸都稳）
    - 全部图形出自 PIL（超采样 + LANCZOS），圆角矩形按钮边缘是抗锯齿的
    - tkinter 必须在创建它的线程里跑消息循环，所以窗口单独占一条线程，
      轮询线程只往队列里丢命令，两边不共享控件。窗口懒加载，不开面板不占额外内存
    """

    W = 360
    H = 236

    def __init__(self, app: "TrayApp"):
        self.app = app
        self._queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._root = None
        self._cv = None
        self._tk = None
        self._f: dict = {}
        self._photos: dict = {}
        self._hover = ""          # "" / "close" / "refresh"
        self._refreshing = False
        self._visible = False
        self._shown_at = 0.0
        self._pos = None          # 卡片左上角（屏幕坐标）
        self._bg_photo = None     # 高斯模糊后的背景位图
        self._btn_close = (0, 0, 0, 0)
        self._btn_refresh = (0, 0, 0, 0)
        self._icon_font = None    # Segoe Fluent Icons（_build 里探测）
        self._hist_win = None     # 电量记录窗口（独立的 Toplevel，懒加载）
        self._hist_text = None
        self._hist_sum = None
        self._hist_bar = None     # 底部按钮画布
        self._hist_btns = {}      # 按钮名 → (x0, y0, x1, y1)
        self._hist_hover = ""
        self._hist_last_draw = None   # (宽度, hover) 去重，防重绘跳位

    # -------------------------------------------------- 对外接口
    def toggle(self) -> None:
        self._start()
        self._queue.put("toggle")

    def notify_update(self) -> None:
        """读数变化时调用；线程没起来就完全跳过，几乎没有开销。"""
        if self._thread is not None and self._thread.is_alive():
            self._queue.put("update")

    def show_history(self) -> None:
        """从托盘菜单打开电量记录窗口。"""
        self._start()
        self._queue.put("history")

    def close(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            return
        self._queue.put("quit")

    # -------------------------------------------------- 线程
    def _start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._main, name="panel", daemon=True)
        self._thread.start()
        if not self._ready.wait(8):
            log("面板线程启动超时")

    def _main(self) -> None:
        try:
            import tkinter as tk
            from tkinter import font as tkfont
        except Exception:
            log(f"tkinter 不可用，面板禁用：{traceback.format_exc()}")
            self._ready.set()
            return

        try:
            root = tk.Tk()
            root.withdraw()
            root.title(APP_NAME)
            root.resizable(False, False)
            root.overrideredirect(True)      # 标题栏去掉，圆角交给 DWM
            self._root = root
            self._build(tk, tkfont)
            root.bind("<Escape>", lambda _e: self._hide())
            root.bind("<FocusOut>", self._on_focus_out)
            self._apply_window_style()
        except Exception:
            log(f"面板创建失败：{traceback.format_exc()}")
            self._ready.set()
            return

        self._ready.set()
        self._pump()
        root.mainloop()

    def _apply_window_style(self) -> None:
        """Win11 的 8px 圆角 + 深色边框；无边框窗口同样有效（靠 DWM 裁切）。"""
        try:
            import ctypes

            hwnd = ctypes.windll.user32.GetParent(self._root.winfo_id()) or self._root.winfo_id()
            pref = ctypes.c_int(2)   # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref)
            )
            dark = ctypes.c_int(0 if self.app.light_taskbar else 1)
            for attr in (20, 19):    # DWMWA_USE_IMMERSIVE_DARK_MODE，旧版本号 19
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(dark), 4)
        except Exception:
            pass

    def _dpi_scale(self) -> float:
        try:
            import ctypes

            return max(1.0, ctypes.windll.user32.GetDpiForSystem() / 96.0)
        except Exception:
            return 1.0

    def _grab_backdrop(self) -> None:
        """截下卡片要盖住的那块屏幕，高斯模糊后叠一层半透明色，做出 Win11 亚克力观感。

        比 DWM 的模糊 API 稳：无边框窗口也能用，深浅主题、任意壁纸都有正确结果。
        """
        self._bg_photo = None
        if self._pos is None or self._tk is None:
            return
        try:
            import base64
            import io

            from PIL import Image, ImageFilter, ImageGrab
        except Exception:
            return

        x, y = self._pos
        s = self._dpi_scale()
        try:
            shot = ImageGrab.grab(
                bbox=(int(x * s), int(y * s), int((x + self.W) * s), int((y + self.H) * s)),
                all_screens=True,
            )
            shot = shot.convert("RGBA").resize((self.W, self.H), Image.LANCZOS)
            shot = shot.filter(ImageFilter.GaussianBlur(18))
            shot = Image.alpha_composite(shot, Image.new("RGBA", shot.size, self._colors()["tint"]))
            buf = io.BytesIO()
            shot.convert("RGB").save(buf, format="PNG")
            self._bg_photo = self._tk.PhotoImage(
                data=base64.b64encode(buf.getvalue()).decode("ascii")
            )
        except Exception:
            log(f"面板背景模糊失败：{traceback.format_exc(limit=1)}")
            self._bg_photo = None

    # -------------------------------------------------- 配色 / 字体
    def _colors(self) -> dict:
        """Win11 Fluent 配色；tint 是叠在模糊背景上的亚克力蒙层色。

        蒙层不透明度要够高（浅色 ~91%、深色 ~82%）：不然彩色壁纸会透上来把卡片
        染脏——浅色主题尤其明显，卡面会变成一片浑浊的粉褐色。
        """
        if self.app.light_taskbar:
            return {"bg": "#F3F3F3", "line": "#D5D5D5", "fg": "#1B1B1B", "sub": "#5D5D5D",
                    "track": "#D2D2D2", "accent": "#0067C0", "warn": "#C42B1C",
                    "chip": "#E8E8E8", "chip_fg": "#3B3B3B", "hover": "#DCDCDC",
                    "soft": "#DCEBF8", "soft_warn": "#FBE3E4",
                    "btn_line": "#C2C2C2", "tint": (247, 247, 247, 240)}
        return {"bg": "#202020", "line": "#4A4A4A", "fg": "#FFFFFF", "sub": "#B4B4B4",
                "track": "#4A4A4A", "accent": "#60CDFF", "warn": "#FF99A4",
                "chip": "#3A3A3A", "chip_fg": "#D8D8D8", "hover": "#4A4A4A",
                "soft": "#1D3B4D", "soft_warn": "#3B2326",
                "btn_line": "#5A5A5A", "tint": (26, 26, 26, 210)}

    def _pick(self, tkfont, names, size, weight="normal"):
        try:
            fams = set(tkfont.families(self._root))
        except Exception:
            fams = set()
        for name in names:
            if name in fams:
                return tkfont.Font(self._root, family=name, size=size, weight=weight)
        return tkfont.Font(self._root, size=size, weight=weight)

    # -------------------------------------------------- 构建
    def _build(self, tk, tkfont) -> None:
        c = self._colors()
        root = self._root
        root.configure(bg=c["bg"])
        cv = tk.Canvas(root, width=self.W, height=self.H, bg=c["bg"],
                       highlightthickness=0, bd=0, takefocus=0)
        cv.pack()
        self._cv = cv
        self._tk = tk
        self._tkfont = tkfont

        # Fluent 字阶（负数 = 像素字号）：Body Strong 14 / Caption 12 / 大数字 48
        # 中文用微软雅黑（只有常规/粗体，粗体顶替 semibold），数字走 Segoe UI Variable
        self._f["name"] = self._pick(tkfont, ("Microsoft YaHei UI", "微软雅黑", "Segoe UI"), -14, "bold")
        self._f["sub"] = self._pick(tkfont, ("Microsoft YaHei UI", "微软雅黑", "Segoe UI"), -12)
        self._f["unit"] = self._pick(tkfont, ("Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI"), -12)
        self._f["btn"] = self._pick(tkfont, ("Microsoft YaHei UI", "微软雅黑", "Segoe UI"), -12)
        self._f["chip"] = self._pick(tkfont, ("Microsoft YaHei UI", "微软雅黑", "Segoe UI"), -12)

        try:
            fams = set(tkfont.families(self._root))
        except Exception:
            fams = set()
        if "Segoe UI Variable Display Semibold" in fams:   # 规范：标题用 semibold 不用 bold
            self._f["num"] = tkfont.Font(self._root, family="Segoe UI Variable Display Semibold", size=-48)
        elif "Segoe UI Variable Display" in fams:
            self._f["num"] = tkfont.Font(self._root, family="Segoe UI Variable Display", size=-48)
        else:
            self._f["num"] = tkfont.Font(self._root, family="Segoe UI", size=-48, weight="bold")

        # Segoe Fluent Icons 图标字体（关闭 ✕ / 刷新 ⟳），没有就退化到手绘线条
        self._icon_font = None
        for fam in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
            if fam in fams:
                self._icon_font = tkfont.Font(self._root, family=fam, size=-11)
                break

        # 按钮用坐标命中：常态不画底，hover 才出底色，浮在毛玻璃上更干净
        cv.bind("<Button-1>", self._on_click)
        cv.bind("<Motion>", self._on_motion)
        cv.bind("<Leave>", lambda _e: self._set_hover(""))
        self._draw()

    # -------------------------------------------------- 圆角 / 图片工具
    def _rrect_photo(self, w, h, r, fill, outline=None):
        """生成抗锯齿的圆角矩形位图（w×h），fill/outline 可为 None。"""
        key = ("rr", w, h, r, fill, outline)
        cached = self._photos.get(key)
        if cached is not None:
            return cached
        try:
            import base64
            import io

            from PIL import Image, ImageDraw

            ss = 3
            img = Image.new("RGBA", (int(w * ss), int(h * ss)), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            inset = ss / 2.0
            d.rounded_rectangle(
                (inset, inset, w * ss - inset, h * ss - inset),
                radius=max(0.0, r * ss), fill=fill, outline=outline,
                width=ss if outline else 1,
            )
            buf = io.BytesIO()
            img.resize((int(w), int(h)), Image.LANCZOS).save(buf, format="PNG")
            photo = self._tk.PhotoImage(data=base64.b64encode(buf.getvalue()).decode("ascii"))
        except Exception:
            log(f"圆角图片生成失败：{traceback.format_exc(limit=1)}")
            return None
        self._photos[key] = photo
        return photo

    def _rrect(self, x0, y0, x1, y1, r, fill, outline=None):
        photo = self._rrect_photo(int(round(x1 - x0)), int(round(y1 - y0)), r, fill, outline)
        if photo is not None:
            self._cv.create_image(x0, y0, anchor="nw", image=photo)

    def _mode_text(self) -> str:
        mode = getattr(self.app, "mode", "") or ""
        if "有线" in mode:
            return "鼠标 · 有线" + ("（充电中）" if getattr(self.app, "charging", False) else "")
        if "2.4G" in mode:
            return "鼠标 · 2.4G 无线"
        return mode or "鼠标"

    def _mouse_photo(self, pct, color):
        key = ("mouse", pct, color)
        if key in self._photos:
            return self._photos[key]
        try:
            import base64
            import io

            img = mouse_art(30, 41, color, pct, ss=6)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            photo = self._tk.PhotoImage(data=base64.b64encode(buf.getvalue()).decode("ascii"))
        except Exception:
            log(f"面板鼠标图生成失败：{traceback.format_exc(limit=2)}")
            return None
        self._photos[key] = photo
        return photo

    def _bolt_badge_photo(self, size: int, bg_color: str, bolt_color: str):
        """充电角标：实心小圆 + 闪电（PIL 4x 超采样，边缘干净）。"""
        key = ("bolt_badge", size, bg_color, bolt_color)
        if key in self._photos:
            return self._photos[key]
        try:
            import base64
            import io

            from PIL import Image, ImageDraw

            ss = 4
            S = size * ss
            img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.ellipse((ss // 2, ss // 2, S - ss // 2, S - ss // 2),
                      fill=bg_color, outline=bg_color, width=ss)
            d.polygon(_bolt_poly(S / 2, S / 2, S * 0.52), fill=bolt_color)
            buf = io.BytesIO()
            img.resize((size, size), Image.LANCZOS).save(buf, format="PNG")
            photo = self._tk.PhotoImage(data=base64.b64encode(buf.getvalue()).decode("ascii"))
        except Exception:
            log(f"充电角标生成失败：{traceback.format_exc(limit=2)}")
            return None
        self._photos[key] = photo
        return photo

    # -------------------------------------------------- 整卡绘制
    def _draw(self) -> None:
        cv = self._cv
        if cv is None:
            return
        c = self._colors()
        app = self.app
        pct = app.percent
        low = pct is not None and pct <= int(app.cfg["low"])
        M = 16                       # 外边距，4px 网格
        R_CTRL, R_OVER = 4, 8       # Fluent 几何：控件 4px，浮层/窗口 8px

        cv.delete("all")
        cv.configure(bg=c["bg"])
        self._root.configure(bg=c["bg"])

        # 毛玻璃底 + 1px 描边（圆角与 DWM 的 8px 对齐）
        if self._bg_photo is not None:
            cv.create_image(0, 0, anchor="nw", image=self._bg_photo)
        else:
            self._rrect(0, 0, self.W, self.H, R_OVER, c["bg"])
        self._rrect(0, 0, self.W, self.H, R_OVER, None, c["line"])

        # —— 头部：设备图标（8px 背板）+ 名称（Body Strong 14）+ 模式（Caption 12）
        self._rrect(M, M, M + 48, M + 48, R_OVER, c["soft_warn"] if low else c["soft"])
        photo = self._mouse_photo(pct, c["warn"] if low else c["fg"])
        if photo is not None:
            cv.create_image(M + 9, M + 3, anchor="nw", image=photo)

        # 充电角标：图标容器右下角的小圆 + 闪电（与托盘充电状态一致）
        if getattr(app, "charging", False) and pct is not None:
            bs = 22
            photo_b = self._bolt_badge_photo(bs, c["accent"], c["bg"])
            if photo_b is not None:
                cv.create_image(M + 48 - bs // 2, M + 48 - bs // 2,
                                anchor="nw", image=photo_b)

        cv.create_text(M + 60, M + 2, text=app.device or "2.4G 设备",
                       font=self._f["name"], fill=c["fg"], anchor="nw")
        cv.create_text(M + 60, M + 27, text=self._mode_text(),
                       font=self._f["sub"], fill=c["sub"], anchor="nw")

        # —— 关闭按钮：28×28，hover 才铺 4px 圆角底，Segoe Fluent 图标
        bw = 28
        bx0, by0 = self.W - M - bw, M
        self._btn_close = (bx0, by0, bx0 + bw, by0 + bw)
        if self._hover == "close":
            self._rrect(bx0, by0, bx0 + bw, by0 + bw, R_CTRL, c["hover"])
        mx, my = bx0 + bw / 2, by0 + bw / 2
        if self._icon_font is not None:
            cv.create_text(mx, my, text="\uE711", font=self._icon_font, fill=c["fg"])
        else:
            for dx0, dy0, dx1, dy1 in ((-4, -4, 4, 4), (-4, 4, 4, -4)):
                cv.create_line(mx + dx0, my + dy0, mx + dx1, my + dy1,
                               fill=c["sub"], width=2, capstyle="round")

        # —— 电量数字（Display 48 半粗）+ 单位（Caption 12）
        text = "--" if pct is None else str(pct)
        num_y = 76
        cv.create_text(M, num_y, text=text, font=self._f["num"], anchor="nw",
                       fill=c["warn"] if low else c["fg"])
        cv.create_text(M + self._f["num"].measure(text) + 6, num_y + 40, text="%",
                       font=self._f["unit"], anchor="nw", fill=c["sub"])

        # —— 状态标签（4px 圆角，Caption 12，右对齐）
        chip = app.status or "读取中"
        cf = self._f["chip"]
        ch_h = 24
        chip_w = cf.measure(chip) + 24
        cx1, cy0 = self.W - M, 98
        cx0 = cx1 - chip_w
        bg = c["chip"] if pct is None else (c["soft_warn"] if low else c["soft"])
        fg = c["sub"] if pct is None else (c["warn"] if low else c["accent"])
        self._rrect(cx0, cy0, cx1, cy0 + ch_h, R_CTRL, bg)
        cv.create_text((cx0 + cx1) / 2, cy0 + ch_h / 2, text=chip, font=cf, fill=fg)

        # —— 进度条（条状元素：4px 高，微软进度条同款细条）
        bx0, bx1 = M, self.W - M
        by0, bh = 158, 4
        self._rrect(bx0, by0, bx1, by0 + bh, bh / 2, c["track"])
        if pct:
            fill_w = max(bh, (bx1 - bx0) * pct / 100.0)
            self._rrect(bx0, by0, bx0 + fill_w, by0 + bh, bh / 2,
                        c["warn"] if low else c["accent"])

        # —— 底部：Caption 时间（+ 最近一次掉电时间）+ 次级按钮
        foot = f"更新于 {app.updated}" if app.updated else ""
        drop = getattr(app, "last_drop", None)
        if drop:
            extra = f" · 掉电 {drop['t'][11:]}"
            if self._f["sub"].measure(foot + extra) < 200:   # 别压到刷新按钮
                foot += extra
        cv.create_text(M, 194, anchor="nw", fill=c["sub"], font=self._f["sub"], text=foot)

        bw2, bh2 = 112, 32
        rx1 = self.W - M
        rx0, ry0 = rx1 - bw2, 188
        self._btn_refresh = (rx0, ry0, rx1, ry0 + bh2)
        if self._hover == "refresh":
            self._rrect(rx0, ry0, rx1, ry0 + bh2, R_CTRL, c["hover"])
        else:
            self._rrect(rx0, ry0, rx1, ry0 + bh2, R_CTRL, None, c["btn_line"])
        label = "刷新中…" if self._refreshing else "立即刷新"
        cy = ry0 + bh2 / 2
        if self._icon_font is not None:
            cv.create_text(rx0 + 18, cy, text="\uE72C", font=self._icon_font,
                           fill=c["fg"])
            cv.create_text((rx0 + 30 + rx1) / 2, cy, text=label,
                           font=self._f["btn"], fill=c["fg"])
        else:
            cv.create_text((rx0 + rx1) / 2, cy, text=label,
                           font=self._f["btn"], fill=c["fg"])

    # -------------------------------------------------- 交互
    def _hit(self, x: int, y: int) -> str:
        for tag, box in (("close", self._btn_close), ("refresh", self._btn_refresh)):
            x0, y0, x1, y1 = box
            if x0 <= x <= x1 and y0 <= y <= y1:
                return tag
        return ""

    def _on_motion(self, event) -> None:
        self._set_hover(self._hit(event.x, event.y))

    def _on_click(self, event) -> None:
        tag = self._hit(event.x, event.y)
        if tag == "close":
            self._hide()
        elif tag == "refresh":
            self._on_refresh()

    def _set_hover(self, tag: str) -> None:
        if tag == self._hover:
            return
        self._hover = tag
        if self._visible:
            self._draw()

    def _refresh_view(self) -> None:
        if self._root is not None:
            self._draw()

    # -------------------------------------------------- 电量记录窗口
    def _open_history(self) -> None:
        """电量变化记录：原生窗口 + 按天分组的可滚动卡片列表（复用面板的 tk 线程）。"""
        tk = self._tk
        if tk is None:
            return
        c = self._colors()
        try:
            if self._hist_win is not None and self._hist_win.winfo_exists():
                self._fill_history()
                self._hist_win.deiconify()
                self._hist_win.lift()
                self._hist_win.focus_force()
                return
        except Exception:
            self._hist_win = None

        # Fluent 排版：标题 Title 20px semibold；记录卡片比底色浮起一层（layering）
        card = "#2A2A2A" if not self.app.light_taskbar else "#FAFAFA"
        if "title" not in self._f:
            try:
                fams = set(self._tkfont.families(self._root))
            except Exception:
                fams = set()
            if "Segoe UI Variable Display Semibold" in fams:
                self._f["title"] = self._tkfont.Font(
                    self._root, family="Segoe UI Variable Display Semibold", size=-20)
            else:
                self._f["title"] = self._pick(
                    self._tkfont, ("Microsoft YaHei UI", "微软雅黑", "Segoe UI"), -20, "bold")

        try:
            import base64
            import ctypes
            import io

            top = tk.Toplevel(self._root)
            who = self.app.device or "2.4G 设备"
            top.title(f"电量记录 · {who}")
            top.configure(bg=c["bg"])
            sw, sh = top.winfo_screenwidth(), top.winfo_screenheight()
            top.geometry(f"460x540+{(sw - 460) // 2}+{max(40, (sh - 540) // 2 - 60)}")
            top.minsize(380, 360)

            # 窗口图标：用当前托盘图标实时渲染一张，替代 tkinter 默认羽毛
            try:
                img = render_icon(self.app.percent, self.app.cfg.get("style", "mouse"),
                                  self.app.light_taskbar, int(self.app.cfg.get("low", 20)),
                                  size=32)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                self._hist_icon_photo = tk.PhotoImage(
                    data=base64.b64encode(buf.getvalue()).decode("ascii"))
                top.iconphoto(True, self._hist_icon_photo)
            except Exception:
                pass

            hwnd = ctypes.windll.user32.GetParent(top.winfo_id()) or top.winfo_id()

            def _paint_frame():
                """映射后再刷一次：Toplevel 刚建时 hwnd 还没准备好，标题栏会漏成白底。"""
                try:
                    h = ctypes.windll.user32.GetParent(top.winfo_id()) or hwnd
                    pref = ctypes.c_int(2)                 # DWMWCP_ROUND
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(h, 33, ctypes.byref(pref), 4)
                    dark = ctypes.c_int(0 if self.app.light_taskbar else 1)
                    for attr in (20, 19):
                        ctypes.windll.dwmapi.DwmSetWindowAttribute(h, attr, ctypes.byref(dark), 4)
                except Exception:
                    pass

            _paint_frame()
            top.after(60, _paint_frame)
            top.after(200, _paint_frame)

            # —— 头部：Title 20 + Caption 12 摘要
            head = tk.Frame(top, bg=c["bg"])
            head.pack(fill="x", padx=16, pady=(16, 8))
            tk.Label(head, text="电量变化记录", bg=c["bg"], fg=c["fg"],
                     font=self._f["title"], anchor="w").pack(anchor="w")
            self._hist_sum = tk.Label(head, text="", bg=c["bg"], fg=c["sub"],
                                      font=self._f["sub"], anchor="w", justify="left")
            self._hist_sum.pack(anchor="w", pady=(4, 0))

            # —— 列表卡片：浮起一层（配色分层）+ 1px 描边，滚动条内嵌右缘
            body = tk.Frame(top, bg=c["bg"])
            body.pack(fill="both", expand=True, padx=16, pady=(8, 0))
            card_bg = "#2A2A2A" if not self.app.light_taskbar else "#FAFAFA"
            card = tk.Frame(body, bg=card_bg, highlightthickness=1,
                            highlightbackground=c["btn_line"], highlightcolor=c["btn_line"])
            card.pack(fill="both", expand=True)
            txt = tk.Text(card, bg=card_bg, fg=c["fg"], bd=0, highlightthickness=0,
                          padx=12, pady=10, wrap="none", cursor="arrow",
                          width=1, height=1,      # 小请求尺寸，靠 pack 扩展；否则会把底部按钮挤成 1px
                          font=self._f["sub"], spacing1=1, spacing3=4)
            sb = tk.Scrollbar(card, command=txt.yview, width=10,
                              bg=c["chip"], troughcolor=card_bg,
                              activebackground=c["hover"], bd=0,
                              activerelief="flat", elementborderwidth=0)
            txt.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            txt.pack(side="left", fill="both", expand=True)
            txt.tag_configure("day", foreground=c["accent"], font=self._f["name"],
                              spacing1=14, spacing3=8)
            # 分列着色：时间灰、掉电行主文字色、充电行淡化；闪电用 Fluent 图标字体
            for name, kw in (
                ("hm", {"foreground": c["sub"]}),
                ("v_up", {"foreground": c["sub"]}),
                ("v_down", {"foreground": c["fg"]}),
                ("d_up", {"foreground": c["accent"]}),
                ("d_down", {"foreground": c["fg"]}),
                ("k_up", {"foreground": c["accent"]}),
                ("k_down", {"foreground": c["sub"]}),
                ("mode", {"foreground": c["sub"]}),
                ("bolt", {"foreground": c["accent"]}),
                ("bolt_c", {"foreground": c["accent"], "justify": "center"}),
                ("empty", {"foreground": c["sub"], "justify": "center"}),
            ):
                kw.setdefault("spacing3", 5)
                if name == "bolt" and self._icon_font is not None:
                    kw["font"] = self._icon_font
                txt.tag_configure(name, **kw)
            self._hist_text = txt

            # —— 底部按钮：Canvas 自绘 4px 圆角 + Fluent 图标（Win11 次级按钮）
            bar = tk.Canvas(top, height=56, bg=c["bg"], highlightthickness=0, bd=0)
            bar.pack(fill="x", side="bottom")
            self._hist_bar = bar
            self._hist_btns = {}
            self._hist_hover = ""
            bar.bind("<Motion>", self._hist_on_motion)
            bar.bind("<Leave>", lambda _e: self._hist_set_hover(""))
            bar.bind("<Button-1>", self._hist_on_click)
            bar.bind("<Configure>", lambda _e: self._draw_hist_btns())   # 尺寸就绪/变化后按真实宽度重画
            self._draw_hist_btns()

            self._hist_win = top
            self._fill_history()
            # Fluent 动效：约 120ms 淡入
            try:
                top.attributes("-alpha", 0.0)
                for i in range(1, 7):
                    top.after(i * 20, lambda v=round(i / 6, 2):
                              top.attributes("-alpha", v))
            except Exception:
                pass
            # 从托盘菜单打开时前台是 explorer，先顶一下再把焦点拿过来
            try:
                top.attributes("-topmost", True)
                top.after(1200, lambda: top.attributes("-topmost", False))
                top.lift()
                top.focus_force()
            except Exception:
                pass
        except Exception:
            log(f"电量记录窗口创建失败：{traceback.format_exc()}")
            self._hist_win = None

    # -- 记录窗口底部按钮（Canvas 自绘 4px 圆角，复用面板的超采样管线）
    def _draw_hist_btns(self) -> None:
        bar = self._hist_bar
        if bar is None:
            return
        c = self._colors()
        w = bar.winfo_width()
        if w < 100:
            w = 428            # 窗口未映射完拿不到真实宽度；<Configure> 后会按实际宽度重画
        key = (w, self._hist_hover)
        if key == self._hist_last_draw:   # 宽度和 hover 都没变就别重画，防点击后跳位
            return
        self._hist_last_draw = key
        bar.delete("all")
        h = 56
        bar.configure(height=h)
        bw, bh = 112, 32
        y0 = (h - bh) // 2
        mx = 16                       # 距窗口边缘 16px，别贴边
        # 关闭靠右，清空靠左（次级按钮：hover 才铺底色）
        boxes = {
            "clear": (mx, y0, mx + bw, y0 + bh),
            "close": (w - mx - bw, y0, w - mx, y0 + bh),
        }
        self._hist_btns = boxes
        for name, (x0, yy0, x1, yy1) in boxes.items():
            hovered = self._hist_hover == name
            fill = c["hover"] if hovered else None
            photo = self._rrect_photo(x1 - x0, yy1 - yy0, 4, fill, c["btn_line"])
            if photo is not None:
                bar.create_image(x0, yy0, anchor="nw", image=photo)
            mx, my = (x0 + x1) / 2, (yy0 + yy1) / 2
            label = "清空记录" if name == "clear" else "关闭"
            if self._icon_font is not None:
                glyph = "\uE74D" if name == "clear" else "\uE711"
                off = 14 if name == "clear" else 10
                bar.create_text(x0 + off, my, text=glyph,
                                font=self._icon_font, fill=c["fg"])
                bar.create_text((x0 + off + 8 + x1) / 2, my, text=label,
                                font=self._f["btn"], fill=c["fg"])
            else:
                bar.create_text(mx, my, text=label, font=self._f["btn"], fill=c["fg"])

    def _hist_hit(self, x: int, y: int) -> str:
        for name, (x0, y0, x1, y1) in self._hist_btns.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return name
        return ""

    def _hist_set_hover(self, name: str) -> None:
        if name == self._hist_hover:
            return
        self._hist_hover = name
        self._draw_hist_btns()

    def _hist_on_motion(self, event) -> None:
        self._hist_set_hover(self._hist_hit(event.x, event.y))

    def _hist_on_click(self, event) -> None:
        name = self._hist_hit(event.x, event.y)
        if name == "clear":
            self._clear_history()
        elif name == "close":
            self._close_history()

    def _fill_history(self) -> None:
        txt = self._hist_text
        if txt is None:
            return
        rows = list(getattr(self.app, "history", []))[::-1]
        drops = sum(1 for h in rows if h.get("to", 0) < h.get("from", 0))
        last = getattr(self.app, "last_drop", None)
        summary = f"共 {len(rows)} 条变化 · 掉电 {drops} 次 · 充电 {len(rows) - drops} 次"
        if last:
            summary += f"\n最近掉电 {last['t'][5:]}（{last['from']}% → {last['to']}%）"
        try:
            self._hist_sum.config(text=summary)
        except Exception:
            pass

        txt.configure(state="normal")
        txt.delete("1.0", "end")
        if not rows:
            txt.insert("end", "\n\n\n")
            if self._icon_font is not None:
                txt.insert("end", "\uE81C\n", "bolt_c")  # 历史时钟图标，别用闪电（会误读成充电中）
            txt.insert("end", "还没有记录\n\n", "empty")
            txt.insert("end", "电量每变化 1% 就会记一条（掉电、充电都记），\n插线充电时每 10 秒检查一次，掉电时间精确到秒。\n", "empty")
        else:
            day = ""
            weekdays = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
            for h in rows:
                stamp = h.get("t", "")
                d, _, hm = stamp.partition(" ")
                if d != day:
                    day = d
                    wd = ""
                    try:
                        from datetime import datetime as _dt

                        wd = "  " + weekdays[_dt.strptime(d, "%Y-%m-%d").weekday()]
                    except Exception:
                        pass
                    txt.insert("end", f"{d}{wd}\n", "day")
                delta = h.get("to", 0) - h.get("from", 0)
                charging = bool(h.get("charging"))
                up = delta > 0
                txt.insert("end", f"{hm}  ", "hm")
                if charging and self._icon_font is not None:   # 只有真充电才画闪电
                    txt.insert("end", "\uE945 ", "bolt")
                txt.insert("end", f"{h.get('from'):>3}% → {h.get('to'):<3}%",
                           "v_up" if up else "v_down")
                txt.insert("end", f"  {delta:+d}%  ", "d_up" if up else "d_down")
                kind = "掉电" if delta < 0 else ("充电" if charging else "回升")
                txt.insert("end", kind, "k_up" if up else "k_down")
                mode = h.get("mode", "")
                txt.insert("end", (f"    {mode}\n" if mode else "\n"), "mode")
        txt.configure(state="disabled")
        txt.see("1.0")

    def _clear_history(self) -> None:
        try:
            from tkinter import messagebox

            if not messagebox.askyesno("电量记录", "清空全部电量变化记录？",
                                       parent=self._hist_win):
                return
        except Exception:
            pass
        with _hist_lock:
            self.app.history.clear()
            self.app.last_drop = None
            save_history([])
        self._fill_history()
        if self._visible:
            self._draw()

    def _close_history(self) -> None:
        try:
            if self._hist_win is not None:
                self._hist_win.destroy()
        except Exception:
            pass
        self._hist_win = None
        self._hist_text = None
        self._hist_bar = None
        self._hist_btns = {}
        self._hist_hover = ""
        self._hist_last_draw = None

    # -------------------------------------------------- 显隐
    def _place(self) -> None:
        try:
            import ctypes
            from ctypes import wintypes

            rect = wintypes.RECT()
            ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)  # 工作区
            right, bottom = rect.right, rect.bottom
        except Exception:
            right, bottom = self._root.winfo_screenwidth(), self._root.winfo_screenheight()
        w = self._root.winfo_reqwidth()
        h = self._root.winfo_reqheight()
        self._pos = (right - w - 14, bottom - h - 14)
        self._root.geometry(f"{w}x{h}+{self._pos[0]}+{self._pos[1]}")

    def _show(self) -> None:
        self._place()
        self._grab_backdrop()
        self._draw()
        self._apply_window_style()
        if time.time() - self.app.last_ok > 10:   # 数据旧了就先刷一次，别让人干等一分钟
            self.app.refresh()
        self._root.deiconify()
        self._root.lift()
        # Fluent 动效：约 120ms 淡入，快速、直接、不抢戏
        try:
            self._root.attributes("-alpha", 0.0)
            for i in range(1, 7):
                self._root.after(i * 20, lambda v=round(i / 6, 2):
                                 self._root.attributes("-alpha", v))
        except Exception:
            pass
        # 先顶一下再放开：从托盘这类前台不是自己的场景弹出，不顶会被前台窗口压住
        try:
            self._root.attributes("-topmost", True)
            self._root.after(1400, lambda: self._root.attributes("-topmost", False))
        except Exception:
            pass
        try:
            import ctypes

            user32 = ctypes.windll.user32
            hwnd = user32.GetParent(self._root.winfo_id()) or self._root.winfo_id()
            # 点击托盘图标时前台是 explorer，不放松限制的话 SetForegroundWindow 会被系统拒绝，
            # 面板会立刻被判成"失焦"而闪一下就消失。
            user32.AllowSetForegroundWindow(ctypes.c_uint(-1).value)   # ASFW_ANY
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
        except Exception:
            pass
        self._root.focus_force()
        self._shown_at = time.time()
        self._visible = True
        self._root.after(120, self._apply_window_style)   # 显示后再刷一次，防止圆角没跟上

    def _hide(self) -> None:
        self._visible = False
        self._hover = ""
        if self._root is not None:
            self._root.withdraw()

    def _on_focus_out(self, _event=None) -> None:
        if self._root is not None and self._visible:
            self._root.after(220, self._hide_if_inactive)

    def _hide_if_inactive(self) -> None:
        if self._root is None or not self._visible:
            return
        if time.time() - self._shown_at < 0.8:
            # 刚弹出来的头一秒，前台切换还没稳定，别急着收
            self._root.after(250, self._hide_if_inactive)
            return
        try:
            import ctypes

            hwnd = self._root.winfo_id()
            parent = ctypes.windll.user32.GetParent(hwnd)
            if ctypes.windll.user32.GetForegroundWindow() not in (hwnd, parent):
                self._hide()
        except Exception:
            pass

    # -------------------------------------------------- 按钮
    def _on_refresh(self) -> None:
        self._refreshing = True
        self._draw()
        self.app.refresh()
        if self._root is not None:
            self._root.after(1400, self._refresh_done)

    def _refresh_done(self) -> None:
        self._refreshing = False
        if self._visible:
            self._draw()

    # -------------------------------------------------- 命令泵
    def _pump(self) -> None:
        try:
            while True:
                cmd = self._queue.get_nowait()
                if cmd == "toggle":
                    self._hide() if self._visible else self._show()
                elif cmd == "update" and self._visible:
                    self._refresh_view()
                elif cmd == "history":
                    self._open_history()
                elif cmd == "quit":
                    self._root.quit()
                    return
        except queue.Empty:
            pass
        except Exception:
            log(f"面板命令处理异常：{traceback.format_exc()}")
        self._root.after(150, self._pump)

# --------------------------------------------------------------------- 托盘应用
class TrayApp:
    def __init__(self, interval_override: int | None = None, open_panel: bool = False):
        self.cfg = load_config()
        if interval_override:
            self.cfg["interval"] = interval_override

        self.icon: pystray.Icon | None = None
        self.open_panel = open_panel
        self.wake = threading.Event()
        self.stopped = threading.Event()

        self.percent: int | None = None
        self.charging = False
        self.device = ""
        self.mode = "2.4G 无线"
        self.status = "读取中"
        self.updated = ""
        self.last_ok = 0.0
        self._just_failed = False
        self.light_taskbar = taskbar_is_light()
        self._last_paint = None
        self._last_header = ""
        self.history = load_history()          # 电量变化记录（JSON）
        # 旧版本没有跳变过滤，混进过 83%→6% 这种垃圾包记录，启动时顺手清掉
        pruned = [h for h in self.history
                  if abs(h.get("to", 0) - h.get("from", 0)) <= MAX_JUMP]
        if len(pruned) != len(self.history):
            log(f"清理历史异常条目 {len(self.history) - len(pruned)} 条")
            self.history = pruned
            save_history(pruned)
        self.last_drop = next(
            (h for h in reversed(self.history) if h.get("to", 0) < h.get("from", 0)), None
        )
        self._pending_pct = None               # 疑似跳变读数（连续两次一致才承认）
        self._pending_hits = 0
        # 记录基准 = 最后一次记录的电量（重启后也接着上次的记录往下走，不丢数据）
        self._last_rec_pct = self.history[-1]["to"] if self.history else None
        self._big_pct = None                   # 大跨度变化的候选值（确认后静默更新基准）
        self._big_hits = 0
        self.dpi_cfg = None                    # DPI 配置缓存（mchose_hid.read_config）
        self._dpi_checked_at = 0.0             # 上次读配置的时间，节流用
        self.panel = Panel(self)

    # -------------------------------------------------- 变化记录
    def _record_change(self, old: int, new: int) -> None:
        """电量每变化 1%（或更多）记一条：时间（精确到秒）、前后值、当时的连接方式。"""
        entry = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "from": old, "to": new,
                 "mode": self.mode, "charging": bool(self.charging)}
        with _hist_lock:
            self.history.append(entry)
            if len(self.history) > MAX_HISTORY:
                del self.history[:-MAX_HISTORY]
            save_history(self.history)
        self._last_rec_pct = new
        if new < old:
            self.last_drop = entry
        log(f"电量变化 {old}% → {new}%（{self.mode}）")

    # -------------------------------------------------- 状态文案
    def _tooltip(self) -> str:
        if self.percent is None:
            return f"{APP_NAME} · {self.status}"
        who = self.device or "2.4G 设备"
        # mode 文案（如「有线（充电中）」）可能已含充电状态，避免重复
        flag = "，充电中" if self.charging and "充电" not in self.mode else ""
        # 当前 DPI：有线模式看 USB 通道，无线看 2.4G 通道；XY 不同时都显示
        dpi = ""
        cfg = self.dpi_cfg
        if cfg:
            stage = cfg["wired_stage"] if "有线" in (self.mode or "") else cfg["wireless_stage"]
            if 0 <= stage < 6:
                vx, vy = cfg["dpi_x"][stage], cfg["dpi_y"][stage]
                if vx:
                    dpi = f" · DPI {vx}/{vy}" if vy and vy != vx else f" · DPI {vx}"
        return f"{who} · 电量 {self.percent}%{flag}{dpi} · {self.mode} · {self.updated}"

    def _header(self) -> str:
        if self.percent is None:
            return self.status
        return f"{self.device or '2.4G 设备'} · {self.percent}% · {self.mode}"

    # -------------------------------------------------- 图标
    def _paint(self, force: bool = False) -> None:
        size = tray_size()
        key = (self.percent, self.cfg["style"], self.light_taskbar, self.cfg["low"],
               size, self.charging)
        if not force and key == self._last_paint:
            return
        self._last_paint = key
        image = render_icon(
            self.percent, self.cfg["style"], self.light_taskbar, self.cfg["low"],
            size=size, charging=self.charging
        )
        if self.icon is not None:
            self.icon.icon = image
            self.icon.title = self._tooltip()

    # -------------------------------------------------- 轮询
    def _poll_once(self) -> None:
        try:
            result = mchose_hid.read_battery()
        except Exception:
            result = {"ok": False, "percent": None, "status": "读取异常",
                      "detail": traceback.format_exc(limit=1)}

        before = (self.percent, self.charging, self.device, self.mode)
        now = time.time()
        if result.get("ok") and result.get("percent") is not None:
            new_pct = int(result["percent"])
            # 单次跳变超阈值 = 垃圾包（实测见过 83% → 6% → 83% 的假读数）。
            # 第一次看到先丢弃、保留原读数；连续两次读到同一个值才承认（真校准跳变）。
            plausible = before[0] is None or abs(new_pct - before[0]) <= MAX_JUMP
            confirmed_jump = False
            if not plausible:
                if self._pending_pct == new_pct:
                    self._pending_hits += 1
                else:
                    self._pending_pct, self._pending_hits = new_pct, 1
                plausible = self._pending_hits >= 2
                confirmed_jump = plausible          # 连续两次一致：这是真实读数，不是垃圾包
                if not plausible:
                    log(f"忽略可疑读数 {new_pct}%（上次 {before[0]}%，跳变 {abs(new_pct - before[0])}%）")
            if plausible:
                self._pending_pct, self._pending_hits = None, 0
                self.percent = new_pct
                self.charging = bool(result.get("charging"))
                self.device = result.get("device") or ""
                self.mode = result.get("mode") or self.mode
                self.status = result.get("status") or "正常"
                self.updated = time.strftime("%H:%M")
                self.last_ok = now
                self._just_failed = False
                # 记录：基准是「最后一次记录的电量」，只有 5% 以内的变化才落表。
                # 这样重启后第一次读数也能补记掉电，而大跨度跳变（休眠/垃圾包）不会写脏数据。
                base = self._last_rec_pct
                if base is None:
                    self._last_rec_pct = new_pct
                elif new_pct != base:
                    if abs(new_pct - base) <= RECORD_MAX_DELTA:
                        self._record_change(base, new_pct)
                        self._big_pct, self._big_hits = None, 0
                    elif confirmed_jump:
                        # 已连续两次确认的大跨度：不落表，直接静默把基准挪过去
                        log(f"电量基准静默更新 {base}% → {new_pct}%"
                            f"（跨度 {abs(new_pct - base)}%，超过 {RECORD_MAX_DELTA}%，不记录）")
                        self._last_rec_pct = new_pct
                        self._big_pct, self._big_hits = None, 0
                    else:
                        # 大跨度：连续两次读到同一值才静默把基准挪过去（不落表）
                        if self._big_pct == new_pct:
                            self._big_hits += 1
                        else:
                            self._big_pct, self._big_hits = new_pct, 1
                        if self._big_hits >= 2:
                            log(f"电量基准静默更新 {base}% → {new_pct}%"
                                f"（跨度 {abs(new_pct - base)}%，超过 {RECORD_MAX_DELTA}%，不记录）")
                            self._last_rec_pct = new_pct
                            self._big_pct, self._big_hits = None, 0
                if self.charging != before[1]:
                    if self.charging:
                        log("插线充电：轮询间隔临时调整为 10 秒")
                    else:
                        log(f"已拔线：恢复轮询间隔 {int(self.cfg['interval'])} 秒")
            else:
                # 读数不可信：保留上次电量，只更新时间
                self.status = "读数异常，显示上次电量"
                self.updated = time.strftime("%H:%M")
                self.last_ok = now
                self._just_failed = False
        elif self.percent is not None and now - self.last_ok < 300:
            # 偶发读不到（设备刚唤醒/正忙）时保留上次读数，图标不要闪成灰色
            self.status = "暂未响应，显示上次读数"
        else:
            self.percent = None
            self.charging = False
            self.status = result.get("status") or "未连接"
            self.updated = time.strftime("%H:%M")

        # 读不到时把现场写进日志，插线充电排查全靠这条
        if not result.get("ok"):
            self._just_failed = True
            reason = result.get("detail") or result.get("status") or ""
            if reason != getattr(self, "_last_fail", ""):
                self._last_fail = reason
                log(f"读取失败：{reason}")

        # 每 30 秒刷一次 DPI 配置缓存（菜单要显示档位表），失败不影响电量主流程
        now2 = time.time()
        if result.get("ok") and now2 - self._dpi_checked_at > 30:
            self._dpi_checked_at = now2
            try:
                cfg = mchose_hid.read_config()
                if cfg and cfg != self.dpi_cfg:
                    self.dpi_cfg = cfg
                    if self.icon is not None:
                        self.icon.update_menu()
            except Exception:
                log(f"DPI 配置读取失败：{traceback.format_exc(limit=1)}")

        self.light_taskbar = taskbar_is_light()
        changed = before != (self.percent, self.charging, self.device, self.mode)
        self._paint(force=changed)
        if self.icon is not None:
            self.icon.title = self._tooltip()
            head = self._header()
            if head != self._last_header:      # 原生菜单文本是构建时快照，有变化才重建
                self._last_header = head
                self.icon.update_menu()
        self.panel.notify_update()

    def _loop(self) -> None:
        self._poll_once()
        log(f"首次轮询完成 percent={self.percent} status={self.status}")
        promote_tray_icon()
        log("托盘图标固定检查完成")
        while not self.stopped.is_set():
            # 插线充电时把检查频率提到 10 秒（电量记录更精确），拔线恢复用户设置的间隔
            if self.charging:
                wait_s = 10
            else:
                wait_s = max(10, int(self.cfg["interval"]))
            if self.percent is None or self._just_failed:
                wait_s = min(wait_s, 6 if self._just_failed else 15)
            self.wake.wait(timeout=wait_s)
            self.wake.clear()
            if self.stopped.is_set():
                break
            self._poll_once()
            log(f"轮询 percent={self.percent} status={self.status} icon={self.icon is not None}")

    # -------------------------------------------------- DPI 档位
    def _dpi_stage(self) -> int:
        """当前生效的档位索引：有线模式看 USB 通道，无线看 2.4G 通道。"""
        cfg = self.dpi_cfg
        if not cfg:
            return -1
        if "有线" in (self.mode or ""):
            return cfg["wired_stage"]
        return cfg["wireless_stage"]

    def _dpi_label(self, k: int) -> str:
        cfg = self.dpi_cfg
        if cfg and cfg["dpi_x"][k]:
            return f"{cfg['dpi_x'][k]} DPI"
        return f"档位 {k + 1}"

    def set_dpi_stage(self, k: int, *_args) -> None:
        """切换 DPI 档位（后台线程，写+校验约 1 秒），完成后刷新缓存和菜单。"""
        def work():
            try:
                ok, msg = mchose_hid.set_dpi_stage(k)
                log(f"切换 DPI 档位 {k}：{msg}")
                if ok:
                    cfg = mchose_hid.read_config()
                    if cfg:
                        self.dpi_cfg = cfg
                    self.refresh()
                    if self.icon is not None:
                        self.icon.update_menu()
            except Exception:
                log(f"切换 DPI 档位异常：{traceback.format_exc()}")
        threading.Thread(target=work, daemon=True, name="dpi-set").start()

    # -------------------------------------------------- 菜单动作
    def diagnose(self, *_):
        """把每个候选接口的原始回包写进 diag.txt 并打开，插线排查用。"""
        def work():
            try:
                rows = mchose_hid.scan()
                lines = [
                    f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
                    "（插着充电线时跑这个最有参考价值）",
                    "",
                ]
                for r in rows:
                    lines.append(
                        f"{r['mode']:12s} VID {r['vid']} PID {r['pid']} "
                        f"页 {r['usage_page']} 接口 {r['if']}"
                    )
                    lines.append(f"    电量 {r['percent']}  状态 {r['status']}")
                    if r["raw"]:
                        lines.append(f"    原始 {r['raw']}")
                    lines.append("")
                if not rows:
                    lines.append("没有发现任何迈从设备接口。")
                path = os.path.join(CFG_DIR, "diag.txt")
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                log(f"诊断结果已写入 {path}")
                os.startfile(path)
            except Exception:
                log(f"诊断失败：{traceback.format_exc(limit=2)}")

        threading.Thread(target=work, daemon=True).start()

    def refresh(self, *_):
        self.wake.set()

    def set_interval(self, seconds: int):
        def handler(*_):
            self.cfg["interval"] = seconds
            save_config(self.cfg)
            self.icon.update_menu()
            self.wake.set()

        return handler

    def set_threshold(self, value: int):
        def handler(*_):
            self.cfg["low"] = value
            save_config(self.cfg)
            self._paint(force=True)
            self.icon.update_menu()

        return handler

    def set_style(self, style: str):
        def handler(*_):
            self.cfg["style"] = style
            save_config(self.cfg)
            self._paint(force=True)
            self.icon.update_menu()

        return handler

    def toggle_autostart(self, *_):
        set_autostart(not autostart_enabled())
        self.icon.update_menu()

    def quit(self, *_):
        self.stopped.set()
        self.wake.set()
        self.panel.close()
        if self.icon is not None:
            self.icon.stop()

    # -------------------------------------------------- 菜单
    def _menu(self) -> pystray.Menu:
        def checked(key, value):
            return lambda item: self.cfg.get(key) == value

        return pystray.Menu(
            pystray.MenuItem(lambda item: self._header(), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("打开面板", lambda *_: self.panel.toggle(), default=True),
            pystray.MenuItem("立即刷新", self.refresh),
            pystray.MenuItem("电量记录…", lambda *_: self.panel.show_history()),
            pystray.MenuItem(
                "DPI 档位",
                pystray.Menu(*[
                    pystray.MenuItem(
                        lambda item, k=k: self._dpi_label(k),
                        # pystray 会按参数个数传 (icon, item)，必须用 *args 吃掉，
                        # 不然位置参数会把闭包默认的 k 覆盖成 MenuItem
                        lambda *args, k=k: self.set_dpi_stage(k),
                        checked=lambda item, k=k: self._dpi_stage() == k,
                        radio=True,
                    )
                    for k in range(6)
                ]),
            ),
            pystray.MenuItem(
                "刷新间隔",
                pystray.Menu(*[
                    pystray.MenuItem(label, self.set_interval(sec),
                                     checked=checked("interval", sec), radio=True)
                    for sec, label in INTERVALS
                ]),
            ),
            pystray.MenuItem(
                "低电量阈值",
                pystray.Menu(*[
                    pystray.MenuItem(label, self.set_threshold(val),
                                     checked=checked("low", val), radio=True)
                    for val, label in THRESHOLDS
                ]),
            ),
            pystray.MenuItem(
                "图标样式",
                pystray.Menu(*[
                    pystray.MenuItem(label, self.set_style(key),
                                     checked=checked("style", key), radio=True)
                    for key, label in STYLES
                ]),
            ),
            pystray.MenuItem("开机自启", self.toggle_autostart,
                             checked=lambda item: autostart_enabled()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("诊断设备（插线读不到时点这个）", self.diagnose),
            pystray.MenuItem("退出", self.quit),
        )

    def _new_icon(self) -> pystray.Icon:
        return pystray.Icon(
            APP_ID, render_icon(None, self.cfg["style"], self.light_taskbar, size=tray_size()),
            APP_NAME, menu=self._menu(),
        )

    def serve(self) -> None:
        """托盘消息循环 + 看门狗：万一循环意外结束，1 秒后重建图标继续跑。"""
        threading.Thread(target=self._loop, name="battery-poll", daemon=True).start()
        if self.open_panel:
            threading.Timer(1.2, self.panel.toggle).start()
        restarts = 0
        while not self.stopped.is_set():
            self.icon = self._new_icon()
            self._last_paint = None
            self._last_header = ""
            self._paint(force=True)
            log(f"icon.run 进入（第 {restarts + 1} 次）")
            try:
                self.icon.run()
            except BaseException:
                log(f"icon.run 异常:\n{traceback.format_exc()}")
            if self.stopped.is_set():
                break
            restarts += 1
            log(f"icon.run 意外返回，将重建图标（累计 {restarts} 次）")
            time.sleep(1)


# --------------------------------------------------------------------- 入口
def main() -> int:
    args = sys.argv[1:]
    if "--cli" in args:
        result = mchose_hid.read_battery()
        if result.get("ok"):
            print(f"{result.get('device')}  {result.get('percent')}%  {result.get('status')}")
        else:
            print(f"[失败] {result.get('status')}：{result.get('detail')}")
        return 0 if result.get("ok") else 1

    interval = None
    if "--interval" in args:
        try:
            interval = int(args[args.index("--interval") + 1])
        except Exception:
            interval = None

    if not acquire_single_instance():
        log("已有实例在跑，本次退出")
        return 0  # 已经有实例在跑

    import logging

    logging.basicConfig(
        filename=os.path.join(CFG_DIR, "pystray.log"),
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log(f"启动，exe={sys.executable} frozen={getattr(sys, 'frozen', False)}")
    try:
        import faulthandler

        _fh = open(os.path.join(CFG_DIR, "crash.log"), "a", encoding="utf-8")
        faulthandler.enable(file=_fh, all_threads=True)
    except Exception:
        pass
    threading.excepthook = lambda a: log(
        f"线程 {getattr(a.thread, 'name', '?')} 异常: {a.exc_value!r}\n"
        + "".join(traceback.format_exception(a.exc_type, a.exc_value, a.exc_traceback))
    )

    TrayApp(interval, open_panel="--panel" in args).serve()
    log("主函数结束")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
