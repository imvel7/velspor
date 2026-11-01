"""Habere gore paylasilabilir tweet metni uretir (haber sayfasindan 1-2 cumle)."""
import html
import re
import urllib.request

from rules import clean_title, tr_lower

UA = "Mozilla/5.0 (compatible; VelSporBot/1.0)"
LIMIT = 270
TAG = "#Galatasaray"
JUNK = ("abone", "tıkla", "reklam", "haberi oku", "devamı", "çerez", "whatsapp", "telegram",
        "kanalımıza", "takip edin", "paylaş", "fotoğraf:", "foto:", "©", "son dakika haberleri",
        "yorum", "giriş yap", "bültenimize")


def _txt(s):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).replace("\xa0", " ").strip()


def fetch_paragraphs(url, timeout=15):
    """Haber sayfasindan paragraflari al; hata olursa bos liste."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "tr"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(700_000).decode("utf-8", "ignore")
    except Exception as e:  # noqa: BLE001
        print("Sayfa okunamadi:", str(e)[:80])
        return []
    return parse_paragraphs(raw)


def parse_paragraphs(raw):
    out = []
    m = re.search(r'<meta[^>]+(?:property="og:description"|name="description")[^>]+content="([^"]+)"', raw, re.I)
    if m:
        out.append(_txt(m.group(1)))
    art = re.search(r"<article.*?</article>", raw, re.S | re.I)
    body = art.group(0) if art else raw
    for p in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S | re.I):
        t = _txt(p)
        if len(t) >= 40:
            out.append(t)
    return out


def sentences(par):
    return [s.strip() for s in re.split(r"(?<=[.!?…])\s+(?=[A-ZÇĞİÖŞÜ0-9\"“'‘])", par) if s.strip()]


def _words(s):
    return {w[:4] for w in re.findall(r"\w+", tr_lower(s)) if len(w) > 2}


def build_post(title, summary, paragraphs, claim=False):
    """Baslik + 1-2 kisa cumle + etiket. Kaynak/link metne konmaz."""
    title = clean_title(title).strip()
    tw = _words(title)
    cand = []
    for par in list(paragraphs) + ([summary] if summary else []):
        for s in sentences(par):
            low = tr_lower(s)
            if len(s) < 35 or len(s) > 220 or any(j in low for j in JUNK):
                continue
            sw = _words(s)
            if tw and len(sw & tw) / max(1, len(sw | tw)) > 0.6:
                continue  # basligin tekrari
            if s not in cand:
                cand.append(s)
    head = title + "\n\n"
    tail = "\n\n" + TAG
    room = LIMIT - len(head) - len(tail)
    body = ""
    for s in cand[:4]:
        nxt = (body + " " + s).strip()
        if len(nxt) <= room:
            body = nxt
        if len(body) > 0 and len(nxt) > room:
            break
        if body.count(".") + body.count("!") + body.count("?") >= 2:
            break
    if not body:
        return (title + tail)[:LIMIT + 10]
    return head + body + tail
