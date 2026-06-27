"""Render a shareable stats card (PNG) from the solved-problem store.

Used two ways: committed to the repo as `profile/stats.png` for embedding in a
GitHub profile README, and rendered live in the app's Showcase tab as a preview.
Pure Pillow so it works inside the py2app bundle with no extra deps.
"""
from __future__ import annotations

import io
from collections import Counter

from PIL import Image, ImageDraw, ImageFont

from .dashboard import _d, _streaks, LABELS

# palette (dark card — looks good on light & dark READMEs)
BG_TOP = (32, 36, 58)
BG_BOT = (18, 20, 28)
BORDER = (42, 47, 62)
INK = (240, 242, 248)
MUTED = (138, 144, 166)
ACCENT = (123, 122, 246)
CHIP_BG = (38, 43, 59)
CHIP_INK = (185, 192, 212)
DIFF = {"Easy": (44, 187, 93), "Medium": (227, 160, 8), "Hard": (229, 72, 77)}

_FONT_PATHS = {
    False: ["/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf"],
    True: ["/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial Bold.ttf",
           "/System/Library/Fonts/Supplemental/Arial Bold.ttf"],
}


def _font(size: int, bold: bool = False):
    for p in _FONT_PATHS[bold]:
        try:
            if p.endswith(".ttc"):
                return ImageFont.truetype(p, size, index=1 if bold else 0)
            return ImageFont.truetype(p, size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def _w(draw, text, font):
    b = draw.textbbox((0, 0), text, font=font)
    return b[2] - b[0]


def render_png(items: list, username: str = "", subtitle: str = "Competitive Programming") -> bytes:
    W, H = 880, 340
    pad = 36
    img = Image.new("RGB", (W, H), BG_BOT)

    # vertical gradient background
    grad = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / H
        grad.putpixel((0, y), tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3)))
    img.paste(grad.resize((W, H)), (0, 0))

    # rounded card mask + border
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], radius=24, fill=255)
    card = Image.new("RGB", (W, H), BG_BOT)
    card.paste(img, (0, 0))
    out = Image.new("RGB", (W, H), (13, 14, 19))
    out.paste(card, (0, 0), mask)
    d = ImageDraw.Draw(out)
    d.rounded_rectangle([1, 1, W - 2, H - 2], radius=24, outline=BORDER, width=2)

    # ---- stats ----
    total = len(items)
    plat = Counter(i.get("platform", "?") for i in items)
    langs = Counter((i.get("lang") or "").strip() for i in items if (i.get("lang") or "").strip())
    diff = Counter(i.get("difficulty") for i in items if i.get("difficulty") in DIFF)
    tags = Counter(t for i in items for t in (i.get("tags") or []))
    days = [x for x in (_d(i.get("timestamp")) for i in items) if x]
    cur, longest = _streaks(days)

    # ---- header: logo + name ----
    lx, ly = pad, pad
    d.rounded_rectangle([lx, ly, lx + 52, ly + 52], radius=14, fill=ACCENT)
    f_gk = _font(24, True)
    d.text((lx + 26 - _w(d, "GK", f_gk) / 2, ly + 12), "GK", font=f_gk, fill=(255, 255, 255))
    tx = lx + 68
    d.text((tx, ly + 2), username or "your profile", font=_font(26, True), fill=INK)
    d.text((tx, ly + 34), subtitle, font=_font(15), fill=MUTED)

    # streak pill (top-right) — drawn flame dot instead of emoji (Pillow has no color emoji)
    if cur:
        ftxt = f"{cur}-day streak"
        fp = _font(15, True)
        pw = _w(d, ftxt, fp) + 44
        px0 = W - pad - pw
        d.rounded_rectangle([px0, ly + 8, W - pad, ly + 40], radius=16, fill=CHIP_BG)
        d.ellipse([px0 + 14, ly + 18, px0 + 26, ly + 30], fill=(255, 145, 60))
        d.text((px0 + 32, ly + 14), ftxt, font=fp, fill=(255, 175, 80))

    # ---- big number ----
    by = 120
    d.text((pad, by), str(total), font=_font(74, True), fill=INK)
    nw = _w(d, str(total), _font(74, True))
    d.text((pad + nw + 14, by + 38), "problems\nsolved", font=_font(16, True), fill=ACCENT)

    # secondary stats row
    sy = 214
    chips = [("platforms", str(len(plat))), ("longest streak", f"{longest}d"),
             ("active days", str(len(set(days)))), ("languages", str(len(langs)))]
    cx = pad
    for label, val in chips:
        d.text((cx, sy), val, font=_font(22, True), fill=INK)
        d.text((cx, sy + 30), label, font=_font(12), fill=MUTED)
        cx += max(_w(d, val, _font(22, True)), _w(d, label, _font(12))) + 34

    # ---- difficulty bars (right column) ----
    rx, rw = 560, 280
    ry = 110
    dtot = sum(diff.values()) or 1
    for level in ("Easy", "Medium", "Hard"):
        n = diff.get(level, 0)
        d.text((rx, ry), level, font=_font(14, True), fill=DIFF[level])
        d.text((rx + rw - _w(d, str(n), _font(14, True)), ry), str(n), font=_font(14, True), fill=MUTED)
        d.rounded_rectangle([rx, ry + 22, rx + rw, ry + 30], radius=4, fill=(46, 51, 68))
        fillw = int(rw * (n / dtot)) if dtot else 0
        if fillw > 6:
            d.rounded_rectangle([rx, ry + 22, rx + fillw, ry + 30], radius=4, fill=DIFF[level])
        ry += 46

    # ---- topic chips (bottom) ----
    chy = 286
    chx = pad
    fc = _font(13, True)
    for t, _n in tags.most_common(6):
        cw = _w(d, t, fc) + 24
        if chx + cw > W - pad:
            break
        d.rounded_rectangle([chx, chy, chx + cw, chy + 28], radius=14, fill=CHIP_BG)
        d.text((chx + 12, chy + 6), t, font=fc, fill=CHIP_INK)
        chx += cw + 8

    # footer wordmark
    d.text((W - pad - _w(d, "gitkosh", _font(13, True)), H - pad + 2),
           "gitkosh", font=_font(13, True), fill=MUTED)

    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue()
