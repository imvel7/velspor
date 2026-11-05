"""Yuvron API testi (tek seferlik, sadece okur). En fazla 8 istek harcar."""
import json, os, sys, time, urllib.request, urllib.error
KEY = os.environ.get("YUVRON_KEY", "").strip()
HOSTS = ["football-leagues1.p.rapidapi.com", "super-lig.p.rapidapi.com", "champions-league4.p.rapidapi.com"]
out, calls = [], 0

def get(host, path):
    global calls
    calls += 1
    time.sleep(2)
    r = urllib.request.Request(f"https://{host}{path}", headers={"X-RapidAPI-Key": KEY, "X-RapidAPI-Host": host, "User-Agent": "velspor"})
    try:
        with urllib.request.urlopen(r, timeout=30) as x:
            return x.status, json.loads(x.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:200]
    except Exception as e:  # noqa: BLE001
        return 0, str(e)[:200]

def shape(o, d=0):
    if isinstance(o, dict):
        return {k: shape(v, d + 1) if d < 3 else "..." for k, v in list(o.items())[:30]}
    if isinstance(o, list):
        return [shape(o[0], d + 1)] if o else []
    return type(o).__name__

def find(o, acc):
    if isinstance(o, dict):
        if "galatasaray" in json.dumps(o, ensure_ascii=False)[:600].lower() and any(k in o for k in ("id", "matchId")):
            acc.append(o)
        else:
            for v in o.values():
                find(v, acc)
    elif isinstance(o, list):
        for v in o:
            find(v, acc)

if not KEY:
    print("YUVRON_KEY yok"); sys.exit(1)
for host in HOSTS:
    out.append(f"== {host}")
    for p in ("/matches", "/fixtures"):
        s, d = get(host, p)
        out.append(f"{p}: HTTP {s}")
        if s == 200:
            acc = []; find(d, acc)
            out.append("yapi: " + json.dumps(shape(d), ensure_ascii=False)[:700])
            out.append(f"Galatasaray eslesmesi: {len(acc)}")
            if acc:
                mid = acc[0].get("id") or acc[0].get("matchId")
                s2, d2 = get(host, f"/matches/{mid}")
                out.append(f"/matches/{mid}: HTTP {s2}")
                if s2 == 200:
                    out.append("detay yapi: " + json.dumps(shape(d2), ensure_ascii=False)[:1500])
            break
        else:
            out.append(str(d)[:150])
            if s == 403:
                break
    if calls >= 8:
        break
txt = "\n".join(out)
print(txt.replace(KEY, "***"))
