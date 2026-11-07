"""Haber gorseli (dikey 1080x1350). Turler: alinti (B), son dakika (C), iddia (A), standart (D).
Hata olursa cagiran render.make'e geri doner."""
from pathlib import Path
from PIL import Image, ImageDraw
import perfkart as P


def tru(s):
    return (s or "").replace("i", "İ").replace("ı", "I").upper()

from perfkart import BS, PM, W, H, _bg, _right

RED = (214, 28, 48)
NAVY_CATS = {"Avrupa"}


def _theme(cat):
    return dict(P.TH["cl" if cat in NAVY_CATS else "sl"])


def _wrap(d, s, f, maxw):
    out, cur = [], ""
    for w in s.split():
        if d.textlength((cur + " " + w).strip(), font=f) <= maxw:
            cur = (cur + " " + w).strip()
        else:
            if cur:
                out.append(cur)
            cur = w
    return out + ([cur] if cur else [])


def _fit_lines(d, s, maxw, maxh, start=170, lo=70, maxlines=5):
    size = start
    while True:
        f = BS(size)
        lines = _wrap(d, s, f, maxw)
        step = int(size * 1.13)
        if (len(lines) <= maxlines and len(lines) * step <= maxh and all(d.textlength(l, font=f) <= maxw for l in lines)) or size <= lo:
            return f, lines, step
        size -= 6


def _block(d, text, ozet, maxw, maxh, start, subsize=30, subw=900, gap=40):
    """Baslik + ozet blogunun yuksekligi ve baslik yazi tipi."""
    f, lines, step = _fit_lines(d, tru(text), maxw, maxh, start)
    sub = _wrap(d, ozet, PM(subsize), subw)[:3] if ozet else []
    h = len(lines) * step + ((gap + len(sub) * (subsize + 16)) if sub else 0)
    return h


def _center_y(top, bottom, h):
    return int(top + max(0, (bottom - top - h)) / 2)


def _draw_head(d, t, text, vurgu, x, y, maxw, maxh, start=170):
    text = tru(text)
    f, lines, step = _fit_lines(d, text, maxw, maxh, start)
    vs = {tru(w.strip(".,:;!?'\"")) for w in (vurgu or "").split() if w}
    for ln in lines:
        words = ln.split(" ")
        cx = x
        for i, w in enumerate(words):
            core = tru(w.strip(".,:;!?'\"")).split("'")[0]
            col = t["acc"] if any(core == v.split("'")[0] for v in vs) else t["acc2"]
            d.text((cx, y), w, font=f, fill=col)
            cx += d.textlength(w + " ", font=f)
        y += step
    return y


def _chip(d, x, y, s, fill, tc):
    w = d.textlength(s, font=BS(36)) + 44
    d.rounded_rectangle((x, y, x + w, y + 60), 8, fill=fill)
    d.text((x + 22, y + 8), s, font=BS(36), fill=tc)
    return w


def _brand(d, t):
    d.line((70, H - 120, W - 70, H - 120), fill=t["line"], width=2)
    d.text((70, H - 92), "VEL SPOR", font=BS(40), fill=t["acc"])
    _right(d, W - 70, H - 86, "GALATASARAY", PM(24), t["txt"])


def _ghost(im, t, word, y=170, size=430, alpha=120, cat=""):
    if not word:
        word = (cat or "").split()[-1] if cat else ""
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    word = tru(word)
    if not word:
        return im
    s = size
    while s > 60 and od.textlength(word, font=BS(s)) > W - 40:
        s -= 10
    gc = t["line"] if t is P.TH["cl"] or t.get("comp") == "ŞAMPİYONLAR LİGİ" else t["panel"]
    od.text((20, y), word, font=BS(s), fill=tuple(gc) + (alpha if gc is t["panel"] else 95,))
    return Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")


def _sub(d, t, text, x, y, maxw=880, size=32):
    f = PM(size)
    for ln in _wrap(d, text, f, maxw)[:3]:
        d.text((x, y), ln, font=f, fill=t["txt"]); y += size + 16
    return y


