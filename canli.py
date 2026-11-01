"""Canli mac izleyici. MOD: otomatik | izle | tekrar | test. Anahtar/token yazdirilmaz."""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import api
from net import tg_configured, tg_send_message, tg_send_photo
from olaykart import caption, league_label, make_card

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
STATE = ROOT / "state" / "mac.json"
FIX = ROOT / "state" / "fixtures.json"
TEAM = int(os.environ.get("TAKIM") or 549679)
COACH = os.environ.get("COACH") or "Okan Buruk"
POLL = int(os.environ.get("POLL_SEC") or 90)
DAILY_MAX = 95
UTC = timezone.utc
DAYS = ["PAZARTESİ", "SALI", "ÇARŞAMBA", "PERŞEMBE", "CUMA", "CUMARTESİ", "PAZAR"]
MONTHS = ["OCAK", "ŞUBAT", "MART", "NİSAN", "MAYIS", "HAZİRAN", "TEMMUZ", "AĞUSTOS",
          "EYLÜL", "EKİM", "KASIM", "ARALIK"]


def now():
    return datetime.now(UTC)


def jload(p, d):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return d


def jsave(p, v):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")


def send_photo(path, text):
    if tg_configured():
        tg_send_photo(path, text)
    print("[foto]", text.split("\n")[0])


def send_text(text):
    if tg_configured():
        tg_send_message(text)
    print("[mesaj]", text.split("\n")[0])


# ---------- butce ----------

class Budget:
    def __init__(self, st):
        today = str(now().date())
        a = st.get("api", {})
        self.date, self.n0 = today, (a.get("n", 0) if a.get("date") == today else 0)

    @property
    def used(self):
        return self.n0 + api.COUNT

    def left(self):
        return DAILY_MAX - self.used

    def dump(self):
        return {"date": self.date, "n": self.used}


# ---------- fikstur ----------

def pick(m):
    return dict(id=m["id"], date=m["date"], home=m["homeTeam"], away=m["awayTeam"],
                league=(m.get("league") or {}).get("name", ""), round=m.get("round", ""))


def refresh_fixtures(force=False):
    fx = jload(FIX, {})
    try:
        age = now() - datetime.fromisoformat(fx.get("at", "2000-01-01T00:00:00+00:00"))
    except Exception:  # noqa: BLE001
        age = timedelta(days=9)
    if fx.get("matches") and age < timedelta(hours=20) and not force:
        return fx["matches"]
    t = now()
    season = t.year if t.month >= 7 else t.year - 1
    found = {}
    for side in ("homeTeamId", "awayTeamId"):
        try:
            d = api.get("/football/matches", season=season, limit=40, **{side: TEAM})
            for m in api.rows(d):
                found[m["id"]] = pick(m)
        except Exception as e:  # noqa: BLE001
            print("Fikstur hatasi:", side, e)
    if found:
        fx = {"at": t.isoformat(), "matches": sorted(found.values(), key=lambda x: x["date"])}
        jsave(FIX, fx)
    return fx.get("matches", [])


def ko(m):
    return datetime.fromisoformat(m["date"].replace("Z", "+00:00"))


# ---------- yardimcilar ----------

def short_name(full, maxlen=17):
    full = (full or "").strip()
    if len(full) <= maxlen:
        return full
    parts = full.split()
    return f"{parts[0][0]}. {parts[-1]}" if len(parts) > 1 else full[:maxlen]


def state_code(desc):
    d = (desc or "").lower()
    if any(x in d for x in ("postpon", "cancel", "abandon", "suspend")):
        return "STOP"
    if any(x in d for x in ("finish", "ended", "full time", "full-time", "after")):
        return "FT"
    if any(x in d for x in ("half time", "halftime", "break", "interval")):
        return "HT"
    if "second" in d:
        return "H2"
    if "first" in d:
        return "H1"
    if "extra" in d or "penalt" in d:
        return "ET"
    if "not started" in d or d in ("", "scheduled"):
        return "NS"
    return "LIVE"


def parse_score(state):
    s = ((state or {}).get("score") or {}).get("current")
    try:
        a, b = [int(x) for x in str(s).replace(" ", "").split("-")]
        return (a, b)
    except Exception:  # noqa: BLE001
        return None


def ekey(e):
    return "|".join(str(x) for x in (e.get("type"), e.get("time"), e.get("playerId"),
                                      (e.get("team") or {}).get("id"), e.get("substituted")))


