# -*- coding: utf-8 -*-
"""托盘图标的绘制。

三种样式：
  mouse    竖向胶囊的鼠标俯视轮廓，内部有滚轮与按键分界线（默认）
  battery  系统同款电池条
  number   纯数字

鼠标造型用「胶囊 + 滚轮 + 按键横线」这套标准画法：形状在 16px 下仍然立得住，
电量用液面从底部升起，未充满的部分留淡淡一层，保证鼠标轮廓始终完整。
所有图形都在 8~10 倍画布上绘制后 LANCZOS 缩放，边缘干净不发虚。
"""
from __future__ import annotations

import math
import os

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = (
    "seguisb.ttf",    # Segoe UI Semibold
    "segoeuib.ttf",   # Segoe UI Bold
    "bahnschrift.ttf",
    "arialbd.ttf",
)

STYLES = ("mouse", "battery", "number", "ring")

MOUSE_ASPECT = 0.68        # 宽 / 高
DIM_ALPHA = 90             # 未充满部分的透明度（0-255）


def _font(size: int) -> ImageFont.FreeTypeFont:
    for name in FONT_CANDIDATES:
        path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", name)
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _level_color(percent: int | None, low: int, fg: str, light_taskbar: bool = False) -> str:
    if percent is None:
        return "#8C8C8C"
    if percent <= low:
        # 深色任务栏用亮红，浅色任务栏用深红，保证对比度
        return "#D32F2F" if light_taskbar else "#FF5252"
    return fg


# --------------------------------------------------------------------- 鼠标图形
def _wedge(cx: float, y0: float, y1: float, body_w: float,
           top_ratio: float = 0.86, top_flat: float = 0.72, bot_flat: float = 0.95):
    """鼠标俯视轮廓：扁圆的顶（前端）+ 两条斜边 + 宽圆的底（掌心）。

    上窄下宽是鼠标最好认的特征，顶部压扁一点才不像水滴，16px 下也立得住。
    """
    rx_t = body_w * top_ratio / 2
    ry_t = rx_t * top_flat
    rx_b = body_w / 2 * 0.98
    ry_b = rx_b * bot_flat
    yt, yb = y0 + ry_t, y1 - ry_b
    pts = []
    for i in range(41):                       # 顶部扁弧，从左到右
        a = math.pi + math.pi * i / 40
        pts.append((cx + rx_t * math.cos(a), yt + ry_t * math.sin(a)))
    for i in range(1, 22):                    # 右斜边
        t = i / 22
        pts.append((cx + rx_t + (rx_b - rx_t) * t, yt + (yb - yt) * t))
    for i in range(41):                       # 底部圆弧，从右到左
        a = math.pi * i / 40
        pts.append((cx + rx_b * math.cos(a), yb + ry_b * math.sin(a)))
    for i in range(1, 22):                    # 左斜边
        t = i / 22
        pts.append((cx - rx_b + (rx_b - rx_t) * t, yb + (yt - yb) * t))
    return pts


def mouse_art(width: int, height: int, color: str, percent: int | None,
              stroke_ratio: float = 0.0, ss: int = 10) -> Image.Image:
    """画一个鼠标俯视图，内部按 percent 填充电量液面。

    percent 为 None 表示尚未读到电量（只有淡轮廓）。返回 width×height 的 RGBA。
    """
    W, H = max(2, int(width * ss)), max(2, int(height * ss))
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    cx = W / 2.0
    h = H * 0.99
    w = min(W * 0.99, h * MOUSE_ASPECT)
    y0 = (H - h) / 2
    y1 = y0 + h

    poly = _wedge(cx, y0, y1, w)
    shape = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shape).polygon(poly, fill=255)

    # 未充满：淡淡一层，鼠标轮廓始终看得出来
    ghost = Image.new("RGBA", (W, H), color)
    ghost.putalpha(DIM_ALPHA if percent is not None else 60)
    img.paste(ghost, (0, 0), shape)

    # 已充满：液面从底部升到 percent 高度
    if percent is not None and percent > 0:
        liquid = shape.copy()
        ImageDraw.Draw(liquid).rectangle(
            (0, 0, W, y1 - h * min(100, percent) / 100.0), fill=0
        )
        img.paste(Image.new("RGBA", (W, H), color), (0, 0), liquid)

    # 滚轮 + 左右键分缝：一条竖缝贯穿上半部，抠成透明（负空间）
    d = ImageDraw.Draw(img)
    gap_w = w * 0.145
    d.rounded_rectangle((cx - gap_w / 2, y0 + h * 0.095, cx + gap_w / 2, y0 + h * 0.42),
                        radius=gap_w / 2, fill=(0, 0, 0, 0))

    return img.resize((int(width), int(height)), Image.LANCZOS)


