"""Vel Spor kare gorsel uretici (1080x1080)."""
from pathlib import Path
import random

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
LOGO_PATH = ROOT / "logo.png"

S = 1080
CREAM = (245, 239, 220)
RED = (165, 0, 33)
DARK = (110, 0, 20)
INK = (30, 24, 22)
GOLD = (200, 150, 45)

PAL = {
    "RED":  dict(strong=RED, on=CREAM, accent=DARK, dbg=(92, 0, 20), dwm=(125, 0, 28)),
    "INK":  dict(strong=(32, 26, 26), on=CREAM, accent=RED, dbg=(22, 17, 17), dwm=(62, 12, 22)),
    "GOLD": dict(strong=GOLD, on=INK, accent=RED, dbg=(40, 30, 14), dwm=(80, 58, 20)),
}

LEVELS = {"A": "SON DAKİKA", "B": "GÜNDEM", "C": "ARŞİV"}

# kategori -> (duzen, palet)
CATS = {
    "Maç Öncesi":          ("split",   "RED"),
    "Maç İçi":             ("dark",    "INK"),
    "Transfer":            ("diag",    "RED"),
    "Oyuncu Performansı":  ("bar",     "INK"),
    "Disiplin ve Ceza":    ("frame",   "GOLD"),
    "Sakatlık":            ("bar",     "RED"),
    "Kulüp ve Yönetim":    ("frame",   "INK"),
    "Özel Gün":            ("diag",    "GOLD"),
    "Puan Durumu":         ("split",   "INK"),
    "Antrenman":           ("stripes", "RED"),
    "Taraftar ve Stadyum": ("dark",    "RED"),
    "Açıklamalar":         ("stripes", "INK"),
    "Avrupa":              ("split",   "GOLD"),
    "Gündem":              ("diag",    "INK"),
}


def tr_upper(s):
    return s.replace("i", "İ").replace("ı", "I").upper()


def font(size, bold=True):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for p in (ROOT / name, Path("/usr/share/fonts/truetype/dejavu") / name):
        try:
            return ImageFont.truetype(str(p), size)
        except OSError:
            continue
    return ImageFont.load_default()


def _load_logo_mask():
    im = Image.open(LOGO_PATH).convert("RGB")
    px = im.load()
    w, h = im.size
    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            mp[x, y] = max(0, min(255, int((r - g - 40) * 2.2)))
    return mask.crop(mask.getbbox())


_LOGO_MASK = None


def logo_mask():
    global _LOGO_MASK
    if _LOGO_MASK is None:
        _LOGO_MASK = _load_logo_mask()
    return _LOGO_MASK


def paste_logo(img, height, pos, color):
    lm = logo_mask()
    ratio = height / lm.height
    m = lm.resize((max(1, int(lm.width * ratio)), height), Image.LANCZOS)
    img.paste(Image.new("RGB", m.size, color), pos, m)
    return m.size


