"""4:5 dikey kartlar (1080x1350): gol, ilk 11, hava durumu."""
import random

from PIL import Image, ImageDraw

from render import PAL, draw_text, fit, font, footer, paste_logo, spaced, tr_upper, tw, wrap

W, H = 1080, 1350


def bg(p, seed=11):
    mask = Image.radial_gradient("L").resize((W, H)).point(lambda v: 255 - v)
    img = Image.composite(Image.new("RGB", (W, H), p["light"]), Image.new("RGB", (W, H), p["dark"]), mask)
    px = img.load()
    rnd = random.Random(seed)
    for _ in range(150000):
        x, y = rnd.randrange(W), rnd.randrange(H)
        dd = rnd.randint(-9, 6)
        r, g, b = px[x, y]
        px[x, y] = (max(0, min(255, r + dd)), max(0, min(255, g + dd)), max(0, min(255, b + dd)))
    return img


def overlay(img, draw_fn):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(ov))
    img.paste(Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB"))


def rings(img, p, cx, cy, step=150, count=10, alpha=60):
    def f(d):
        for i in range(1, count + 1):
            r = i * step
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=p["line"] + (alpha,), width=2)
    overlay(img, f)


def header(img, p, left, right):
    spaced(img, 70, 62, left, 24, p["small"], gap=7)
    spaced(img, W - 70, 62, right, 24, p["small"], gap=7, anchor="r")
    ImageDraw.Draw(img).line([(70, 102), (W - 70, 102)], fill=p["line"], width=2)


def fit_one(text, maxw, start, minsize=30):
    size = start
    while size > minsize and tw(text, size) > maxw:
        size -= 2
    return size


# ---------------- GOL ----------------

