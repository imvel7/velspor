"""Canli maç olay kartlari (1080x1080) ve paylasim metinleri."""
from PIL import Image, ImageDraw

from render import (PAL, S, _hand_raw, background, chevrons, draw_text, font, footer, hand, hfont,
                    overlay_lines, spaced, text_layer, tr_upper, tw)

RED = (214, 28, 48)
YEL = (250, 204, 40)

LEAGUES = {"uefa champions league": "ŞAMPİYONLAR LİGİ", "uefa europa league": "AVRUPA LİGİ",
           "uefa conference league": "KONFERANS LİGİ", "süper lig": "SÜPER LİG",
           "super lig": "SÜPER LİG", "turkish cup": "TÜRKİYE KUPASI", "ziraat turkish cup": "TÜRKİYE KUPASI",
           "super cup": "SÜPER KUPA"}

# tur -> (baslik, palet, not)
KINDS = {
    "goal": ("GOL", "BURG"), "opp_goal": ("RAKİP GOLÜ", "BLACK"), "own_goal": ("KENDİ KALESİNE", "BLACK"),
    "pen_goal": ("PENALTIDAN GOL", "BURG"), "opp_pen_goal": ("RAKİP PENALTISI", "BLACK"),
    "pen_miss": ("PENALTI KAÇTI", "BLACK"), "pen_award": ("PENALTI", "BURG"),
    "yellow": ("SARI KART", "BLACK"), "red": ("KIRMIZI KART", "BLACK"), "second_yellow": ("İKİNCİ SARI", "BLACK"),
    "var": ("VAR İNCELEMESİ", "BLACK"), "goal_cancel": ("GOL İPTAL", "BLACK"), "injury": ("SAKATLIK", "BLACK"),
    "sub": ("OYUNCU DEĞİŞİKLİĞİ", "BURG"),
    "kickoff": ("MAÇ BAŞLADI", "BURG"), "ht": ("İLK YARI SONA ERDİ", "BLACK"),
    "h2": ("İKİNCİ YARI BAŞLADI", "BURG"), "ft": ("MAÇ SONA ERDİ", "BURG"),
}
NOTES = {"goal": "gooool", "pen_goal": "nokta atışı", "own_goal": "talihsiz", "pen_miss": "olmadı!",
         "red": "ceza var", "second_yellow": "oyundan atıldı", "var": "inceleniyor", "goal_cancel": "iptal",
         "kickoff": "hadi!", "ht": "devre arası", "h2": "devam", "ft": "maç bitti", "injury": "geçmiş olsun"}


def league_label(name):
    n = (name or "").strip()
    return LEAGUES.get(n.lower(), tr_upper(n) if n else "MAÇ")


def _fit(text, maxw, start, minsize=34):
    size = start
    while size > minsize and tw(text, size) > maxw:
        size -= 2
    return size


# ---------- olcumlu yerlesim: her oge ink-kirpilmis bir RGBA gorsel ----------

def _crop(layer):
    bb = layer.getchannel("A").getbbox()
    return layer.crop(bb) if bb else Image.new("RGBA", (1, 1), (0, 0, 0, 0))


def txt(text, size, fill, maxw=None):
    if maxw:
        size = _fit(text, maxw, size, 30)
    return _crop(text_layer(text, size, fill))


def spaced_img(text, size, fill, gap=7):
    size = int(size * 1.3)
    f = font(size)
    total = int(sum(f.getlength(c) + gap for c in text) - gap) + 12
    lay = Image.new("RGBA", (total, int(size * 1.5)), (0, 0, 0, 0))
    dd = ImageDraw.Draw(lay)
    x = 4
    for c in text:
        dd.text((x, 0), c, font=f, fill=tuple(fill) + (255,))
        x += f.getlength(c) + gap
    return _crop(lay)


def hand_img(text, size, fill, angle=-4, maxw=800):
    while hfont(size).getlength(text) > maxw and size > 30:
        size -= 4
    lay = _hand_raw(text, size, fill).rotate(angle, expand=True, resample=Image.BICUBIC)
    return _crop(lay)


def put(img, im, cx=None, x=None, y=0):
    px = int(x if x is not None else cx - im.width / 2)
    img.paste(im, (px, int(y)), im)


