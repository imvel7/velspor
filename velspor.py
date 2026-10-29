"""Vel Spor haber botu (tek dosya).

Normal calisma: haberleri tarar, gorsele cevirir, Telegram'a yollar.
HEADLINE ortam degiskeni doluysa: elle kart uretir.
"""
import html
import json
import os
import random
import re
import sys
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus

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


# ---------------- siniflandirma ----------------

def tr_lower(s):
    return s.replace("İ", "i").replace("I", "ı").lower()


# Sira onemli: ustteki kural once denenir.
RULES = [
    ("Disiplin ve Ceza", r"pfdk|disipline sevk|\bceza|kırmızı kart|sarı kart|hak mahrumiyeti"),
    ("Sakatlık", r"sakatl|\bsakat\b|ameliyat|tedavi|kas yırtığı|sezonu kapattı|dönüş tarihi|forma giyemeyecek"),
    ("Özel Gün", r"doğum günü|yıl dönümü|anıyoruz|rahmetle|vefat|hatırlıyoruz"),
    ("Transfer", r"transfer|bonservis|imzay|imza at|kiralık|teklif|ilgileniyor|sözleşme|anlaşma sağla|anlaştı|takip ediyor"),
    ("Avrupa", r"uefa|şampiyonlar ligi|avrupa ligi|konferans ligi|\bkura\b"),
    ("Maç Öncesi", r"hakem|ilk 11|muhtemel 11|maç kadrosu|saat kaçta|hangi kanalda|şifresiz|maç öncesi"),
    ("Puan Durumu", r"puan durumu|puan farkı|liderlik|şampiyonluk yarışı|averaj"),
    ("Antrenman", r"antrenman|idman|\bkamp"),
    ("Taraftar ve Stadyum", r"bilet|taraftar|kombine|tribün|stadyum|koreografi|deplasman yasağı"),
    ("Kulüp ve Yönetim", r"başkan|yönetim|\bkap\b|resmi açıklama|sponsor|kongre|divan|kulüpten"),
    ("Oyuncu Performansı", r"asist|istatistik|rekor|gol sayısı|maçın adamı|maçın oyuncusu|gol krallığı|performans"),
    ("Maç İçi", r"\bgol(ü|le|ler|ünü)?\b|penaltı|\bvar\b|maç sonucu|maç sona erdi|ilk yarı|devre arası|canlı anlatım"),
    ("Açıklamalar", r"açıklama|konuştu|röportaj|basın toplantısı|\bdedi\b|okan buruk"),
]

OFFICIAL = re.compile(r"resmen|resmi olarak|imzayı attı|imzaladı|kap'a|kap’a|duyurdu|açıkladı|açıklandı")
CLAIM = re.compile(
    r"iddia|kulis|ilgileniyor|takip ediyor|gündemde|gelebilir|sürpriz|\?|görüşme|istiyor|peşinde|masada|hedefte|yakın|"
    r"gelecek mi|ayrılacak mı|olabilir|bekleniyor|haberleri"
)
BREAKING = re.compile(r"son dakika|resmen|ilk 11|kırmızı kart|imzayı attı|ameliyat edildi|ayrıldı")


def classify(title, hint=None):
    t = tr_lower(title)
    for cat, pattern in RULES:
        if re.search(pattern, t):
            return cat
    return hint or "Gündem"


def is_claim(title, category, official_source):
    if official_source:
        return False
    t = tr_lower(title)
    if OFFICIAL.search(t):
        return False
    if category == "Transfer":
        return True  # resmi dil yoksa transfer haberi 'iddia' sayilir
    return bool(CLAIM.search(t))


def level_for(title, category, claim):
    t = tr_lower(title)
    if category == "Özel Gün":
        return "C"
    if claim and "son dakika" not in t:
        return "B"
    if category == "Maç İçi" or BREAKING.search(t):
        return "A"
    return "B"


# ---------------- kaynaklar ----------------
# official: kulup/federasyon gibi resmi kaynak (haber 'iddia' sayilmaz)
# filter:   True ise sadece icinde 'Galatasaray' gecen haberler alinir
# hint:     siniflandirici kategori bulamazsa kullanilacak kategori

GN = "https://news.google.com/rss/search?q={q}&hl=tr&gl=TR&ceid=TR:tr"


def gn(query):
    return GN.format(q=quote_plus(query + " when:1d"))


