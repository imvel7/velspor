"""Vel Spor gorsel uretici: bordo-altin, Galatasaray haber dili (1080x1080)."""
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
LOGO_PATH = ROOT / "logo.png"
S = 1080
SQ = 0.80  # yazi daraltma orani (dar ve kalin gorunum)

PAL = {
    "BURG": dict(dark=(48, 0, 12), light=(128, 10, 32), text=(250, 208, 140),
                 line=(196, 30, 54), small=(238, 200, 150), on=(48, 0, 12)),
    "BLACK": dict(dark=(12, 8, 9), light=(54, 14, 24), text=(250, 208, 140),
                  line=(165, 0, 33), small=(230, 196, 150), on=(12, 8, 9)),
    "NAVY": dict(dark=(6, 12, 52), light=(22, 56, 156), text=(255, 255, 255),
                 line=(60, 200, 240), small=(200, 218, 255), on=(6, 12, 52)),
}
GOLD = (250, 208, 140)

LEVELS = {"A": "SON DAKİKA", "B": "GÜNDEM", "C": "ARŞİV"}

# kategori -> (duzen, palet)
CATS = {
    "Maç Öncesi":          ("center", "BURG"),
    "Maç İçi":             ("big",     "BLACK"),
    "Transfer":            ("big", "BURG"),
    "Oyuncu Performansı":  ("center",  "BLACK"),
    "Oyuncu Değişikliği":  ("chevron", "BURG"),
    "Disiplin ve Ceza":    ("frame", "BLACK"),
    "Sakatlık":            ("bar", "BURG"),
    "Kulüp ve Yönetim":    ("frame", "BURG"),
    "Özel Gün":            ("center", "BLACK"),
    "Puan Durumu":         ("bar", "BLACK"),
    "Antrenman":           ("split", "BLACK"),
    "Taraftar ve Stadyum": ("split", "BURG"),
    "Açıklamalar":         ("bar",   "BLACK"),
    "Avrupa":              ("center", "NAVY"),
    "Gündem":              ("split", "BURG"),
}


def tr_upper(s):
    return s.replace("i", "İ").replace("ı", "I").upper()


def font(size, bold=True):
    name = "LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf"
    for p in (ROOT / name, Path("/usr/share/fonts/truetype/liberation") / name,
              Path("/usr/share/fonts/truetype/dejavu") / name.replace("Liberation", "DejaVu")):
        try:
            return ImageFont.truetype(str(p), size)
        except OSError:
            continue
    return ImageFont.load_default()


def tw(text, size, sq=SQ):
    return font(size).getlength(text) * sq


def text_layer(text, size, fill, sq=SQ):
    f = font(size)
    w = int(f.getlength(text)) + 8
    h = int(size * 1.4)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((2, 0), text, font=f, fill=tuple(fill) + (255,))
    return layer.resize((max(1, int(w * sq)), h), Image.LANCZOS)


def draw_text(img, x, y, text, size, fill, sq=SQ, anchor="l"):
    """Dar (yatay sikistirilmis) kalin yazi. anchor: l / m / r"""
    layer = text_layer(text, size, fill, sq)
    nw = layer.width
    if anchor == "m":
        x = x - nw // 2
    elif anchor == "r":
        x = x - nw
    img.paste(layer, (int(x), int(y)), layer)
    return nw


def spaced(img, x, y, text, size, fill, gap=6, anchor="l", bold=True):
    """Harf aralikli kucuk etiket yazisi."""
    f = font(size, bold)
    total = sum(f.getlength(c) + gap for c in text) - gap
    if anchor == "m":
        x = x - total / 2
    elif anchor == "r":
        x = x - total
    d = ImageDraw.Draw(img)
    for c in text:
        d.text((x, y), c, font=f, fill=fill)
        x += f.getlength(c) + gap
    return total