def classify(e):
    t = (e.get("type") or "").lower()
    if "own" in t:
        return "own"
    if "miss" in t and "pen" in t:
        return "pen_miss"
    if "penalty" in t and ("award" in t or "decision" in t):
        return "pen_award"
    if "penalty" in t:
        return "pen_goal"
    if "goal" in t and ("cancel" in t or "disallow" in t):
        return "goal_cancel"
    if "goal" in t:
        return "goal"
    if "yellow" in t and "red" in t or "second" in t:
        return "second_yellow"
    if "yellow" in t:
        return "yellow"
    if "red" in t:
        return "red"
    if "sub" in t:
        return "sub"
    if "var" in t:
        return "var"
    if "injur" in t:
        return "injury"
    return None


def minute_of(e):
    return str(e.get("time") or "").strip()


def names_from(lu, names):
    for side in ("homeTeam", "awayTeam"):
        t = lu.get(side) or {}
        for grp in t.get("initialLineup", []):
            for p in grp:
                names[p["id"]] = p["name"]
        for p in t.get("substitutes", []):
            names[p["id"]] = p["name"]


class Match:
    def __init__(self, m, st, budget, replay=False):
        self.m, self.st, self.b, self.replay = m, st, budget, replay
        self.mid = m["id"]
        self.home, self.away = m["home"], m["away"]
        self.hn, self.an = self.home["name"], self.away["name"]
        self.names = {}
        self.score = None
        self.code = "NS"
        self.goal_keys = {}  # key -> kac poll yok
        self.seen = set(st.setdefault("seen", {}).get(str(self.mid), []))

    # --- kart gonder ---
    def card(self, kind, **d):
        OUT.mkdir(exist_ok=True)
        path = OUT / f"{self.mid}_{kind}_{int(time.time()*1000)%100000}.png"
        hot = d.pop("hot", None)
        make_card(kind, path, self.hn, self.an, league=self.m["league"], score=self.score, hot=hot, **d)
        cd = dict(d)
        cd.update(home=self.hn, away=self.an, score=self.score)
        send_photo(path, caption(kind, cd))

    def side(self, e):
        tid = (e.get("team") or {}).get("id")
        return "home" if tid == self.home["id"] else "away" if tid == self.away["id"] else None

    def us(self, side):
        return (self.home["id"] if side == "home" else self.away["id"]) == TEAM

    def pname(self, pid, short):
        full = self.names.get(pid)
        return short_name(full) if full else (short or "")

    # --- olay -> kart ---
    def handle(self, e):
        k = classify(e)
        side = self.side(e)
        mine = self.us(side) if side else True
        mn = minute_of(e)
        who = self.pname(e.get("playerId"), e.get("player"))
        if k is None:
            send_text(f"Yeni olay türü: {e.get('type')}\n{json.dumps(e, ensure_ascii=False)[:600]}")
            return
        if k == "sub":
            ins = self.pname(e.get("assistingPlayerId"), e.get("substituted"))
            outp = who
            self.card("sub", minute=mn, ins=ins, outp=outp, hot=side)
            return
        if k in ("goal", "pen_goal", "own"):
            if k == "own":
                # kendi kalesine atan oyuncunun rakibi lehine sayilir
                side_for = "away" if side == "home" else "home"
                good = self.us(side_for)
                kind = "own_goal"
            else:
                side_for, good = side, mine
                kind = ("goal" if k == "goal" else "pen_goal") if good else ("opp_goal" if k == "goal" else "opp_pen_goal")
            self.refresh_score(expect_goal=True)
            sub = ""
            if kind in ("goal",) and e.get("assist"):
                sub = "asist: " + self.pname(e.get("assistingPlayerId"), e.get("assist"))
            self.card(kind, minute=mn, name=who, sub=sub, hot=side_for)
            return
        self.card(k, minute=mn, name=who, hot=side)

    # --- durum ---
    def refresh_score(self, expect_goal=False):
        try:
            d = api.one(api.get(f"/football/matches/{self.mid}"))
            sc = parse_score(d.get("state"))
            if sc:
                self.score = sc
            self.code = state_code((d.get("state") or {}).get("description"))
            self.clock = (d.get("state") or {}).get("clock")
        except Exception as e:  # noqa: BLE001
            print("Durum hatasi:", e)

    def lineup(self):
        d = api.get(f"/football/lineups/{self.mid}")
        return d if isinstance(d, dict) else api.one(d)

    def send_lineup(self, lu):
        from kartlar import make_lineup
        names_from(lu, self.names)
        side = "homeTeam" if self.home["id"] == TEAM else "awayTeam"
        t = lu.get(side) or {}
        players = [(p["number"], short_name(p["name"], 19), False) for grp in t.get("initialLineup", []) for p in grp]
        if len(players) < 5:
            return False
        subs = [p["name"].split()[-1] for p in t.get("substitutes", [])]
        OUT.mkdir(exist_ok=True)
        path = OUT / f"{self.mid}_ilk11.png"
        make_lineup(self.hn, self.an, players, COACH, subs, path, title="İLK 11", extra=t.get("formation", ""))
        send_photo(path, f"İlk 11 · {self.hn} - {self.an}\n\n#Galatasaray")
        self.weather()
        return True

    def weather(self):
        if self.home["id"] != TEAM:
            return
        try:
            from kartlar import make_weather
            from ozel import fetch_weather
            local = ko(self.m) + timedelta(hours=3)
            hhmm = local.strftime("%H:%M")
            w = fetch_weather(os.environ.get("HOME_CITY") or "İstanbul", local.strftime("%Y-%m-%d"), hhmm)
            path = OUT / f"{self.mid}_hava.png"
            dt = f"{local.day} {MONTHS[local.month - 1]} {DAYS[local.weekday()]}"
            make_weather(self.hn, self.an, os.environ.get("STADIUM") or "RAMS Park", hhmm, dt, w, path)
            send_photo(path, f"Hava durumu · {self.hn} - {self.an}\n(Tahmindir.)\n\n#Galatasaray")
        except Exception as e:  # noqa: BLE001
            print("Hava kartı yapılamadı:", str(e)[:100])

    def events(self):
        d = api.get(f"/football/events/{self.mid}")
        return api.rows(d)

    def scorers(self, evs):
        out = []
        for e in evs:
            k = classify(e)
            if k in ("goal", "pen_goal", "own"):
                n = self.pname(e.get("playerId"), e.get("player")).split()[-1]
                out.append(f"{n} {minute_of(e)}'" + (" (P)" if k == "pen_goal" else " (KK)" if k == "own" else ""))
        return out

    def save(self):
        self.st["seen"][str(self.mid)] = sorted(self.seen)
        self.st["api"] = self.b.dump()
        jsave(STATE, self.st)

    # --- ana dongu ---
    def run(self):
        kick = ko(self.m)
        lineup_done = bool(self.st.setdefault("lineup", {}).get(str(self.mid)))
        phase_sent = set(self.st.setdefault("phase", {}).get(str(self.mid), []))
        last_clock, polls, silent_first = 0, 0, not self.st["seen"].get(str(self.mid)) and now() > kick + timedelta(minutes=3)
        self.clock = 0
        while True:
            t = now()
            if t > kick + timedelta(hours=4, minutes=30):
                print("Zaman asimi")
                return "timeout"
            if self.b.left() <= 3:
                send_text("⚠️ Günlük API hakkı bitti, maç takibi durdu.")
                return "budget"
            if t < kick - timedelta(minutes=3):
                if not lineup_done:
                    try:
                        lu = self.lineup()
                        if lu and self.send_lineup(lu):
                            lineup_done = True
                            self.st["lineup"][str(self.mid)] = True
                            self.save()
                    except Exception as e:  # noqa: BLE001
                        print("Kadro yok henüz:", str(e)[:60])
                wait = 480 if not lineup_done else max(30, min(600, (kick - t).total_seconds() - 150))
                time.sleep(wait)
                continue
            if not lineup_done and not self.names:
                try:
                    names_from(self.lineup(), self.names)
                except Exception:  # noqa: BLE001
                    pass
            polls += 1
            try:
                evs = self.events()
            except Exception as e:  # noqa: BLE001
                print("Olay hatasi:", e)
                time.sleep(POLL)
                continue
            keys = {ekey(e) for e in evs}
            new = [e for e in evs if ekey(e) not in self.seen]
            if silent_first:
                self.seen |= keys
                silent_first, new = False, []
                send_text("ℹ️ Bot maça geç başladı; geçmiş olaylar atlandı, bundan sonrakiler gelecek.")
                self.refresh_score()
            # gol iptali: onceden gonderilen gol listeden kaybolursa
            for e in evs:
                if classify(e) in ("goal", "pen_goal", "own"):
                    self.goal_keys[ekey(e)] = 0
            for gk in list(self.goal_keys):
                if gk not in keys:
                    self.goal_keys[gk] += 1
                    if self.goal_keys[gk] >= 2:
                        del self.goal_keys[gk]
                        self.refresh_score()
                        self.card("goal_cancel")
            for e in new:
                self.seen.add(ekey(e))
                try:
                    self.handle(e)
                except Exception as ex:  # noqa: BLE001
                    print("Olay işlenemedi:", str(ex)[:100])
            # durum
            due = polls % 6 == 1 or self.code in ("HT",) or (self.code == "H1" and (self.clock or 0) >= 42) or (self.code == "H2" and (self.clock or 0) >= 86)
            if due and not new:
                self.refresh_score()
            code = self.code
            if code == "H1" and "ko" not in phase_sent:
                phase_sent.add("ko")
                self.card("kickoff")
            elif code == "HT" and "ht" not in phase_sent:
                phase_sent.add("ht")
                self.card("ht")
            elif code == "H2" and "h2" not in phase_sent:
                phase_sent.add("h2")
                self.card("h2")
            elif code == "FT":
                self.card("ft", extra=self.scorers(evs))
                phase_sent.add("ft")
                self.st["phase"][str(self.mid)] = sorted(phase_sent)
                self.save()
                return "ft"
            elif code == "STOP":
                send_text("Maç ertelendi / iptal edildi.")
                return "stop"
            self.st["phase"][str(self.mid)] = sorted(phase_sent)
            self.save()
            wait = 300 if code == "HT" else POLL
            if self.b.left() < 30:
                wait = max(wait, 180)
            time.sleep(wait)