def _quote(cat, soz, kisi, unvan, t):
    im = _bg(t, .5); d = ImageDraw.Draw(im)
    _chip(d, 70, 90, tru(cat) if cat and cat != "Gündem" else "AÇIKLAMA", t["acc"], t["c0"])
    # blogu ayri katmanda ciz, gercek murekkep sinirini olc, sonra dikey ortala
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
    f, lines, step = _fit_lines(ld, soz, 900, 560, 130, 64, 7)
    ld.text((60, 300), "“", font=BS(360), fill=tuple(t["panel"]) + (255,))
    qb = lay.getbbox()
    qbot = qb[3]
    y = qbot + 45
    for ln in lines:
        ld.text((70, y), ln, font=f, fill=tuple(t["acc2"]) + (255,)); y += step
    tb = lay.getbbox()
    ld.line((70, tb[3] + 36, 250, tb[3] + 36), fill=tuple(t["acc"]) + (255,), width=6)
    ld.text((70, tb[3] + 66), tru(kisi), font=BS(80), fill=tuple(t["acc"]) + (255,))
    if unvan:
        nb = lay.getbbox()
        ld.text((70, nb[3] + 18), unvan, font=PM(28), fill=tuple(t["txt"]) + (255,))
    box = lay.getbbox()
    bh = box[3] - box[1]
    ny = int(190 + (1190 - 190 - bh) / 2)
    im.paste(lay.crop(box), (box[0], ny), lay.crop(box))
    _brand(ImageDraw.Draw(im), t)
    return im


def _breaking(cat, head, vurgu, ozet, t):
    im = _bg(t, .3); d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 150), fill=RED)
    d.text((70, 38), "SON DAKİKA", font=BS(84), fill=(255, 255, 255))
    _right(d, W - 70, 58, tru(cat), PM(28), (255, 255, 255))
    y = _draw_head(d, t, head, vurgu, 70, 240, 940, 740, 176)
    if ozet:
        lines = _wrap(d, ozet, PM(34), 820)[:3]
        d.rectangle((70, y + 30, 90, y + 30 + len(lines) * 50), fill=t["acc"])
        for i, ln in enumerate(lines):
            d.text((115, y + 30 + i * 50), ln, font=PM(34), fill=t["txt"])
    _brand(d, t)
    return im


def _claim(cat, head, vurgu, ozet, anahtar, t):
    im = _bg(t, .4)
    im = _ghost(im, t, anahtar or cat, 200, 560, 120, cat); d = ImageDraw.Draw(im)
    x = 70
    x += _chip(d, x, 90, tru(cat), t["acc"], t["c0"]) + 14
    _chip(d, x, 90, "İDDİA", (130, 26, 44), t["acc2"])
    h = _block(d, head, ozet, 940, 700, 160)
    y = _draw_head(d, t, head, vurgu, 70, 1150 - h, 940, 700, 160)
    if ozet:
        _sub(d, t, ozet, 70, y + 40, 900, 30)
    _brand(d, t)
    return im


def _standard(cat, head, vurgu, ozet, anahtar, t):
    im = _bg(t, .55)
    im = _ghost(im, t, anahtar or cat, 200, 430, 130, cat); d = ImageDraw.Draw(im)
    _chip(d, 70, 90, tru(cat), t["acc"], t["c0"])
    h = _block(d, head, ozet, 940, 560, 150, gap=36)
    y = _draw_head(d, t, head, vurgu, 70, 1150 - h, 940, 560, 150)
    if ozet:
        _sub(d, t, ozet, 70, y + 36, 900, 30)
    _brand(d, t)
    return im


