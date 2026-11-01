"""Canli maç olay kartlari (1080x1080) ve paylasim metinleri."""
from PIL import Image, ImageDraw

from render import (PAL, S, background, chevrons, draw_text, footer, hand, overlay_lines,
                    spaced, tr_upper, tw)

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


def _score_bar(img, p, home, away, score, hot, y=808):
    hn, an = tr_upper(home), tr_upper(away)
    d = ImageDraw.Draw(img)
    if score:
        draw_text(img, S // 2, y - 8, f"{score[0]} - {score[1]}", 112, p["text"], anchor="m")
    sz = min(_fit(hn, 330, 50), _fit(an, 330, 50))
    hc = p["text"] if hot in ("home", None) else p["small"]
    ac = p["text"] if hot in ("away", None) else p["small"]
    draw_text(img, 70, y + 18, hn, sz, hc)
    draw_text(img, S - 70, y + 18, an, sz, ac, anchor="r")
    d.line([(70, y - 22), (S - 70, y - 22)], fill=p["line"], width=2)


def _card_icon(img, kind, x, y):
    """Sari/kirmizi kart simgesi (hafif egik dikdortgen)."""
    cols = {"yellow": [YEL], "red": [RED], "second_yellow": [YEL, RED]}[kind]
    ov = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for i, c in enumerate(cols):
        ox = i * 60
        d.rounded_rectangle([x + ox, y, x + ox + 120, y + 170], radius=14, fill=c + (255,))
    ov = ov.rotate(-10, center=(x + 60, y + 85), resample=Image.BICUBIC)
    img.paste(ov, (0, 0), ov)


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
    if minute:
        t = f"{minute}'"
        w = int(tw(t, 60) + 60)
        d.rectangle([70, 140, 70 + w, 140 + 78], fill=p["text"])
        draw_text(img, 100, 146, t, 60, p["on"])

    if kind == "sub":
        chevrons(d, 80, 300, 90, True, p["text"], n=3, gap=20, width=8)
        spaced(img, 200, 270, "GİREN", 26, p["small"], gap=8)
        draw_text(img, 200, 300, tr_upper(ins), _fit(tr_upper(ins), 820, 120), p["text"])
        chevrons(d, 80, 610, 90, False, p["text"], n=3, gap=20, width=8)
        spaced(img, 200, 560, "ÇIKAN", 26, p["small"], gap=8)
        draw_text(img, 200, 590, tr_upper(outp), _fit(tr_upper(outp), 820, 120), p["text"])
        spaced(img, S // 2, 760, "OYUNCU DEĞİŞİKLİĞİ", 28, p["small"], gap=9, anchor="m")
        if score:
            _score_bar(img, p, home, away, score, hot, y=830)
    elif kind in ("kickoff", "ht", "h2", "ft"):
        size = _fit(title, 940, 190, 60)
        draw_text(img, S // 2, 250, title, size, p["text"], anchor="m")
        if score:
            draw_text(img, S // 2, 430, f"{score[0]} - {score[1]}", 260, p["text"], anchor="m")
        if extra:
            for i, line in enumerate(extra[:4]):
                spaced(img, S // 2, 690 + i * 36, tr_upper(line), 22, p["small"], gap=5, anchor="m")
        hand(img, NOTES.get(kind, ""), S // 2, 775, 90, p["text"], angle=-4, maxw=600) if kind != "ft" or not extra else None
        _score_bar(img, p, home, away, None, None, y=825) if not score else None
        if score:
            hn, an = tr_upper(home), tr_upper(away)
            sz = min(_fit(hn, 450, 54), _fit(an, 450, 54))
            draw_text(img, 70, 836, hn, sz, p["text"])
            draw_text(img, S - 70, 836, an, sz, p["text"], anchor="r")
    else:
        if kind in ("yellow", "red", "second_yellow"):
            _card_icon(img, kind, 80 if kind != "second_yellow" else 70, 250)
            size = _fit(title, 640, 200, 60)
            draw_text(img, 300 if kind != "second_yellow" else 330, 300, title, size, p["text"])
            top = 500
        elif kind == "goal":
            size = _fit(title, 940, 290, 60)
            draw_text(img, S // 2, 215, title, size, p["text"], anchor="m")
            top = 500
        else:
            size = _fit(title, 940, 230, 60)
            draw_text(img, S // 2, 250, title, size, p["text"], anchor="m")
            top = 520
        if name:
            nm = tr_upper(name)
            draw_text(img, S // 2, top, nm, _fit(nm, 940, 140, 50), p["text"], anchor="m")
        note = NOTES.get(kind)
        cy = top + (190 if kind == "goal" else 215)
        if sub:
            hand(img, sub, S // 2, cy, 80, p["text"], angle=-3, maxw=860)
        elif note:
            hand(img, note, S // 2, cy, 90, p["text"], angle=-4, maxw=700)
        _score_bar(img, p, home, away, score, hot)
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
