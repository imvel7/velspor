"""API-Football ucretsiz plan testi: ne geliyor, ne gelmiyor. Anahtar yazdirilmaz."""
import json
import os
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

from net import tg_configured, tg_send_message

BASE = "https://v3.football.api-sports.io"
KEY = "".join(c for c in os.environ.get("API_FOOTBALL_KEY", "") if 33 <= ord(c) <= 126)
LOG = []


def say(s):
    print(s)
    LOG.append(s)


def get(path, **params):
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"x-apisports-key": KEY, "User-Agent": "VelSporBot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        return {"errors": {"http": str(e)[:80]}, "response": []}


def errs(d):
    e = d.get("errors")
    return e if e else None


def main():
    if not KEY:
        say("API_FOOTBALL_KEY bos")
        return 1
    st = get("/status")
    r = st.get("response") or {}
    if isinstance(r, list):
        r = r[0] if r else {}
    sub, rq = r.get("subscription", {}), r.get("requests", {})
    say(f"Plan: {sub.get('plan')} | Kullanilan: {rq.get('current')}/{rq.get('limit_day')}")
    if errs(st):
        say(f"Status hatasi: {errs(st)}")
        return 1

    t = get("/teams", search="galatasaray")
    team = None
    for x in t.get("response", []):
        if x["team"]["name"].lower().startswith("galatasaray") and not x["team"].get("national"):
            team = x["team"]
            break
    if not team:
        say(f"Takim bulunamadi: {errs(t)}")
        return 1
    tid = team["id"]
    say(f"Takim: {team['name']} (id {tid})")

    # son maclar: farkli yollari dene
    fx, how = [], None
    today = datetime.now(timezone.utc).date()
    tries = [
        ("last=3", dict(team=tid, last=3)),
        ("son 20 gun", dict(team=tid, **{"from": str(today - timedelta(days=20)), "to": str(today)}, season=today.year if today.month >= 7 else today.year - 1)),
        ("sezon", dict(team=tid, season=today.year if today.month >= 7 else today.year - 1)),
    ]
    for name, p in tries:
        d = get("/fixtures", **p)
        if d.get("response"):
            fx, how = d["response"], name
            break
        say(f"Fikstur ({name}) bos/hatali: {errs(d)}")
    if not fx:
        say("Fikstur alinamadi")
        return finish()
    say(f"Fikstur yontemi: {how}, {len(fx)} mac")
    done = [f for f in fx if f["fixture"]["status"]["short"] in ("FT", "AET", "PEN")]
    done.sort(key=lambda f: f["fixture"]["timestamp"])
    nxt = [f for f in fx if f["fixture"]["status"]["short"] in ("NS", "TBD")]
    if nxt:
        n = min(nxt, key=lambda f: f["fixture"]["timestamp"])
        say(f"Siradaki mac: {n['teams']['home']['name']} - {n['teams']['away']['name']} {n['fixture']['date'][:16]}")
    if not done:
        say("Biten mac yok")
        return finish()
    m = done[-1]
    fid = m["fixture"]["id"]
    say(f"Test maci: {m['teams']['home']['name']} {m['goals']['home']}-{m['goals']['away']} {m['teams']['away']['name']}")

    d = get("/fixtures", id=fid)
    ev = (d.get("response") or [{}])[0].get("events", [])
    say(f"Olay sayisi: {len(ev)}")
    c = Counter((e["type"], e["detail"]) for e in ev)
    for (a, b), n in sorted(c.items()):
        say(f"  {a} / {b}: {n}")
    asist = [e for e in ev if e["type"] == "Goal" and (e.get("assist") or {}).get("name")]
    say(f"Asisti olan gol: {len(asist)}")
    if errs(d):
        say(f"Olay hatasi: {errs(d)}")

    ln = get("/fixtures/lineups", fixture=fid)
    say(f"Kadro verisi: {'var' if ln.get('response') else 'yok'} {errs(ln) or ''}")
    pl = get("/fixtures/players", fixture=fid)
    pr = pl.get("response") or []
    rated = 0
    for team_ in pr:
        for p in team_.get("players", []):
            if (p["statistics"][0]["games"] or {}).get("rating"):
                rated += 1
    say(f"Oyuncu performansi (puanli oyuncu): {rated} {errs(pl) or ''}")

    lv = get("/fixtures", live="all")
    say(f"Canli mac listesi: {len(lv.get('response') or [])} mac {errs(lv) or ''}")
    return finish()


def finish():
    st = get("/status")
    r = st.get("response") or {}
    if isinstance(r, list):
        r = r[0] if r else {}
    say(f"Test sonrasi kullanilan istek: {r.get('requests', {}).get('current')}")
    if tg_configured():
        tg_send_message("API testi:\n" + "\n".join(LOG))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