# --------------------------------------------------------------------- 电池 / 数字
def _draw_battery(d: ImageDraw.ImageDraw, box, color: str, percent: int | None, radius: int, width: int):
    """画一个 Windows 风格的横向电池：外框 + 右侧触点 + 内部填充。"""
    x0, y0, x1, y1 = box
    nub_w = max(2, int((y1 - y0) * 0.20))
    nub_h = (y1 - y0) * 0.42
    ny = (y0 + y1) / 2 - nub_h / 2

    body = (x0, y0, x1 - nub_w, y1)
    d.rounded_rectangle(body, radius=radius, outline=color, width=width)
    d.rounded_rectangle(
        (body[2] + 1, ny, x1, ny + nub_h), radius=max(1, radius // 2), fill=color
    )

    if percent is None:
        return
    # 填充必须落在描边内侧，否则 16px 下会和边框糊成一整块
    pad = width + max(1, int((y1 - y0) * 0.06))
    ix0, iy0 = body[0] + pad, body[1] + pad
    ix1, iy1 = body[2] - pad, body[3] - pad
    span = ix1 - ix0
    if percent > 0 and span > 0:
        fill_w = max(2, span * percent / 100)
        d.rounded_rectangle(
            (ix0, iy0, ix0 + fill_w, iy1), radius=max(1, radius // 2), fill=color
        )


def _sharpen_alpha(img: Image.Image, low: float = 0.32, high: float = 0.68) -> Image.Image:
    """把 LANCZOS 缩小产生的边缘中间灰阶压窄。

    16px 下边缘渐变拖到 2px 就显糊；把 alpha 在 [low, high] 区间外钳到 0/255、
    区间内线性拉满，渐变收窄到 ~1px，观感明显更锐（仍保留少量抗锯齿）。
    只用于 battery / number 这类实心图形；mouse 的淡色打底是有意做的半透明，不走这步。
    """
    a = img.getchannel("A")
    span = high - low
    lut = [0 if v / 255.0 <= low
           else 255 if v / 255.0 >= high
           else int(round(255 * (v / 255.0 - low) / span))
           for v in range(256)]
    img.putalpha(a.point(lut))
    return img


# --------------------------------------------------------------------- 圆环
def _bolt_poly(cx: float, cy: float, h: float):
    """闪电七边形（Material bolt 造型的归一化坐标），h 为高度，宽随比例。"""
    pts = [(13, 2), (3, 14), (11, 14), (9, 22), (21, 10), (13, 10)]
    w = h * 18.0 / 20.0
    return [(cx - w / 2 + px / 24.0 * w, cy - h / 2 + py / 24.0 * h) for px, py in pts]


def _ring_art(size: int, color: str, percent: int | None,
              scale: int = 4, charging: bool = False) -> Image.Image:
    """圆环进度：淡色底环 + 从 12 点方向顺时针的进度弧，端点圆头。

    percent 为 None 时只画一圈更淡的底环（未连接）。
    charging 为 True 时环心画一个实心闪电。
    """
    S = size * scale
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    pad = S * 0.06          # 尽量占满图标槽，托盘里看起来更大
    bbox = (pad, pad, S - pad, S - pad)
    w = max(2, int(S * 0.16))

    # 底环：与 mouse 的淡色打底同一思路，让"未充满的部分"也存在
    ghost_a = DIM_ALPHA if percent is not None else 60
    r, g, b = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
    d.ellipse(bbox, outline=(r, g, b, ghost_a), width=w)

    cx = cy = S / 2.0
    radius = (S - 2 * pad) / 2.0

    if percent is not None and percent > 0:
        sweep = 360.0 * min(100, percent) / 100.0
        a0, a1 = -90.0, -90.0 + sweep
        d.arc(bbox, start=a0, end=a1, fill=color, width=w)
        # PIL 的 arc 端点是平头，补两个圆点做圆头收口
        dot_r = w / 2.0
        for ang in (a0, a1):
            rad = math.radians(ang)
            ex, ey = cx + radius * math.cos(rad), cy + radius * math.sin(rad)
            d.ellipse((ex - dot_r, ey - dot_r, ex + dot_r, ey + dot_r), fill=color)

    # 充电中：环心实心闪电（闪电和环之间留一点空隙）
    if charging and percent is not None:
        inner_d = 2 * (radius - w / 2.0)
        d.polygon(_bolt_poly(cx, cy, inner_d * 0.66), fill=color)

    return _sharpen_alpha(img.resize((size, size), Image.LANCZOS), low=0.12, high=0.75)


def _fit_font(draw, text: str, max_w: float, max_h: float) -> ImageFont.FreeTypeFont:
    size = int(max_h)
    while size > 5:
        f = _font(size)
        l, t, r, b = draw.textbbox((0, 0), text, font=f)
        if (r - l) <= max_w and (b - t) <= max_h:
            return f
        size -= 1
    return _font(5)


def render(percent: int | None, style: str, light_taskbar: bool,
           low: int = 20, size: int = 32, scale: int = 4,
           charging: bool = False) -> Image.Image:
    """percent 为 None 表示未连接；返回 size×size 的 RGBA 图标。"""
    S = size * scale
    fg = "#1B1B1B" if light_taskbar else "#FFFFFF"
    color = _level_color(percent, low, fg, light_taskbar)

    if style == "number":
        img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        text = "--" if percent is None else str(percent)
        f = _fit_font(d, text, S * 0.96, S * 0.74)
        l, t, r, b = d.textbbox((0, 0), text, font=f)
        d.text(((S - (l + r)) / 2, (S - (t + b)) / 2), text, font=f, fill=color)
        return _sharpen_alpha(img.resize((size, size), Image.LANCZOS))

    if style == "battery":
        img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        margin_x = S * 0.03
        _draw_battery(d, (margin_x, S * 0.26, S - margin_x, S * 0.74), color, percent,
                      radius=int(S * 0.09), width=max(2, int(S * 0.0625)))
        return _sharpen_alpha(img.resize((size, size), Image.LANCZOS))

    if style == "ring":
        return _ring_art(size, color, percent, scale=scale, charging=charging)

    # mouse —— 竖着占满整个图标
    return mouse_art(S, S, color, percent, ss=1).resize((size, size), Image.LANCZOS)


def tray_size() -> int:
    """任务栏通知区域图标在 100% 缩放下是 16px，按当前 DPI 取准确尺寸，避免发虚。"""
    try:
        import ctypes

        dpi = int(ctypes.windll.user32.GetDpiForSystem())
    except Exception:
        dpi = 96
    return max(16, min(48, int(round(16 * (dpi or 96) / 96))))
