"""Oyuncu performans karti (Yuvron verisi). H = dikey isim, M = dev forma numarasi.
Sampiyonlar Ligi: lacivert/acik mavi. Super Lig: bordo/altin."""
import json, os, re
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
W, H = 1080, 1350
TH = {
    "cl": dict(c0=(5, 9, 36), c1=(22, 48, 140), acc=(142, 200, 255), acc2=(255, 255, 255), txt=(214, 226, 248), panel=(16, 34, 104), line=(70, 110, 200), comp="ŞAMPİYONLAR LİGİ"),
    "sl": dict(c0=(48, 6, 16), c1=(112, 16, 32), acc=(236, 190, 98), acc2=(247, 240, 232), txt=(226, 205, 190), panel=(130, 26, 44), line=(150, 60, 70), comp="TRENDYOL SÜPER LİG"),
}


def _font(name, size):
    for p in (ROOT / name, Path("/usr/share/fonts/truetype/google-fonts") / name, Path("/usr/share/fonts/truetype") / name):
        if p.exists():
            return ImageFont.truetype(str(p), size)
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


BS = lambda s: _font("BigShoulders-Bold.ttf", s)
PO = lambda s: _font("Poppins-Bold.ttf", s)
PM = lambda s: _font("Poppins-Medium.ttf", s)


def _bg(t, tilt):
    try:
        import arka
        return arka.bg(t, "cl" if t is TH["cl"] or t.get("comp") == "ŞAMPİYONLAR LİGİ" else "sl")
    except Exception:  # noqa: BLE001
        return _bg_basit(t, tilt)


def _bg_basit(t, tilt):
    y, x = np.mgrid[0:H, 0:W]
    d = np.sqrt(((x - W * .5) / W) ** 2 + ((y - H * tilt) / H) ** 2)
    k = np.clip(1 - d * 1.5, 0, 1)[..., None]
    a = np.array(t["c0"]) * (1 - k) + np.array(t["c1"]) * k + np.random.RandomState(2).normal(0, 2, (H, W, 1))
    return Image.fromarray(np.clip(a, 0, 255).astype("uint8")).convert("RGB")


