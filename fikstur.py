"""Aylik fikstur karti. Her ayin 1'inde (veya elle) o ayin Galatasaray maclarini kart olarak Telegram'a yollar.
Env: AY=2026-11 (bos = bu ay), TAKIM (549679). Anahtarlar yazdirilmaz."""
import base64, io, math, os, random, sys, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

import fikstur_assets as A
from net import tg_configured, tg_send_message, tg_send_photo
from olaykart import _crop, put, spaced_img, txt
from render import paste_logo, tr_upper

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
LOGOS = ROOT / "state" / "logos"
TEAM = int(os.environ.get("TAKIM") or 549679)
W, H = 1080, 1350
GOLD = (232, 190, 128)
DIM = (150, 112, 74)
RED = (150, 22, 44)
AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
TR = {  # API'nin ASCII verdigi isimler
    "fenerbahce": "Fenerbahçe", "besiktas": "Beşiktaş", "basaksehir": "Başakşehir", "istanbul basaksehir": "Başakşehir",
    "caykur rizespor": "Çaykur Rizespor", "rizespor": "Rizespor", "eyupspor": "Eyüpspor", "kasimpasa": "Kasımpaşa",
    "goztepe": "Göztepe", "genclerbirligi": "Gençlerbirliği", "karagumruk": "Karagümrük", "fatih karagumruk": "Karagümrük",
    "amedspor": "Amedspor", "samsunspor": "Samsunspor", "konyaspor": "Konyaspor", "kayserispor": "Kayserispor",
    "antalyaspor": "Antalyaspor", "alanyaspor": "Alanyaspor", "gaziantep fk": "Gaziantep FK", "trabzonspor": "Trabzonspor",
    "bodrum fk": "Bodrum FK", "sivasspor": "Sivasspor", "hatayspor": "Hatayspor", "adana demirspor": "Adana Demirspor",
}
UTC = timezone.utc


def tr_name(n):
    return TR.get((n or "").strip().lower(), (n or "").strip())


# ---------- gorsel parcalar ----------

def _png(b64):
    return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGBA")


def sized(im, h):
    r = h / im.height
    return im.resize((max(1, round(im.width * r)), h), Image.LANCZOS)


def paste(img, im, cx, cy):
    img.paste(im, (round(cx - im.width / 2), round(cy - im.height / 2)), im)


def lora(text, size, fill, wght=600):
    f = ImageFont.truetype(io.BytesIO(base64.b64decode(A.LORA)), size)
    try:
        f.set_variation_by_axes([wght])
    except Exception:  # noqa: BLE001
        pass
    lay = Image.new("RGBA", (int(f.getlength(text)) + 40, int(size * 1.6)), (0, 0, 0, 0))
    ImageDraw.Draw(lay).text((20, 10), text, font=f, fill=tuple(fill) + (255,))
    return _crop(lay)


def duotone(raw):
    """Renkli arma -> altin tek renk. Arka plan saydamsa alfa, degilse parlaklik kullanilir."""
    im = Image.open(io.BytesIO(raw)).convert("RGBA")
    a, lum = im.getchannel("A"), im.convert("L")
    if a.getextrema()[0] > 200:  # tamamen opak: parlaklik
        al = lum.point(lambda v: 0 if v < 25 else min(255, (v - 25) * 2))
    else:
        l2 = lum.point(lambda v: min(255, int(60 + v * 0.8)))
        al = ImageChops.multiply(a, l2)
    bb = al.getbbox()
    if not bb:
        raise ValueError("bos arma")
    al = al.crop(bb)
    big = al.resize((al.width * 2, al.height * 2), Image.LANCZOS) if al.height < 300 else al
    out = Image.new("RGBA", big.size, GOLD + (0,))
    out.putalpha(big)
    return out


def team_logo(team):
    """Rakip arma: indir, altina boya, state/logos'ta sakla. Olmazsa bas harf rozeti."""
    LOGOS.mkdir(parents=True, exist_ok=True)
    cache = LOGOS / f"{team.get('id')}.png"
    try:
        if cache.exists():
            return Image.open(cache).convert("RGBA")
        url = team.get("logo") or team.get("logoUrl") or team.get("image")
        if not url:
            raise ValueError("logo adresi yok")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=20).read()
        im = duotone(raw)
        im.save(cache)
        return im
    except Exception as e:  # noqa: BLE001
        print("Arma alinamadi:", team.get("name"), type(e).__name__, str(e)[:80])
        return badge(team.get("name", "?"))