def stack(img, make_items, top, bottom, gap=34):
    """make_items(scale) -> [(gorsel, x_mod)]. Sigana kadar kucultur, dikeyde ortalar."""
    scale = 1.0
    while True:
        items = make_items(scale)
        total = sum(i.height for i in items) + gap * (len(items) - 1)
        if total <= bottom - top or scale <= 0.45:
            break
        scale -= 0.05
    y = top + max(0, (bottom - top - total) // 2)
    for im in items:
        put(img, im, cx=S // 2, y=y)
        y += im.height + gap
    return y


def _team_img(name, color, maxw, size=50, right=False):
    """Takim adi: sigarsa tek satir, sigmazsa iki satira boler."""
    one = txt(name, size, color)
    if one.width <= maxw:
        return one
    sz = size
    while sz > 36 and tw(name, sz) > maxw:
        sz -= 2
    if tw(name, sz) <= maxw:
        return txt(name, sz, color)
    words = name.split()
    best = None
    for i in range(1, len(words)):
        l1, l2 = " ".join(words[:i]), " ".join(words[i:])
        w = max(tw(l1, 36), tw(l2, 36))
        if best is None or w < best[0]:
            best = (w, l1, l2)
    if not best:
        return txt(name, 36, color, maxw=maxw)
    sz2 = 40
    while sz2 > 26 and best[0] * sz2 / 36 > maxw:
        sz2 -= 2
    a, b2 = txt(best[1], sz2, color), txt(best[2], sz2, color)
    im = Image.new("RGBA", (max(a.width, b2.width), a.height + b2.height + 6), (0, 0, 0, 0))
    im.paste(a, (im.width - a.width if right else 0, 0), a)
    im.paste(b2, (im.width - b2.width if right else 0, a.height + 6), b2)
    return im


def _bar(img, p, home, away, score, hot, line_y, bottom_y=922):
    """Alt skor cubugu: ortada skor, kenarlarda takim adlari."""
    d = ImageDraw.Draw(img)
    d.line([(70, line_y), (S - 70, line_y)], fill=p["line"], width=2)
    hn, an = tr_upper(home), tr_upper(away)
    hc = p["text"] if hot in ("home", None) else p["small"]
    ac = p["text"] if hot in ("away", None) else p["small"]
    mid = (line_y + bottom_y) // 2
    sc = txt(f"{score[0]} - {score[1]}", 100, p["text"]) if score else None
    side_w = (940 - (sc.width + 70 if sc else 40)) // 2
    h_im = _team_img(hn, hc, side_w)
    a_im = _team_img(an, ac, side_w, right=True)
    put(img, h_im, x=70, y=mid - h_im.height // 2)
    put(img, a_im, x=S - 70 - a_im.width, y=mid - a_im.height // 2)
    if sc:
        put(img, sc, cx=S // 2, y=mid - sc.height // 2)


def _card_icon_img(kind):
    cols = {"yellow": [YEL], "red": [RED], "second_yellow": [YEL, RED]}[kind]
    w = 120 + 60 * (len(cols) - 1)
    lay = Image.new("RGBA", (w + 60, 260), (0, 0, 0, 0))
    dd = ImageDraw.Draw(lay)
    for i, c in enumerate(cols):
        dd.rounded_rectangle([30 + i * 60, 40, 150 + i * 60, 210], radius=14, fill=c + (255,))
    return _crop(lay.rotate(-10, expand=True, resample=Image.BICUBIC))


def _sub_group(label, name, p, up):
    nm = txt(tr_upper(name), 120, p["text"], maxw=740)
    lb = spaced_img(label, 26, p["small"], gap=8)
    h = lb.height + 8 + nm.height
    g = Image.new("RGBA", (940, h), (0, 0, 0, 0))
    g.paste(lb, (130, 0), lb)
    g.paste(nm, (130, lb.height + 8), nm)
    ar = Image.new("RGBA", (110, 110), (0, 0, 0, 0))
    chevrons(ImageDraw.Draw(ar), 10, 10 if up else 100, 90, up, p["text"] + (255,), n=3, gap=20, width=8)
    ar = _crop(ar)
    g.paste(ar, (0, (h - ar.height) // 2), ar)
    return _crop(g)


def make_card(kind, out, home, away, league="", minute=None, name="", sub="", score=None,
              hot=None, extra=None, ins="", outp=""):
    """kind: KINDS anahtari. name: oyuncu; sub: asist ya da alt satir; ins/outp: degisiklik."""
    title, pal = KINDS[kind]
    p = PAL[pal]
    img = background(p)
    overlay_lines(img, p, cx=900, cy=300, step=140, count=7)
    d = ImageDraw.Draw(img)
    spaced(img, 70, 62, "GALATASARAY", 24, p["small"], gap=7)
    spaced(img, S - 70, 62, league_label(league), 24, p["small"], gap=7, anchor="r")
    d.line([(70, 102), (S - 70, 102)], fill=p["line"], width=2)
    top = 135
    if minute:
        t = txt(f"{minute}'", 60, p["on"])
        w, h = t.width + 60, t.height + 36
        d.rectangle([70, 140, 70 + w, 140 + h], fill=p["text"])
        put(img, t, cx=70 + w / 2, y=140 + (h - t.height) / 2)
        top = 140 + h + 20
        if kind == "sub":
            put(img, spaced_img("OYUNCU DEĞİŞİKLİĞİ", 28, p["small"], gap=9), x=70 + w + 30, y=150 + (h - 30) // 2 - 8)

    status = kind in ("kickoff", "ht", "h2", "ft")
    if status:
        line_y = 806
        hn, an = tr_upper(home), tr_upper(away)

        def items(sc):
            out_ = [txt(title, int(190 * sc), p["text"], maxw=940)]
            if score:
                out_.append(txt(f"{score[0]} - {score[1]}", int(210 * sc), p["text"]))
            if kind == "ft" and extra:
                lines = list(extra)
                if len(lines) > 4:
                    lines = ["  ·  ".join(lines[i:i + 2]) for i in range(0, len(lines), 2)][:5]
                for ln in lines:
                    out_.append(spaced_img(tr_upper(ln), 22, p["small"], gap=5))
            else:
                out_.append(hand_img(NOTES.get(kind, ""), int(90 * sc), p["text"], maxw=600))
            return out_
        # satir araliklari: baslik ve skor arasi genis, golcu satirlari dar -> tek tek istifle
        scale = 1.0
        while True:
            its = items(scale)
            gaps = [30] + [10] * (len(its) - 2) if kind == "ft" and extra else [30] * (len(its) - 1)
            if kind == "ft" and extra and len(its) > 2:
                gaps[1] = 24
            total = sum(i.height for i in its) + sum(gaps)
            if total <= line_y - 28 - top or scale <= 0.45:
                break
            scale -= 0.05
        y = top + max(0, (line_y - 28 - top - total) // 2)
        for i, im in enumerate(its):
            put(img, im, cx=S // 2, y=y)
            y += im.height + (gaps[i] if i < len(gaps) else 0)
        _bar(img, p, home, away, None, None, line_y)
    elif kind == "sub":
        line_y = 786
        gi = _sub_group("GİREN", ins, p, True)
        go = _sub_group("ÇIKAN", outp, p, False)
        total = gi.height + go.height + 60
        y = top + max(0, (line_y - 28 - top - total) // 2)
        gx = (S - max(gi.width, go.width)) // 2
        put(img, gi, x=gx, y=y)
        put(img, go, x=gx, y=y + gi.height + 60)
        _bar(img, p, home, away, score, hot, line_y)
    else:
        line_y = 786

        def items(sc):
            out_ = []
            if kind in ("yellow", "red", "second_yellow"):
                ic = _card_icon_img(kind)
                tt = txt(title, int(200 * sc), p["text"], maxw=640)
                row = Image.new("RGBA", (ic.width + 40 + tt.width, max(ic.height, tt.height)), (0, 0, 0, 0))
                row.paste(ic, (0, (row.height - ic.height) // 2), ic)
                row.paste(tt, (ic.width + 40, (row.height - tt.height) // 2), tt)
                out_.append(row)
            else:
                out_.append(txt(title, int((290 if kind == "goal" else 200) * sc), p["text"], maxw=940))
            if name:
                out_.append(txt(tr_upper(name), int(125 * sc), p["text"], maxw=940))
            note = sub or NOTES.get(kind)
            if note:
                out_.append(hand_img(note, int((80 if sub else 90) * sc), p["text"], angle=-3, maxw=860))
            return out_
        stack(img, items, top, line_y - 28)
        _bar(img, p, home, away, score, hot, line_y)
    footer(img, p, None, y=950, h=84)
    img.save(out)
    return out


def caption(kind, d):
    """Paylasim metni. d: name, sub, minute, home, away, score, ins, outp"""
    m = f"{d.get('minute')}' " if d.get("minute") else ""
    sc = f"{d['home']} {d['score'][0]}-{d['score'][1]} {d['away']}" if d.get("score") else f"{d['home']} - {d['away']}"
    n, s = d.get("name", ""), d.get("sub", "")
    t = {
        "goal": f"⚽ GOL! {m}{n}" + (f" ({s})" if s else "") + f"\n\n{sc}",
        "opp_goal": f"Rakipten gol. {m}{n}\n\n{sc}",
        "own_goal": f"Kendi kalesine gol. {m}{n}\n\n{sc}",
        "pen_goal": f"⚽ Penaltıdan gol! {m}{n}\n\n{sc}",
        "opp_pen_goal": f"Rakip penaltıdan golü buldu. {m}{n}\n\n{sc}",
        "pen_miss": f"Penaltı kaçtı! {m}{n}\n\n{sc}",
        "pen_award": f"Penaltı kararı! {m}\n\n{sc}",
        "yellow": f"🟨 Sarı kart: {n} {m}".strip(),
        "red": f"🟥 Kırmızı kart! {n} {m}".strip(),
        "second_yellow": f"🟥 İkinci sarıdan kırmızı: {n} {m}".strip(),
        "var": f"VAR incelemesi {m}".strip(),
        "goal_cancel": f"Gol iptal edildi.\n\n{sc}",
        "injury": f"Sakatlık: {n} {m}".strip(),
        "sub": f"🔁 Oyuncu değişikliği {m}\n⬆️ {d.get('ins','')}\n⬇️ {d.get('outp','')}".strip(),
        "kickoff": f"Maç başladı!\n\n{d['home']} - {d['away']}",
        "ht": f"İlk yarı sona erdi.\n\n{sc}",
        "h2": f"İkinci yarı başladı.\n\n{sc}",
        "ft": f"Maç sona erdi.\n\n{sc}",
    }[kind]
    return t + "\n\n#Galatasaray"