def wrap(text, size, maxw):
    lines, cur = [], ""
    for word in text.split():
        t = (cur + " " + word).strip()
        if tw(t, size) <= maxw:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def fit(text, maxw, maxh, start, minsize=34, lh=1.02):
    size = start
    while size >= minsize:
        lines = wrap(text, size, maxw)
        if len(lines) * int(size * lh) <= maxh and all(tw(l, size) <= maxw for l in lines):
            return size, lines
        size -= 2
    lines = wrap(text, minsize, maxw)
    n = max(1, maxh // int(minsize * lh))
    lines = lines[:n]
    while lines and tw(lines[-1] + "…", minsize) > maxw:
        lines[-1] = lines[-1][:-1]
    if lines:
        lines[-1] = lines[-1].rstrip() + "…"
    return minsize, lines


def headline(img, text, x, y, maxw, maxh, color, start=110, align="l", lh=1.02):
    text = tr_upper(text)
    size, lines = fit(text, maxw, maxh, start, lh=lh)
    step = int(size * lh)
    top = y + max(0, (maxh - step * len(lines)) // 2)
    for i, l in enumerate(lines):
        if align == "m":
            draw_text(img, x + maxw // 2, top + i * step, l, size, color, anchor="m")
        else:
            draw_text(img, x, top + i * step, l, size, color)
    return size


def _logo_mask():
    im = Image.open(LOGO_PATH).convert("RGB")
    px = im.load()
    w, h = im.size
    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    for yy in range(h):
        for xx in range(w):
            r, g, b = px[xx, yy]
            mp[xx, yy] = max(0, min(255, int((r - g - 40) * 2.2)))
    return mask.crop(mask.getbbox())


_LM = None


def paste_logo(img, height, pos, color, alpha=255):
    global _LM
    if _LM is None:
        _LM = _logo_mask()
    ratio = height / _LM.height
    m = _LM.resize((max(1, int(_LM.width * ratio)), height), Image.LANCZOS)
    if alpha < 255:
        m = m.point(lambda v: v * alpha // 255)
    img.paste(Image.new("RGB", m.size, color), pos, m)
    return m.size


def background(p):
    mask = Image.radial_gradient("L").resize((S, S))
    # radial_gradient: merkez siyah, kenar beyaz -> merkez acik olsun diye ters cevir
    mask = mask.point(lambda v: 255 - v)
    img = Image.composite(Image.new("RGB", (S, S), p["light"]), Image.new("RGB", (S, S), p["dark"]), mask)
    px = img.load()
    rnd = random.Random(11)
    for _ in range(110000):
        x, y = rnd.randrange(S), rnd.randrange(S)
        dd = rnd.randint(-9, 6)
        r, g, b = px[x, y]
        px[x, y] = (max(0, min(255, r + dd)), max(0, min(255, g + dd)), max(0, min(255, b + dd)))
    return img


def overlay_lines(img, p, cx=540, cy=540, step=120, count=8, alpha=70):
    ov = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for i in range(1, count + 1):
        r = i * step
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=p["line"] + (alpha,), width=2)
    img.paste(Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB"))


def chevrons(d, x, y, w, up, color, n=3, gap=26, width=9):
    for i in range(n):
        yy = y + i * gap * (1 if up else -1)
        if up:
            d.line([(x, yy + w // 2), (x + w // 2, yy), (x + w, yy + w // 2)], fill=color, width=width, joint="curve")
        else:
            d.line([(x, yy - w // 2), (x + w // 2, yy), (x + w, yy - w // 2)], fill=color, width=width, joint="curve")


def footer(img, p, src, y=950, h=84, center=False, color=None):
    color = color or p["text"]
    d = ImageDraw.Draw(img)
    d.line([(70, y - 22), (S - 70, y - 22)], fill=p["line"], width=2)
    sz = paste_logo(img, h, (70, y), color)
    d = ImageDraw.Draw(img)
    spaced(img, 70 + sz[0] + 24, y + h // 2 - 16, "VEL SPOR", 26, color, gap=8)
    if src:
        t = "Kaynak: " + src
        f = font(24, False)
        while f.getlength(t) > 420 and len(t) > 12:
            t = t[:-2] + "…"
        d.text((S - 70 - f.getlength(t), y + h // 2 - 14), t, font=f, fill=p["small"])


def top_label(img, p, cat, lvl, y=62, x0=70):
    spaced(img, x0, y, "GALATASARAY", 24, p["small"], gap=7)
    spaced(img, S - 70, y, LEVELS[lvl], 24, p["small"], gap=7, anchor="r")
    d = ImageDraw.Draw(img)
    d.line([(x0, y + 40), (S - 70, y + 40)], fill=p["line"], width=2)


# ---------------- duzenler ----------------

def l_center(img, cat, lvl, text, src, p):
    overlay_lines(img, p)
    top_label(img, p, cat, lvl)
    size, lines = fit(tr_upper(text), 900, 520, 240, minsize=90, lh=0.98)
    step = int(size * 0.98)
    y = 170 + (560 - step * len(lines)) // 2
    for i, l in enumerate(lines):
        draw_text(img, S // 2, y + i * step, l, size, p["text"], anchor="m")
    y += step * len(lines) + 26
    ImageDraw.Draw(img).line([(S // 2 - 60, y), (S // 2 + 60, y)], fill=p["text"], width=4)
    spaced(img, S // 2, y + 28, tr_upper(cat), 28, p["small"], gap=9, anchor="m")
    footer(img, p, src)


def l_chevron(img, cat, lvl, text, src, p):
    overlay_lines(img, p, cx=900, cy=300, step=140, count=7)
    d = ImageDraw.Draw(img)
    top_label(img, p, cat, lvl)
    chevrons(d, 90, 160, 120, True, p["text"])
    chevrons(d, S - 210, 880, 120, False, p["text"])
    spaced(img, S // 2, 160, tr_upper(cat), 30, p["text"], gap=9, anchor="m")
    headline(img, text, 90, 250, 900, 580, p["text"], start=210, align="m")
    footer(img, p, src, y=960, h=70)


def l_big(img, cat, lvl, text, src, p):
    overlay_lines(img, p, cx=200, cy=900, step=130, count=9)
    top_label(img, p, cat, lvl)
    d = ImageDraw.Draw(img)
    t = tr_upper(cat)
    w = int(tw(t, 38) + 60)
    d.rectangle([70, 150, 70 + w, 150 + 62], fill=p["text"])
    draw_text(img, 100, 158, t, 38, p["on"])
    headline(img, text, 70, 250, 940, 600, p["text"], start=220)
    d.polygon([(0, 905), (S, 835), (S, 850), (0, 920)], fill=p["line"])
    footer(img, p, src, y=950, h=84)


def l_split(img, cat, lvl, text, src, p):
    d = ImageDraw.Draw(img)
    # sag panel
    d.polygon([(700, 0), (S, 0), (S, S), (560, S)], fill=p["dark"])
    d.polygon([(690, 0), (706, 0), (566, S), (550, S)], fill=p["line"])
    paste_logo(img, 520, (690, 300), p["light"], alpha=170)
    top_label(img, p, cat, lvl)
    t = tr_upper(cat)
    w = int(tw(t, 38) + 60)
    d.rectangle([70, 150, 70 + w, 150 + 62], fill=p["text"])
    draw_text(img, 100, 158, t, 38, p["on"])
    headline(img, text, 70, 250, 500, 600, p["text"], start=170)
    footer(img, p, src, y=950, h=84)


def l_bar(img, cat, lvl, text, src, p):
    d = ImageDraw.Draw(img)
    overlay_lines(img, p, cx=900, cy=900, step=130, count=9)
    d.rectangle([0, 0, 190, S], fill=p["dark"])
    d.rectangle([190, 0, 200, S], fill=p["text"])
    paste_logo(img, 130, (30, 60), p["text"])
    # dikey kategori yazisi
    t = tr_upper(cat)
    size = 70
    while tw(t, size) > 700 and size > 30:
        size -= 4
    rot = text_layer(t, size, p["text"]).rotate(90, expand=True)
    img.paste(rot, (60, S - 120 - rot.height), rot)
    top_label(img, p, cat, lvl, x0=250)
    headline(img, text, 250, 160, 760, 700, p["text"], start=200)
    d = ImageDraw.Draw(img)
    d.line([(250, 960), (S - 70, 960)], fill=p["line"], width=2)
    spaced(img, 250, 985, "VEL SPOR", 24, p["text"], gap=8)
    f = font(24, False)
    tt = "Kaynak: " + src
    while f.getlength(tt) > 420 and len(tt) > 12:
        tt = tt[:-2] + "…"
    d.text((S - 70 - f.getlength(tt), 985), tt, font=f, fill=p["small"])


def l_frame(img, cat, lvl, text, src, p):
    overlay_lines(img, p)
    d = ImageDraw.Draw(img)
    d.rectangle([44, 44, S - 44, S - 44], outline=p["text"], width=3)
    d.rectangle([58, 58, S - 58, S - 58], outline=p["line"], width=2)
    t = tr_upper(cat)
    f = 34
    w = tw(t, f) + 80
    x0 = S // 2 - w / 2
    d.rectangle([x0, 30, x0 + w, 100], fill=p["dark"], outline=p["text"], width=3)
    draw_text(img, S // 2, 44, t, f + 6, p["text"], anchor="m")
    spaced(img, S // 2, 128, "GALATASARAY · " + LEVELS[lvl], 24, p["small"], gap=7, anchor="m")
    headline(img, text, 110, 190, 860, 650, p["text"], start=220, align="m")
    footer(img, p, src, y=905, h=84)


LAYOUTS = dict(center=l_center, chevron=l_chevron, big=l_big, split=l_split, bar=l_bar, frame=l_frame)


def claim_badge(img):
    d = ImageDraw.Draw(img)
    w, h = 170, 54
    x, y = S - 70 - w, 118
    d.rectangle([x, y, x + w, y + h], fill=GOLD)
    spaced(img, x + w // 2, y + 12, "İDDİA", 28, (40, 6, 14), gap=6, anchor="m")


def make(cat, lvl, text, src, out, claim=False):
    if cat not in CATS:
        cat = "Gündem"
    layout, pal = CATS[cat]
    p = PAL[pal]
    img = background(p)
    LAYOUTS[layout](img, cat, lvl, text, src, p)
    if claim:
        claim_badge(img)
    img.save(out)
    return img