def _ct(d, y, s, f, fill, cx=W // 2):
    d.text((cx - d.textlength(s, font=f) / 2, y), s, font=f, fill=fill)


def _right(d, x, y, s, f, fill):
    d.text((x - d.textlength(s, font=f), y), s, font=f, fill=fill)


def _fit(d, s, maker, size, maxw, lo=40):
    while size > lo and d.textlength(s, font=maker(size)) > maxw:
        size -= 4
    return maker(size)


def _top(d, t, match):
    _ct(d, 52, "VEL SPOR", BS(32), t["acc"])
    _ct(d, 100, f'{t["comp"]}  ·  {match.upper()}', PM(24), t["txt"])


def _pct(a, b):
    return f"%{round(100 * a / b)}" if b else ""


def build(player, lineup_row=None):
    """Yuvron lineups.starting/bench satiri -> kart verisi. None = gosterilecek veri yok."""
    p = player
    s = p.get("stats") or {}
    nm = (p.get("player") or {}).get("name", "")
    parts = nm.split()
    if not parts:
        return None
    first, last = " ".join(parts[:-1]), parts[-1]
    if len(parts) == 1:
        first, last = "", parts[0]
    g = lambda k: s.get(k) or 0
    rows, big = [], []
    if (p.get("position") or "").upper() == "GK":
        big = [(str(g("saves")), "KURTARIŞ"), (str(g("goalsConceded")), "YENEN GOL"),
               (f'{g("expectedGoalsPrevented"):+.2f}', "ÖNLENEN xG")]
        if g("penaltiesSaved"): rows.append(("Kurtarılan penaltı", str(g("penaltiesSaved"))))
    else:
        big = [(str(p.get("goals") or 0), "GOL"), (str(g("shots")), "ŞUT"), (f'{g("expectedGoalsOnTarget"):.2f}', "xGOT")]
        if p.get("assists"): rows.append(("Asist", str(p["assists"])))
        if g("keyPasses"): rows.append(("Kilit pas", str(g("keyPasses"))))
    if g("passesAttempted"):
        rows.append(("İsabetli pas", f'{g("passesCompleted")}/{g("passesAttempted")} ({_pct(g("passesCompleted"), g("passesAttempted"))})'))
    if g("passesIntoFinalThird"):
        rows.append(("Son üçte bire pas", str(g("passesIntoFinalThird"))))
    if g("groundDuelsAttempted"):
        rows.append(("Yer mücadelesi", f'{g("groundDuelsWon")}/{g("groundDuelsAttempted")}'))
    if g("aerialDuelsAttempted"):
        rows.append(("Hava mücadelesi", f'{g("aerialDuelsWon")}/{g("aerialDuelsAttempted")}'))
    if g("touches"): rows.append(("Topla buluşma", str(g("touches"))))
    dcon = g("tacklesWon") + g("interceptions") + g("clearances") + g("blocks")
    if dcon: rows.append(("Savunma katkısı", str(dcon)))
    if g("interceptions"): rows.append(("Pas arası", str(g("interceptions"))))
    if g("ballRecoveries"): rows.append(("Top kazanma", str(g("ballRecoveries"))))
    r = p.get("rating")
    return dict(first=first.title(), last=last.upper(), num=str(p.get("shirtNumber") or ""),
                rating=f"{r:.1f}" if isinstance(r, (int, float)) else "", big=big, rows=rows[:7], minutes=p.get("minutes"))


def _variant_h(t, D, match):
    im = _bg(t, .6); d = ImageDraw.Draw(im); _top(d, t, match)
    tx = Image.new("RGBA", (900, 230), (0, 0, 0, 0)); td = ImageDraw.Draw(tx)
    f = _fit(td, D["last"], BS, 200, 840, 90)
    td.text((0, 0), D["last"], font=f, fill=t["acc2"] + (255,))
    bb = tx.getbbox() or (0, 0, 1, 1); tx = tx.crop(bb).rotate(90, expand=True)
    im.paste(tx, (60, 1180 - tx.size[1] if tx.size[1] < 980 else 200), tx); d = ImageDraw.Draw(im)
    d.text((300, 200), D["first"], font=_fit(d, D["first"], BS, 64, 700, 36), fill=t["acc"])
    if D["rating"]:
        d.text((300, 270), D["rating"], font=BS(300), fill=t["acc"]); d.text((310, 580), "REYTİNG", font=PM(28), fill=t["txt"])
    for i, (v, l) in enumerate(D["big"]):
        x = 300 + i * 250; d.text((x, 680), v, font=BS(100), fill=t["acc2"]); d.text((x + 4, 790), l, font=PM(24), fill=t["acc"])
    y = 880
    for l, v in D["rows"][:6]:
        d.text((300, y), l, font=PM(27), fill=t["txt"]); _right(d, W - 80, y, v, PO(28), t["acc2"])
        d.line((300, y + 46, W - 80, y + 46), fill=t["line"]); y += 60
    return im


def _variant_m(t, D, match):
    im = _bg(t, .5)
    nb = Image.new("RGBA", im.size, (0, 0, 0, 0)); nd = ImageDraw.Draw(nb)
    num = D["num"] or ""
    if num:
        size = 1250 if len(num) == 1 else 640 if len(num) == 2 else 440
        nd.text((-40 if len(num) == 1 else 10, 60 if len(num) == 1 else 330), num, font=BS(size), fill=t["panel"] + (150,), stroke_width=4, stroke_fill=t["line"] + (255,))
    im = Image.alpha_composite(im.convert("RGBA"), nb).convert("RGB"); d = ImageDraw.Draw(im); _top(d, t, match)
    d.text((470, 200), D["first"], font=_fit(d, D["first"], BS, 70, 560, 36), fill=t["acc"])
    d.text((470, 262), D["last"], font=_fit(d, D["last"], BS, 130, 560, 60), fill=t["acc2"])
    if D["rating"]:
        d.rounded_rectangle((470, 430, 740, 600), 26, fill=t["acc"])
        _ct(d, 440, "REYTİNG", PM(22), t["c0"], 605); _ct(d, 468, D["rating"], BS(116), t["c0"], 605)
    y = 660
    items = [(l, v) for v, l in D["big"]]
    items = [("Gol", D["big"][0][0]), ("Şut", D["big"][1][0]), ("xGOT", D["big"][2][0])] if D["big"][0][1] == "GOL" else [(l.title(), v) for v, l in D["big"]]
    items += D["rows"]
    items = items[:9]
    d.line((490, y, 490, y + len(items) * 60 - 12), fill=t["acc"], width=3)
    for l, v in items:
        d.ellipse((482, y + 16, 498, y + 32), fill=t["acc"]); d.text((520, y + 4), l, font=PM(28), fill=t["txt"]); _right(d, W - 70, y + 2, v, PO(29), t["acc2"]); y += 60
    return im


def make(player, match, comp, out, variant=None):
    """player: Yuvron oyuncu kaydi. match: 'Galatasaray 2-0 Stuttgart'. comp: 'cl' | 'sl'. variant: 'H' | 'M' (None = oyuncu id'sine gore)."""
    D = build(player)
    if not D:
        return None
    t = TH["cl" if comp == "cl" else "sl"]
    if variant not in ("H", "M"):
        variant = "H" if (int((player.get("player") or {}).get("id") or 0) % 2 == 0) else "M"
    im = (_variant_h if variant == "H" else _variant_m)(t, D, match)
    im.save(out)
    return out


if __name__ == "__main__":
    # ornek veri (Batrakov, gercek degil)
    P = dict(player=dict(id=1, name="Aleksey Batrakov"), shirtNumber=83, position="CM", minutes=90, rating=8.8, goals=2, assists=0,
             stats=dict(touches=37, shots=3, shotsOnTarget=3, expectedGoalsOnTarget=0.74, passesCompleted=19, passesAttempted=23, passesIntoFinalThird=10,
                        groundDuelsWon=3, groundDuelsAttempted=3, tacklesWon=1, interceptions=2, clearances=0, blocks=0, ballRecoveries=4))
    for c in ("cl", "sl"):
        for v in ("H", "M"):
            make(P, "Galatasaray 2-0 Stuttgart", c, f"/tmp/claude-0/-home-claude/d5165a86-1578-550f-abe3-2f22a82e8aa9/scratchpad/perf/pk_{v}_{c}.png", v)
