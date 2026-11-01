"""Highlightly futbol API istemcisi (anahtar asla yazdirilmaz)."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://sports.highlightly.net"
KEY = "".join(c for c in os.environ.get("HIGHLIGHTLY_KEY", "") if 33 <= ord(c) <= 126)
COUNT = 0
_hdr = None


class ApiError(Exception):
    pass


def _once(url, name):
    h = {"User-Agent": "VelSporBot/1.0", "Accept": "application/json"}
    if name == "bearer":
        h["Authorization"] = "Bearer " + KEY
    else:
        h[name] = KEY
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=25) as r:
        return json.loads(r.read())


def get(path, **params):
    """GET. Dogru baslik adini kendi bulur ve hatirlar."""
    global _hdr, COUNT
    if not KEY:
        raise ApiError("HIGHLIGHTLY_KEY bos")
    params = {k: v for k, v in params.items() if v not in (None, "")}
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    names = [_hdr] if _hdr else ["x-rapidapi-key", "x-api-key", "bearer"]
    last = None
    for name in names:
        for attempt in range(2):
            try:
                data = _once(url, name)
                _hdr = name
                COUNT += 1
                return data
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code}"
                if e.code in (401, 403) and not _hdr:
                    break  # baska baslik dene
                if e.code == 429:
                    raise ApiError("istek limiti (429)")
                if e.code >= 500 and attempt == 0:
                    time.sleep(3)
                    continue
                raise ApiError(last)
            except Exception as e:  # noqa: BLE001
                last = str(e)[:80]
                if attempt == 0:
                    time.sleep(3)
                    continue
                raise ApiError(last)
    raise ApiError(last or "bilinmeyen hata")


def rows(d):
    """Cevaptan liste cikar: dogrudan liste ya da {'data': [...]}"""
    if isinstance(d, list):
        return d
    if isinstance(d, dict):
        x = d.get("data")
        if isinstance(x, list):
            return x
        if isinstance(x, dict):
            return [x]
    return []


def one(d):
    if isinstance(d, dict) and "data" not in d:
        return d
    r = rows(d)
    return r[0] if r else {}
