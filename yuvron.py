"""Mac sonu oyuncu performans kartlari (Yuvron). Anahtar: YUVRON_KEY. Hata olursa sessizce atlar, kayda yazar."""
import json, os, time, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
STATE = ROOT / "state" / "yuvron.json"
HOSTS = {"cl": "champions-league4.p.rapidapi.com", "sl": "super-lig.p.rapidapi.com"}
KEY = (os.environ.get("YUVRON_KEY") or "").strip()


def _load():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save(s):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")


def get(comp, path):
    host = HOSTS[comp]
    time.sleep(1.5)
    r = urllib.request.Request(f"https://{host}{path}", headers={"X-RapidAPI-Key": KEY, "X-RapidAPI-Host": host, "User-Agent": "velspor"})
    with urllib.request.urlopen(r, timeout=30) as x:
        return json.loads(x.read().decode("utf-8", "replace"))


def comp_of(league_name):
    n = (league_name or "").lower()
    if "champions" in n or "şampiyonlar" in n:
        return "cl"
    if "süper" in n or "super" in n or "trendyol" in n:
        return "sl"
    return None


def _kick(m):
    return datetime.fromisoformat(m["kickoff"].replace("Z", "+00:00"))


def find_match(comp, kick, st):
    """kick: UTC datetime. Yuvron maç listesinde (tarihe gore sirali) Galatasaray maçini bulur."""
    page = max(1, int(st.get(f"page_{comp}", 1)))
    seen = set()
    for _ in range(5):
        if page in seen or page < 1:
            break
        seen.add(page)
        d = get(comp, f"/matches?page={page}&limit=100")
        rows = d.get("data") or []
        if not rows:
            break
        for m in rows:
            names = (m["homeTeam"]["name"] + " " + m["awayTeam"]["name"]).lower()
            if "galatasaray" in names and abs(_kick(m) - kick) <= timedelta(hours=4):
                st[f"page_{comp}"] = page
                return m
        ks = sorted(_kick(m) for m in rows)
        if kick < ks[0]:
            page -= 1
        elif kick > ks[-1]:
            page += 1
        else:
            break
    return None


def gs_players(detail):
    dd = detail["data"]
    side = "home" if "galatasaray" in dd["homeTeam"]["name"].lower() else "away"
    lu = (dd.get("lineups") or {}).get(side) or {}
    return [p for p in (lu.get("starting") or []) + (lu.get("bench") or []) if (p.get("minutes") or 0) > 0], side


def select(players):
    rated = [p for p in players if isinstance(p.get("rating"), (int, float))]
    top = sorted(rated, key=lambda p: (p["rating"], p.get("goals") or 0, p.get("minutes") or 0), reverse=True)[:3]
    ids = {id(p) for p in top}
    out = list(top)
    for p in players:
        if (p.get("goals") or 0) > 0 and id(p) not in ids:
            out.append(p); ids.add(id(p))
    return out


