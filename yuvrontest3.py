"""Yuvron 3. test (Sampiyonlar Ligi): oyuncu verisi var mi? En fazla 6 istek. Anahtar yazdirilmaz."""
import json, os, sys, time, urllib.request, urllib.error
KEY = os.environ.get("YUVRON_KEY", "").strip()
H = "champions-league4.p.rapidapi.com"
def get(path):
    time.sleep(2)
    r = urllib.request.Request(f"https://{H}{path}", headers={"X-RapidAPI-Key": KEY, "X-RapidAPI-Host": H, "User-Agent": "velspor"})
    try:
        with urllib.request.urlopen(r, timeout=30) as x:
            return x.status, json.loads(x.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:200]
    except Exception as e:  # noqa: BLE001
        return 0, str(e)[:200]
if not KEY:
    sys.exit("YUVRON_KEY yok")
s, d = get("/matches")
rows = [m for m in (d.get("data") or []) if "galatasaray" in json.dumps(m, ensure_ascii=False).lower()] if s == 200 else []
print("Galatasaray maclari:")
for m in rows:
    print(" ", m["id"], m.get("kickoff"), m.get("status"), m["homeTeam"]["name"], m["score"], m["awayTeam"]["name"])
done = [m for m in rows if str(m.get("status")).lower() in ("finished", "ft", "full_time", "ended", "completed")] or rows
if not done:
    sys.exit("mac yok")
mid = done[0]["id"]
s, d = get(f"/matches/{mid}")
print("DETAY", mid, s)
if s == 200:
    dd = d["data"]
    for side in ("home", "away"):
        st = (dd.get("lineups") or {}).get(side, {}).get("starting") or []
        print(side, "ilk 11 adet:", len(st))
        if st:
            print(side, "ilk oyuncu ornegi:", json.dumps(st[0], ensure_ascii=False)[:1500])
            break
    print("olay ornegi:", json.dumps((dd.get("events") or [])[:3], ensure_ascii=False)[:800])
    print("detay ust anahtarlar:", list(dd.keys()))
for p in (f"/matches/{mid}/players", f"/matches/{mid}/stats"):
    s, d = get(p)
    print(p, "HTTP", s, json.dumps(d, ensure_ascii=False)[:600])
