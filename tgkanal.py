"""Herkese acik Telegram kanallarini (t.me/s/<kanal>) okur; mesajlari haber maddesine cevirir."""
import html
import re
import urllib.request
from datetime import datetime, timedelta, timezone

UA = "Mozilla/5.0 (compatible; VelSporBot/1.0)"


def _clean(s):
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</(p|div)>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def parse(raw, channel):
    """HTML -> [{post, text, ts, link, fwd}] (yeniden eskiye degil, sayfa sirasinda)."""
    out = []
    parts = re.split(r'(?=<div class="tgme_widget_message_wrap)', raw)
    for p in parts:
        m = re.search(r'data-post="([^"]+)"', p)
        if not m:
            continue
        post = m.group(1)
        tm = re.search(r'<time[^>]+datetime="([^"]+)"', p)
        try:
            ts = datetime.fromisoformat(tm.group(1)).timestamp() if tm else 0
        except ValueError:
            ts = 0
        tx = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', p, re.S)
        text = _clean(tx.group(1)) if tx else ""
        fw = re.search(r'tgme_widget_message_forwarded_from_name[^>]*>(.*?)</(?:a|span)>', p, re.S)
        out.append(dict(post=post, text=text, ts=ts, link=f"https://t.me/{post}", fwd=_clean(fw.group(1)) if fw else ""))
    return out


def _title(text):
    first = re.sub(r"#\w+", "", text.split("\n")[0])
    first = re.sub(r"^[^\wÇĞİÖŞÜçğıöşü\"“']+", "", first).strip()
    return first[:140] if first else text[:140]


def collect_channel(name, max_age_h=12, timeout=20):
    """(maddeler, hata). Madde alanlari velspor.collect ile ayni + text, tg=True."""
    try:
        req = urllib.request.Request(f"https://t.me/s/{name}", headers={"User-Agent": UA, "Accept-Language": "tr"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(1_500_000).decode("utf-8", "ignore")
    except Exception as e:  # noqa: BLE001
        return [], f"{type(e).__name__}: {str(e)[:60]}"
    if "tgme_widget_message_wrap" not in raw:
        return [], "mesaj yok (kanal herkese acik degil olabilir)"
    now = datetime.now(timezone.utc)
    items = []
    for m in parse(raw, name):
        if len(m["text"]) < 40:
            continue  # sadece resim/cok kisa
        if m["ts"] and now.timestamp() - m["ts"] > max_age_h * 3600:
            continue
        items.append(dict(
            id=f"tg:{m['post']}", title=_title(m["text"]), link=m["link"],
            source=m["fwd"] or f"@{name}", ts=m["ts"] or now.timestamp(),
            hint=None, official=False, text=m["text"], tg=True, channel=name,
        ))
    return items, None
