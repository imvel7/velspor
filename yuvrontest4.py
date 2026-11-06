"""Yuvron 4. test: sayfalama ve en yeni mac. Anahtar yazdirilmaz. En fazla 8 istek."""
import json, os, sys, time, urllib.request, urllib.error
KEY = os.environ.get("YUVRON_KEY", "").strip()
if not KEY:
    sys.exit("YUVRON_KEY yok")
def get(h, path):
    time.sleep(2)
    r = urllib.request.Request(f"https://{h}{path}", headers={"X-RapidAPI-Key": KEY, "X-RapidAPI-Host": h, "User-Agent": "velspor"})
    try:
        with urllib.request.urlopen(r, timeout=30) as x:
            return x.status, json.loads(x.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:200]
    except Exception as e:  # noqa: BLE001
        return 0, str(e)[:200]
def gs(rows):
    return [m for m in rows if "galatasaray" in json.dumps(m, ensure_ascii=False).lower()]
for h in ("champions-league4.p.rapidapi.com", "super-lig.p.rapidapi.com"):
    print("==", h)
    for q in ("/matches", "/matches?page=2", "/matches?limit=100", "/matches?status=live"):
        s, d = get(h, q)
        if s != 200:
            print(q, "HTTP", s, str(d)[:150])
            continue
        rows = d.get("data") or []
        print(q, "HTTP 200 adet:", len(rows), "meta:", json.dumps(d.get("meta"), ensure_ascii=False), "| ust anahtarlar:", list(d.keys()))
        if rows:
            ks = sorted(m.get("kickoff", "") for m in rows)
            print("  tarih araligi:", ks[0][:10], "->", ks[-1][:10], "| Galatasaray:", len(gs(rows)))
            for m in gs(rows)[-3:]:
                print("  ", m["id"], m.get("kickoff", "")[:16], m.get("status"), m["homeTeam"]["name"], m["score"], m["awayTeam"]["name"])