def wrap(d, text, f, maxw):
    lines, cur = [], ""
    for word in text.split():
        t = (cur + " " + word).strip()
        if d.textlength(t, font=f) <= maxw:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def headline(d, text, x, y, maxw, maxh, color, start=92, minsize=40):
    size = start
    while size >= minsize:
        f = font(size)
        lines = wrap(d, text, f, maxw)
        lh = int(size * 1.18)
        if len(lines) * lh <= maxh and all(d.textlength(l, font=f) <= maxw for l in lines):
            break
        size -= 2
    f = font(size)
    lines = wrap(d, text, f, maxw)
    lh = int(size * 1.18)
    max_lines = max(1, maxh // lh)
    if len(lines) > max_lines:  # cok uzunsa son satiri kisalt
        lines = lines[:max_lines]
        last = lines[-1]
        while last and d.textlength(last + "…", font=f) > maxw:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    for i, l in enumerate(lines):
        d.text((x, y + i * lh), l, font=f, fill=color)


def tag(d, x, y, text, fill, fg, size=36):
    f = font(size)
    tw = d.textlength(text, font=f)
    d.rectangle([x, y, x + tw + 48, y + size + 28], fill=fill)
    d.text((x + 24, y + 11), text, font=f, fill=fg)


def texture(img):
    px = img.load()
    rnd = random.Random(7)
    for _ in range(90000):
        x, y = rnd.randrange(S), rnd.randrange(S)
        dd = rnd.randint(-7, 3)
        r, g, b = px[x, y]
        px[x, y] = (r + dd, g + dd, b + dd)


def brand_row(img, x, y, h, logo_color, text_color, source, src_color):
    sz = paste_logo(img, h, (x, y), logo_color)
    d = ImageDraw.Draw(img)
    d.text((x + sz[0] + 26, y + h // 2 - 20), "V E L   S P O R", font=font(28), fill=text_color)
    if source:
        f = font(24, False)
        t = "Kaynak: " + source
        if d.textlength(t, font=f) > 420:
            while d.textlength(t + "…", font=f) > 420 and len(t) > 10:
                t = t[:-1]
            t += "…"
        d.text((S - 70 - d.textlength(t, font=f), y + h // 2 - 14), t, font=f, fill=src_color)


def _short_source(src, n=40):
    return src if len(src) <= n else src[: n - 1] + "…"


# ---------------- duzenler ----------------

def l_diag(img, cat, lvl, text, src, p):
    d = ImageDraw.Draw(img)
    tag(d, 70, 70, tr_upper(cat), p["strong"], p["on"])
    d.text((70, 170), LEVELS[lvl], font=font(30), fill=RED)
    headline(d, text, 70, 250, 940, 380, INK)
    d.polygon([(0, 790), (S, 640), (S, 660), (0, 810)], fill=p["accent"])
    d.polygon([(0, 810), (S, 660), (S, S), (0, S)], fill=p["strong"])
    brand_row(img, 70, 900, 110, p["on"], p["on"], src, p["on"])


def l_split(img, cat, lvl, text, src, p):
    d = ImageDraw.Draw(img)
    d.polygon([(0, 0), (S, 0), (S, 330), (0, 420)], fill=p["strong"])
    d.polygon([(0, 420), (S, 330), (S, 350), (0, 440)], fill=p["accent"])
    d.text((70, 70), LEVELS[lvl], font=font(30), fill=p["on"])
    big = tr_upper(cat)
    size = 130
    while d.textlength(big, font=font(size)) > 940 and size > 50:
        size -= 4
    d.text((70, 140), big, font=font(size), fill=p["on"])
    headline(d, text, 70, 500, 940, 380, INK)
    d.line([(70, 930), (500, 930)], fill=RED, width=3)
    brand_row(img, 70, 950, 90, RED, INK, src, INK)


def l_dark(img, cat, lvl, text, src, p):
    img.paste(Image.new("RGB", (S, S), p["dbg"]))
    paste_logo(img, 760, (440, 330), p["dwm"])
    d = ImageDraw.Draw(img)
    tag(d, 70, 70, tr_upper(cat), CREAM, INK)
    d.ellipse([70, 170, 94, 194], fill=GOLD)
    d.text((110, 166), LEVELS[lvl], font=font(30), fill=GOLD)
    headline(d, text, 70, 270, 900, 520, CREAM)
    d.line([(70, 930), (500, 930)], fill=GOLD, width=3)
    brand_row(img, 70, 950, 90, CREAM, CREAM, src, (210, 200, 180))


def l_bar(img, cat, lvl, text, src, p):
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 200, S], fill=p["strong"])
    d.rectangle([200, 0, 214, S], fill=p["accent"])
    paste_logo(img, 150, (28, 70), p["on"])
    d = ImageDraw.Draw(img)
    for i, w in enumerate(["VEL", "SPOR"]):
        d.text((100 - d.textlength(w, font=font(30)) / 2, 960 + i * 40 - 30), w, font=font(30), fill=p["on"])
    tag(d, 270, 90, tr_upper(cat), p["strong"], p["on"], size=34)
    d.text((270, 190), LEVELS[lvl], font=font(30), fill=RED)
    headline(d, text, 270, 280, 740, 600, INK, start=84)
    d.line([(270, 960), (700, 960)], fill=RED, width=3)
    d.text((270, 985), "Kaynak: " + _short_source(src), font=font(24, False), fill=INK)


def l_frame(img, cat, lvl, text, src, p):
    img.paste(Image.new("RGB", (S, S), p["strong"]))
    d = ImageDraw.Draw(img)
    d.rectangle([60, 60, S - 60, 860], fill=CREAM)
    d.rectangle([76, 76, S - 76, 844], outline=p["accent"], width=3)
    tag(d, 110, 30, tr_upper(cat), p["accent"], CREAM, size=34)
    d.text((120, 130), LEVELS[lvl], font=font(30), fill=RED)
    headline(d, text, 120, 200, 840, 540, INK, start=84)
    d.text((120, 790), "Kaynak: " + _short_source(src), font=font(24, False), fill=INK)
    brand_row(img, 70, 905, 110, p["on"], p["on"], None, None)


def l_stripes(img, cat, lvl, text, src, p):
    d = ImageDraw.Draw(img)
    d.polygon([(S, 560), (S, S), (560, S)], fill=p["strong"])
    d.polygon([(S, 470), (S, 520), (470, S), (520, S)], fill=p["accent"])
    d.polygon([(S, 400), (S, 425), (400, S), (425, S)], fill=p["strong"])
    brand_row(img, 70, 70, 110, RED, INK, None, None)
    tag(d, 70, 240, tr_upper(cat), p["strong"], p["on"], size=34)
    d.text((70, 340), LEVELS[lvl], font=font(30), fill=RED)
    headline(d, text, 70, 410, 760, 340, INK, start=84)
    d.text((70, 990), "Kaynak: " + _short_source(src), font=font(24, False), fill=INK)


LAYOUTS = dict(diag=l_diag, split=l_split, dark=l_dark, bar=l_bar, frame=l_frame, stripes=l_stripes)


def claim_badge(img):
    d = ImageDraw.Draw(img)
    f = font(30)
    t = "İDDİA"
    w = d.textlength(t, font=f) + 40
    x = S - 70 - w
    d.rectangle([x, 100, x + w, 100 + 58], fill=GOLD)
    d.text((x + 20, 111), t, font=f, fill=INK)


def make(cat, lvl, text, src, out, claim=False):
    if cat not in CATS:
        cat = "Gündem"
    layout, pal = CATS[cat]
    img = Image.new("RGB", (S, S), CREAM)
    texture(img)
    LAYOUTS[layout](img, cat, lvl, text, src, PAL[pal])
    if claim:
        claim_badge(img)
    img.save(out)
    return img