FEEDS = [
    dict(name="Galatasaray SK", url="https://www.galatasaray.org/xml/gs.rss", official=True, filter=False, hint=None),
    dict(name="A Spor", url="https://www.aspor.com.tr/rss/galatasaray.xml", official=False, filter=False, hint=None),
    dict(name="Fotomaç", url="https://www.fotomac.com.tr/rss/Galatasaray.xml", official=False, filter=False, hint=None),
    dict(name="Ajansspor", url="https://ajansspor.com/rss", official=False, filter=True, hint=None),
    # Google Haberler: her arama bir kategoriye denk gelir
    dict(name="Google Haberler: son dakika", url=gn("Galatasaray son dakika"), official=False, filter=False, hint=None),
    dict(name="Google Haberler: hakem", url=gn("Galatasaray maçının hakemi"), official=False, filter=False, hint="Maç Öncesi"),
    dict(name="Google Haberler: ilk 11", url=gn("Galatasaray ilk 11 maç kadrosu"), official=False, filter=False, hint="Maç Öncesi"),
    dict(name="Google Haberler: transfer", url=gn("Galatasaray transfer"), official=False, filter=False, hint="Transfer"),
    dict(name="Google Haberler: sakatlık", url=gn("Galatasaray sakatlık ceza oyuncu"), official=False, filter=False, hint="Sakatlık"),
    dict(name="Google Haberler: yönetim", url=gn("Galatasaray yönetim resmi açıklama"), official=False, filter=False, hint="Kulüp ve Yönetim"),
    dict(name="Google Haberler: antrenman", url=gn("Galatasaray antrenman hazırlıkları"), official=False, filter=False, hint="Antrenman"),
    dict(name="Google Haberler: taraftar", url=gn("Galatasaray bilet taraftar stadyum"), official=False, filter=False, hint="Taraftar ve Stadyum"),
    dict(name="Google Haberler: açıklama", url=gn("Galatasaray Okan Buruk açıklama"), official=False, filter=False, hint="Açıklamalar"),
    dict(name="Google Haberler: puan durumu", url=gn("Galatasaray puan durumu"), official=False, filter=False, hint="Puan Durumu"),
    dict(name="Google Haberler: Avrupa", url=gn("Galatasaray UEFA Avrupa"), official=False, filter=False, hint="Avrupa"),
]


# ---------------- RSS okuyucu ----------------

UA = "Mozilla/5.0 (compatible; VelSporBot/1.0)"
TAG_RE = re.compile(r"<[^>]+>")


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _text(el):
    return (el.text or "").strip() if el is not None else ""


def _clean(s):
    return html.unescape(TAG_RE.sub(" ", s or "")).replace("\xa0", " ").strip()


def _parse_date(s):
    if not s:
        return None
    try:
        dt = parsedate_to_datetime(s)
    except Exception:
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def rss_parse(xml_bytes):
    root = ET.fromstring(xml_bytes)
    items = []
    for el in root.iter():
        name = _local(el.tag)
        if name not in ("item", "entry"):
            continue
        d = {"title": "", "link": "", "id": "", "summary": "", "date": None, "source": ""}
        for ch in el:
            n = _local(ch.tag)
            if n == "title":
                d["title"] = _clean(_text(ch))
            elif n == "link":
                d["link"] = (ch.get("href") or _text(ch)).strip()
            elif n in ("guid", "id"):
                d["id"] = _text(ch)
            elif n in ("description", "summary", "content"):
                d["summary"] = _clean(_text(ch))[:400]
            elif n in ("pubDate", "published", "updated", "date"):
                if d["date"] is None:
                    d["date"] = _parse_date(_text(ch))
            elif n == "source":
                d["source"] = _clean(_text(ch))
        if d["title"]:
            d["id"] = d["id"] or d["link"] or d["title"]
            items.append(d)
    return items


def rss_fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return rss_parse(resp.read())


# ---------------- Telegram ----------------

def _clean_secret(s):
    # gorunmez karakterleri at
    return re.sub(r"[^\x21-\x7e]", "", s or "")


def _creds():
    token = _clean_secret(os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    chat = _clean_secret(os.environ.get("TELEGRAM_CHAT_ID", ""))
    if not token or not chat:
        raise RuntimeError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID tanimli degil")
    return token, chat


def tg_configured():
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


def tg_send_message(text):
    token, chat = _creds()
    data = json.dumps({"chat_id": chat, "text": text[:4000], "disable_web_page_preview": True}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data, headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def tg_send_photo(path, caption):
    token, chat = _creds()
    boundary = uuid.uuid4().hex
    body = b""

    def field(name, value):
        return (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n").encode()

    body += field("chat_id", chat)
    body += field("caption", caption[:1000])
    with open(path, "rb") as f:
        img = f.read()
    body += (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"haber.png\"\r\n"
        f"Content-Type: image/png\r\n\r\n"
    ).encode() + img + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendPhoto",
        data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


# ---------------- ana akis ----------------

STATE = ROOT / "state" / "seen.json"
OUT = ROOT / "out"

MAX_PER_RUN = 6      # tek calismada en fazla kac gorsel
MAX_FIRST_RUN = 3    # ilk calismada kac gorsel (geri kalani sessizce 'goruldu' isaretlenir)
MAX_AGE_HOURS = 12   # bundan eski haberler atlanir
MAX_TITLE = 95


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=0), encoding="utf-8")


def tokens(title):
    return {w for w in re.findall(r"\w+", tr_lower(title)) if len(w) > 2}


def similar(a, b):
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= 0.6


def short_title(t):
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) <= MAX_TITLE:
        return t
    cut = t[:MAX_TITLE].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:-") + "…"


def collect(feed):
    """Bir kaynaktan haberleri al. (haberler, hata) dondurur."""
    try:
        raw = rss_fetch(feed["url"])
    except Exception as e:  # noqa: BLE001
        return [], f"{type(e).__name__}: {e}"
    now = datetime.now(timezone.utc)
    out = []
    for it in raw:
        title = it["title"]
        source = feed["name"]
        if "news.google.com" in feed["url"]:
            if it["source"]:
                source = it["source"]
                suffix = " - " + it["source"]
                if title.endswith(suffix):
                    title = title[: -len(suffix)]
            elif " - " in title:
                title, source = title.rsplit(" - ", 1)
        if feed["filter"] and "galatasaray" not in tr_lower(title + " " + it["summar