def _health(cat, kisi, teshis, durum, t):
    im = _bg(t, .45); d = ImageDraw.Draw(im)
    _chip(d, 70, 90, tru(cat) if cat else "SAKATLIK", t["acc"], t["c0"])
    # sari bant (paralelkenar) + SAGLIK RAPORU
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    od.polygon([(40, 260), (W - 20, 236), (W - 40, 420), (20, 444)], fill=tuple(t["acc"]) + (255,))
    im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB"); d = ImageDraw.Draw(im)
    f = BS(150)
    tw_ = d.textlength("SAĞLIK RAPORU", font=f)
    d.text(((W - tw_) / 2, 262), "SAĞLIK RAPORU", font=f, fill=t["c0"] if t is not P.TH["sl"] else (92, 10, 26))
    # EKG cizgisi
    y0 = 520
    pts = [(0, y0), (300, y0), (330, y0 - 18), (360, y0 + 8), (390, y0), (470, y0), (495, y0 - 60), (520, y0 + 70), (545, y0 - 100), (570, y0), (640, y0), (665, y0 - 14), (690, y0), (W, y0)]
    d.line(pts, fill=tuple(t["acc"]), width=4, joint="curve")
    # oyuncu adi
    name = tru(kisi)
    nf, nl, ns = _fit_lines(d, name, 940, 300, 190, 90, 2)
    y = 590
    for ln in nl:
        d.text((70, y), ln, font=nf, fill=t["acc2"]); y += ns
    y += 30
    if teshis:
        d.text((70, y), "TEŞHİS", font=BS(40), fill=t["acc"]); y += 56
        for ln in _wrap(d, teshis, PM(40), 930)[:3]:
            d.text((70, y), ln, font=PM(40), fill=t["acc2"]); y += 58
        y += 24
    if durum:
        d.text((70, y), "DURUM", font=BS(40), fill=t["acc"]); y += 56
        for ln in _wrap(d, durum, PM(34), 930)[:3]:
            d.text((70, y), ln, font=PM(34), fill=t["txt"]); y += 50
    _brand(d, t)
    return im


def make(cat, level, head, out, vurgu="", ozet="", anahtar="", tur="haber", soz="", kisi="", unvan="", claim=False):
    t = _theme(cat)
    if tur == "saglik" and kisi and (soz or ozet):
        im = _health(cat, kisi, soz, ozet, t)
    elif tur == "alinti" and soz and kisi:
        im = _quote(cat, soz, kisi, unvan, t)
    elif claim:
        im = _claim(cat, head, vurgu, ozet, anahtar, t)
    elif level == "A":
        im = _breaking(cat, head, vurgu, ozet, t)
    else:
        im = _standard(cat, head, vurgu, ozet, anahtar, t)
    im.save(out)
    return out


if __name__ == "__main__":
    o = Path("/tmp/claude-0/-home-claude/d5165a86-1578-550f-abe3-2f22a82e8aa9/scratchpad/haber")
    make("Transfer", "B", "Kislyak Galatasaray'ın transfer listesinde", o / "t1.png", "Kislyak", "Genç orta saha sarı-kırmızılılara sıcak bakıyor.", "Kislyak", claim=True)
    make("Kulüp ve Yönetim", "A", "Görev dağılımı çarşamba günü", o / "t2.png", "çarşamba", "Dursun Özbek, yeni görev dağılımını maçtan sonra yapmayı planlıyor.", "Özbek")
    make("Açıklamalar", "B", "x", o / "t3.png", tur="alinti", soz="Abdullah Kavukcu'nun istifasını ben istedim. Habersiz medya üzerinden istifa eden Öztürk'e ise kırgınım.", kisi="Dursun Özbek", unvan="Galatasaray Kulübü Başkanı")
    make("Sakatlık", "B", "Davinson Sanchez'in sağlık durumu belli oldu", o / "t4.png", "Sanchez", "Oyuncunun MR sonucu çıktı.", "Sanchez")
    make("Avrupa", "B", "Şampiyonlar Ligi'nde rakip belli oldu: Aston Villa", o / "t5.png", "Villa", "Karşılaşma 24 Kasım'da oynanacak.", "Villa")