def badge(name):
    code = "".join(w[0] for w in tr_name(name).split()[:3]).upper() or "?"
    if len(code) < 2:
        code = tr_name(name)[:3].upper()
    S = 360
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([6, 6, S - 6, S - 6], outline=GOLD + (255,), width=10)
    t = txt(code, 150, GOLD, maxw=240)
    im.paste(t, ((S - t.width) // 2, (S - t.height) // 2), t)
    return im


def comp_icon(league):
    n = (league or "").lower()
    if "champions" in n:
        return _png(A.CL)
    if "super lig" in n or "süper lig" in n or "trendyol" in n:
        return _png(A.LIG)
    return None


# ---------- arka plan ----------

def _noise(sc, seed):
    r = np.random.RandomState(seed)
    a = r.rand(H // sc + 2, W // sc + 2).astype("float32")
    return np.asarray(Image.fromarray((a * 255).astype("uint8")).resize((W, H), Image.BICUBIC), dtype="float32") / 255


def ribbons():
    S2 = 2
    ov = Image.new("RGBA", (W * S2, 520 * S2), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    def cy(x, k):
        t = x / W
        return 70 + 300 * math.sin(t * math.pi * 0.95) * (1 - 0.25 * t) + 40 * math.sin(t * 9) * t * (1 - t) * 4 + k

    for i in range(9):
        k = i * 30
        top = [(x * S2, cy(x, k) * S2) for x in range(0, W + 1, 6)]
        bot = [(x * S2, (cy(x, k) + 17) * S2) for x in range(W, -1, -6)]
        a = 255 - i * 8
        d.polygon(top + bot, fill=RED + (a,) if i % 2 == 0 else (30, 6, 12, a))
    ov = ov.resize((W, 520), Image.LANCZOS)
    g = Image.new("L", (W, 520), 255)
    gd = ImageDraw.Draw(g)
    for yy in range(340, 520):
        gd.line([(0, yy), (W, yy)], fill=int(255 * (520 - yy) / 180))
    ov.putalpha(ImageChops.multiply(ov.getchannel("A"), g))
    base = Image.new("RGBA", (W, 520), (0, 0, 0, 255))
    rb = Image.alpha_composite(base, ov).convert("RGB")
    return rb.filter(ImageFilter.GaussianBlur(22)).point(lambda v: int(v * 0.8)), rb


def backdrop():
    rnd = random.Random(8)
    y = np.linspace(0, 1, H)[:, None]
    base = np.zeros((H, W, 3), "float32")
    base[..., 0] = 12 + 26 * y
    base[..., 1] = 7 + 8 * y
    base[..., 2] = 9 + 8 * y
    img = Image.fromarray(base.clip(0, 255).astype("uint8"))
    beams = Image.new("L", (W, H), 0)
    bd = ImageDraw.Draw(beams)
    for ax, tx, sp in ((120, 330, 120), (540, 540, 150), (960, 750, 120)):
        bd.polygon([(ax - 14, -20), (ax + 14, -20), (tx + sp, 980), (tx - sp, 980)], fill=255)
    beams = beams.filter(ImageFilter.GaussianBlur(48))
    fade = Image.linear_gradient("L").transpose(Image.FLIP_TOP_BOTTOM).resize((W, H))
    beams = ImageChops.multiply(beams, fade).point(lambda v: int(v * 0.34))
    img = Image.composite(Image.new("RGB", (W, H), (255, 176, 96)), img, beams)
    n = _noise(220, 1) * 0.6 + _noise(90, 2) * 0.3 + _noise(40, 3) * 0.1
    sm = np.clip((n - 0.42) * 2.2, 0, 1) * np.clip((np.linspace(0, 1, H)[:, None] - 0.25) * 1.6, 0, 1)
    img = Image.composite(Image.new("RGB", (W, H), (120, 26, 40)), img, Image.fromarray((sm * 90).astype("uint8")))
    bk = Image.new("RGB", (W, H), (0, 0, 0))
    bd = ImageDraw.Draw(bk)
    for _ in range(22):
        x, yy, r = rnd.randrange(W), rnd.randrange(H), rnd.randint(6, 26)
        c = rnd.randint(22, 50)
        bd.ellipse([x - r, yy - r, x + r, yy + r], fill=(c, int(c * 0.7), int(c * 0.35)))
    img = ImageChops.screen(img, bk.filter(ImageFilter.GaussianBlur(5)))
    dd = Image.new("RGB", (W, H), (0, 0, 0))
    d2 = ImageDraw.Draw(dd)
    for _ in range(420):
        x, yy = rnd.randrange(W), rnd.randrange(H)
        c = rnd.randint(90, 230)
        d2.ellipse([x - 1, yy - 1, x + 1, yy + 1], fill=(c, int(c * 0.78), int(c * 0.45)))
    img = ImageChops.screen(img, dd.filter(ImageFilter.GaussianBlur(0.6)))
    vg = Image.radial_gradient("L").resize((W, H)).point(lambda v: int(v * 0.85))
    img = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), img, vg)
    glow, rb = ribbons()
    r = ImageChops.screen(rb, glow)
    img.paste(ImageChops.screen(img.crop((0, 0, W, 520)), r), (0, 0))
    return img


# ---------- kart ----------

def panel(img, y, h):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.rounded_rectangle([60, y, W - 60, y + h], 16, fill=(10, 5, 6, 150), outline=GOLD + (70,), width=2)
    d.rectangle([60, y + 14, 66, y + h - 14], fill=GOLD + (220,))
    img.paste(Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB"))


def make_card(ay_adi, rows, out):
    """rows: [(gun, rakip_dict, lig_adi, evde_mi)]"""
    img = backdrop()
    d = ImageDraw.Draw(img)
    k = lora(ay_adi, 130, GOLD)
    put(img, k, cx=W // 2, y=40)
    f = txt("FİKSTÜR", 230, GOLD, maxw=940)
    fy = 40 + k.height + 12
    put(img, f, cx=W // 2, y=fy)
    y0 = fy + f.height
    paste(img, sized(_png(A.GS), 140), W // 2, y0 + 92)
    n = len(rows)
    top, bottom, gap = y0 + 190, 1245, 14
    ph = min(124, int((bottom - top - (n - 1) * gap) / n))
    top += max(0, (bottom - top - (n * ph + (n - 1) * gap)) // 2) if n < 5 else 0
    for i, (gun, opp, lig, evde) in enumerate(rows):
        y = top + i * (ph + gap)
        cy = y + ph / 2
        panel(img, y, ph)
        num = txt(f"{gun:02d}", int(ph * 0.8), GOLD)
        put(img, num, x=104, y=cy - num.height / 2)
        km = spaced_img(tr_upper(ay_adi), 20, DIM, gap=8)
        put(img, km, x=250, y=cy - km.height / 2)
        paste(img, sized(team_logo(opp), int(ph * 0.8)), W // 2, cy)
        ic = comp_icon(lig)
        if ic is not None:
            paste(img, sized(ic, int(ph * 0.43)), 790, cy)
        else:
            t = spaced_img(tr_upper((lig or "")[:11]), 14, DIM, gap=4)
            put(img, t, cx=770, y=cy - t.height / 2)
        tag = spaced_img("EVDE" if evde else "DEPL.", 24, GOLD, gap=8)
        put(img, tag, x=W - 100 - tag.width, y=cy - tag.height / 2)
    d.line([(70, 1282), (W - 70, 1282)], fill=(110, 40, 40), width=2)
    paste_logo(img, 34, (70, 1298), GOLD)
    put(img, spaced_img("VEL SPOR", 20, GOLD, gap=9), x=122, y=1306)
    img.save(out)


# ---------- veri ----------

def month_rows(year, month):
    import canli  # fikstur onbellegi + API istemcisi
    fx = canli.refresh_fixtures(force=True)
    rows = []
    for m in fx:
        t = canli.ko(m) + timedelta(hours=3)  # Turkiye saati
        if t.year != year or t.month != month:
            continue
        evde = m["home"].get("id") == TEAM
        opp = m["away"] if evde else m["home"]
        rows.append((t.day, opp, m.get("league", ""), evde, t))
    rows.sort(key=lambda r: r[4])
    return rows


def tweet(ay_adi, rows):
    lines = [f"📅 {ay_adi} ayı fikstürü", ""]
    for gun, opp, lig, evde, t in rows:
        lines.append(f"{gun} {ay_adi} {t.strftime('%H:%M')} · {tr_name(opp.get('name'))} ({'E' if evde else 'D'})")
    lines += ["", "#Galatasaray"]
    return "\n".join(lines)


def main():
    ay = (os.environ.get("AY") or "").strip()
    now = datetime.now(UTC) + timedelta(hours=3)
    y, m = (int(ay[:4]), int(ay[5:7])) if len(ay) >= 7 else (now.year, now.month)
    ay_adi = AYLAR[m - 1]
    rows = month_rows(y, m)
    if not rows:
        tg_send_message(f"{ay_adi} ayında fikstürde Galatasaray maçı bulunamadı.")
        return 0
    OUT.mkdir(exist_ok=True)
    path = str(OUT / f"fikstur_{y}_{m:02d}.png")
    make_card(ay_adi, [(g, o, l, e) for g, o, l, e, _ in rows], path)
    if tg_configured():
        tg_send_photo(path, tweet(ay_adi, rows))
    else:
        print("Telegram ayarli degil; kart:", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
