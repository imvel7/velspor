"""RSS okuyucu ve Telegram gonderici (dis paket gerektirmez)."""
import json
import os
import uuid
import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

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