def caption(D, player, match):
    s = player.get("stats") or {}
    g = lambda k: s.get(k) or 0
    L = [f'{D["first"]} {D["last"].title()} · {match} performansı', ""]
    if D["rating"]:
        L.append(f'⭐ {D["rating"]} Reyting')
    if (player.get("position") or "").upper() == "GK":
        L.append(f'🧤 {g("saves")} kurtarış')
        L.append(f'🥅 {g("goalsConceded")} yenen gol')
        if g("expectedGoalsPrevented"):
            L.append(f'🎯 {g("expectedGoalsPrevented"):+.2f} önlenen xG')
    else:
        if player.get("goals"): L.append(f'⚽️ {player["goals"]} gol')
        if player.get("assists"): L.append(f'🅰️ {player["assists"]} asist')
        if g("shots"): L.append(f'🥅 {g("shots")} şut ({g("shotsOnTarget")} isabetli)')
        if g("expectedGoalsOnTarget"): L.append(f'🎯 {g("expectedGoalsOnTarget"):.2f} xGOT')
    if g("passesAttempted"):
        L.append(f'📈 {g("passesCompleted")}/{g("passesAttempted")} isabetli pas (%{round(100*g("passesCompleted")/g("passesAttempted"))})')
    if g("passesIntoFinalThird"): L.append(f'📍 Son üçte bire {g("passesIntoFinalThird")} pas')
    if g("touches"): L.append(f'👟 {g("touches")} kez topla buluşma')
    if g("groundDuelsAttempted"): L.append(f'⚔️ {g("groundDuelsWon")}/{g("groundDuelsAttempted")} kazanılan yer mücadelesi')
    dcon = g("tacklesWon") + g("interceptions") + g("clearances") + g("blocks")
    if dcon: L.append(f'🛡 {dcon} savunma katkısı')
    if g("interceptions"): L.append(f'🔒 {g("interceptions")} pas arası')
    if g("clearances"): L.append(f'🌟 {g("clearances")} top uzaklaştırma')
    if g("ballRecoveries"): L.append(f'💛 {g("ballRecoveries")} top kazanma')
    return "\n".join(L)[:1000]


def send_cards(comp, detail, send_photo):
    import perfkart
    dd = detail["data"]
    sc = dd.get("score") or {}
    match = f'{dd["homeTeam"]["name"]} {sc.get("home")}-{sc.get("away")} {dd["awayTeam"]["name"]}'
    players, _ = gs_players(detail)
    chosen = select(players)
    OUT.mkdir(exist_ok=True)
    n = 0
    for p in chosen:
        D = perfkart.build(p)
        if not D:
            continue
        path = OUT / f'perf_{dd["id"]}_{(p.get("player") or {}).get("id")}.png'
        if perfkart.make(p, match, comp, str(path)):
            send_photo(path, caption(D, p, match)); n += 1
    return n


def run(kick, league_name, send_photo, delays=(0, 240, 600, 900)):
    """canli.py maç sonunda cagirir. kick: UTC datetime."""
    comp = comp_of(league_name)
    if not comp or not KEY:
        print("Yuvron: atlandi (lig desteklenmiyor ya da anahtar yok)")
        return 0
    st = _load()
    for i, w in enumerate(delays):
        time.sleep(w)
        try:
            mid = (st.get("mid") or {}).get(f"{comp}:{kick.date()}")
            if not mid:
                m = find_match(comp, kick, st)
                if not m:
                    print("Yuvron: mac listede yok, tekrar denenecek"); continue
                mid = m["id"]; st.setdefault("mid", {})[f"{comp}:{kick.date()}"] = mid
            if str(mid) in (st.get("done") or []):
                return 0
            d = get(comp, f"/matches/{mid}")
            players, _ = gs_players(d)
            rated = [p for p in players if isinstance(p.get("rating"), (int, float))]
            if d["data"].get("status") != "finished" or len(rated) < 8:
                print(f"Yuvron: veri henuz hazir degil ({len(rated)} puan)"); continue
            n = send_cards(comp, d, send_photo)
            st.setdefault("done", []).append(str(mid))
            _save(st)
            print(f"Yuvron: {n} kart gonderildi")
            return n
        except Exception as e:  # noqa: BLE001
            print("Yuvron hata:", str(e)[:120].replace(KEY or "x", "***"))
    _save(st)
    return 0


if __name__ == "__main__":
    # Elle test: YT_COMP=cl YT_MATCH=658308499
    from net import tg_configured, tg_send_photo
    def sp(path, text):
        if tg_configured():
            tg_send_photo(path, text)
        print("[foto]", text.split("\n")[0])
    comp, mid = os.environ.get("YT_COMP", "cl"), os.environ.get("YT_MATCH", "")
    if not KEY or not mid:
        raise SystemExit("YUVRON_KEY ve YT_MATCH gerekli")
    d = get(comp, f"/matches/{mid}")
    print("kart:", send_cards(comp, d, sp))