def make_goal(home, away, hs, as_, minute, scorer, scoring_side, out):
    p = PAL["BURG"]
    img = bg(p, 21)
    rings(img, p, 540, 520, step=170, count=8)
    header(img, p, "GALATASARAY", "MAÇ İÇİ · SON DAKİKA")
    size = 560
    while tw("GOL", size) > 900:
        size -= 6
    draw_text(img, W // 2, 110, "GOL", size, p["text"], anchor="m")
    draw_text(img, W // 2, 610, f"{minute}'", 200, p["text"], anchor="m")
    name = tr_upper(scorer)
    draw_text(img, W // 2, 800, name, fit_one(name, 900, 170), p["text"], anchor="m")
    ImageDraw.Draw(img).line([(W // 2 - 70, 985), (W // 2 + 70, 985)], fill=p["text"], width=4)
    # skor satiri
    hn, an = tr_upper(home), tr_upper(away)
    ys = 1040
    hcol = p["text"] if scoring_side == "home" else p["small"]
    acol = p["text"] if scoring_side == "away" else p["small"]
    sh = fit_one(hn, 330, 64)
    sa = fit_one(an, 330, 64)
    draw_text(img, 400, ys + 20, hn, sh, hcol, anchor="r")
    draw_text(img, 680, ys + 20, an, sa, acol)
    draw_text(img, W // 2, ys - 6, f"{hs}-{as_}", 120, p["text"], anchor="m")
    footer(img, p, None, y=1255, h=70)
    spaced(img, W - 70, 1255 + 35 - 12, "CANLI", 22, p["small"], gap=7, anchor="r")
    img.save(out)


# ---------------- ILK 11 ----------------

def make_lineup(home, away, players, coach, subs, out, title="İLK 11", extra=""):
    p = PAL["BURG"]
    img = bg(p, 31)
    rings(img, p, 900, 300, step=160, count=9)
    paste_logo(img, 820, (500, 250), p["line"], alpha=80)
    header(img, p, "GALATASARAY", "MAÇ KADROSU")
    size = 210
    while tw(title, size) > 900:
        size -= 6
    draw_text(img, 70, 110, title, size, p["text"])
    spaced(img, 74, 322, f"{tr_upper(home)}  –  {tr_upper(away)}" + (f"   ·   {extra}" if extra else ""), 24, p["small"], gap=7)
    y0, step = 368, 60
    f_num = font(34, False)
    d = ImageDraw.Draw(img)
    for i, (num, name, cap) in enumerate(players):
        y = y0 + i * step
        d.text((72, y + 18), str(num), font=f_num, fill=p["small"])
        w = draw_text(img, 150, y, tr_upper(name), 58, p["text"])
        if cap:
            d.text((150 + w + 14, y + 20), "(K)", font=font(36), fill=p["small"])
    y = y0 + len(players) * step + 10
    d.text((72, y + 18), "TD", font=f_num, fill=p["small"])
    draw_text(img, 150, y, tr_upper(coach), 58, p["text"])
    y += 80
    spaced(img, 74, y, "YEDEKLER", 22, p["text"], gap=7)
    d.line([(70, y + 36), (520, y + 36)], fill=p["line"], width=2)
    lines = wrap(", ".join(subs), 30, 440 / 0.8) if False else []
    # yedekleri iki satira yay
    half = (len(subs) + 1) // 2
    for k, chunk in enumerate([subs[:half], subs[half:]]):
        d.text((72, y + 50 + k * 32), ", ".join(chunk), font=font(32, False), fill=p["small"])
    footer(img, p, None, y=1272, h=54)
    img.save(out)


# ---------------- HAVA DURUMU ----------------

def weather_fx(img, p, rain, snow):
    rnd = random.Random(5)

    def f(d):
        if rain:
            for _ in range(300):
                x, y, ln = rnd.randrange(-40, W), rnd.randrange(-40, H), rnd.randint(24, 64)
                d.line([(x, y), (x - ln * 0.28, y + ln)], fill=p["line"] + (110,), width=rnd.choice((2, 2, 3)))
        if snow:
            for _ in range(180):
                x, y, r = rnd.randrange(W), rnd.randrange(H), rnd.randint(2, 6)
                d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 120))
    overlay(img, f)


def icon(d, kind, cx, y, col):
    if kind == "temp":
        d.rounded_rectangle([cx - 8, y, cx + 8, y + 42], radius=8, outline=col, width=4)
        d.ellipse([cx - 17, y + 34, cx + 17, y + 68], outline=col, width=4)
        d.line([(cx, y + 18), (cx, y + 50)], fill=col, width=5)
    elif kind == "wind":
        for yy, ln in [(y + 12, 60), (y + 32, 74), (y + 52, 52)]:
            d.line([(cx - 38, yy), (cx - 38 + ln, yy)], fill=col, width=4)
            d.arc([cx - 38 + ln - 16, yy - 16, cx - 38 + ln + 8, yy + 8], 270, 90, fill=col, width=4)
    else:
        for dx, dy, sz in [(-16, 10, 22), (12, 0, 28)]:
            d.polygon([(cx + dx, y + dy), (cx + dx - sz // 2, y + dy + sz), (cx + dx + sz // 2, y + dy + sz)], outline=col, width=4)
            d.ellipse([cx + dx - sz // 2, y + dy + sz // 2 + 2, cx + dx + sz // 2, y + dy + sz + sz // 2 + 2], outline=col, width=4)


def stat(img, cx, y, value, unit, label, kind, p):
    d = ImageDraw.Draw(img)
    icon(d, kind, cx, y, p["text"])
    spaced(img, cx, y + 90, label, 22, p["text"], gap=6, anchor="m")
    v = str(value)
    wv = tw(v, 130)
    wu = tw(unit, 52) if unit else 0
    x0 = cx - (wv + wu + 8) / 2
    draw_text(img, x0, y + 120, v, 130, p["text"])
    if unit:
        draw_text(img, x0 + wv + 8, y + 146, unit, 52, p["text"])


def team_name(img, cx, name, p):
    name = tr_upper(name)
    size = 72
    while size > 34 and (len(wrap(name, size, 300)) > 2 or max(tw(l, size) for l in wrap(name, size, 300)) > 300):
        size -= 2
    lines = wrap(name, size, 300)
    top = 450 + (2 - len(lines)) * (size // 2)
    for i, l in enumerate(lines):
        draw_text(img, cx, top + i * size, l, size, p["text"], anchor="m")


def make_weather(home, away, stadium, hhmm, date_text, w, out):
    p = PAL["BURG"]
    img = bg(p, 41)
    rings(img, p, 300, 330, step=160, count=10, alpha=55)
    paste_logo(img, 520, (700, 840), p["line"], alpha=45)
    weather_fx(img, p, w["rain"], w["snow"])
    header(img, p, "GALATASARAY", "MAÇ GÜNÜ")
    size = 250
    while tw("HAVA DURUMU", size) > 900:
        size -= 4
    draw_text(img, W // 2, 118, "HAVA DURUMU", size, p["text"], anchor="m")
    team_name(img, 220, home, p)
    team_name(img, 860, away, p)
    paste_logo(img, 110, (W // 2 - 60, 430), p["text"])
    spaced(img, W // 2, 610, tr_upper(stadium), 28, p["small"], gap=7, anchor="m")
    spaced(img, W // 2, 690, "MAÇ SAATİ", 24, p["text"], gap=7, anchor="m")
    draw_text(img, W // 2, 722, hhmm.replace(":", "."), 210, p["text"], anchor="m")
    stat(img, 190, 960, w["temp"], "°C", "SICAKLIK", "temp", p)
    stat(img, 540, 960, w["wind"], "KM/SA", "RÜZGAR HIZI", "wind", p)
    stat(img, 890, 960, "%" + str(w["hum"]), "", "NEM", "hum", p)
    footer(img, p, None, y=1262, h=60)
    spaced(img, W - 70, 1262 + 30 - 12, tr_upper(date_text), 22, p["small"], gap=6, anchor="r")
    img.save(out)