def replay(mid, limit=8):
    """Bitmis mac olaylarini kart olarak yolla (tasarim denemesi)."""
    d = api.one(api.get(f"/football/matches/{mid}"))
    m = pick(d)
    st = {"seen": {}}
    b = Budget(st)
    M = Match(m, st, b, replay=True)
    try:
        names_from(M.lineup(), M.names)
    except Exception as e:  # noqa: BLE001
        print("kadro yok", e)
    M.refresh_score()
    evs = M.events()
    shown = 0
    for e in evs:
        if classify(e) in ("goal", "pen_goal", "own", "red", "second_yellow", "yellow", "sub", "var") and shown < limit:
            M.handle(e)
            shown += 1
            time.sleep(1)
    M.code = "FT"
    M.card("ft", extra=M.scorers(evs))
    return 0


def main():
    mod = os.environ.get("MOD") or "otomatik"
    mid = (os.environ.get("MAC_ID") or "").strip()
    st = jload(STATE, {})
    b = Budget(st)
    if mod == "test":
        fx = refresh_fixtures(force=True)
        up = [x for x in fx if ko(x) > now()][:3]
        lines = [f"Fikstür: {len(fx)} maç. Sıradakiler:"]
        for x in up:
            lines.append(f"{(ko(x)+timedelta(hours=3)).strftime('%d.%m %H:%M')} {x['home']['name']} - {x['away']['name']} ({league_label(x['league'])})")
        lines.append(f"API: {api.COUNT} istek bu çalışmada. Kimlik başlığı: {api._hdr}")
        send_text("\n".join(lines))
        st["api"] = Budget(st).dump() | {"n": b.n0 + api.COUNT}
        jsave(STATE, st)
        return 0
    if mod == "tekrar":
        return replay(int(mid))
    if mod == "izle":
        d = api.one(api.get(f"/football/matches/{mid}"))
        M = Match(pick(d), st, b)
        print("Sonuc:", M.run())
        return 0
    # otomatik
    fx = refresh_fixtures()
    done = set(st.get("done", []))
    for x in fx:
        k = ko(x)
        if x["id"] in done or not (k - timedelta(minutes=80) <= now() <= k + timedelta(hours=4)):
            continue
        M = Match(x, st, b)
        res = M.run()
        st.setdefault("done", []).append(x["id"])
        st["done"] = st["done"][-60:]
        st["api"] = b.dump()
        jsave(STATE, st)
        print("Mac bitti:", res)
        break
    else:
        st["api"] = b.dump()
        jsave(STATE, st)
        print("Su an izlenecek mac yok.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
