"""Form kartlari: MOD=hava | ilk11. Veriyi formdan alir, Telegram'a yollar."""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from kartlar import make_lineup, make_weather
from net import tg_configured, tg_send_photo

OUT = Path(__file__).resolve().parent / "out"
DAYS = ["PAZARTESİ", "SALI", "ÇARŞAMBA", "PERŞEMBE", "CUMA", "CUMARTESİ", "PAZAR"]
MONTHS = ["OCAK", "ŞUBAT", "MART", "NİSAN", "MAYIS", "HAZİRAN", "TEMMUZ", "AĞUSTOS",
          "EYLÜL", "EKİM", "KASIM", "ARALIK"]


def env(k, d=""):
    return os.environ.get(k, d).strip()


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "VelSporBot/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read())


def fetch_weather(city, date, hhmm):
    g = get_json("https://geocoding-api.open-meteo.com/v1/search?count=1&language=tr&format=json&name="
                 + urllib.parse.quote(city))
    res = g["results"][0]
    q = urllib.parse.urlencode({
        "latitude": res["latitude"], "longitude": res["longitude"], "timezone": "Europe/Istanbul",
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation,snowfall,weather_code",
        "start_date": date, "end_date": date,
    })
    h = get_json("https://api.open-meteo.com/v1/forecast?" + q)["hourly"]
    i = h["time"].index(f"{date}T{int(hhmm.split(':')[0]):02d}:00")
    code = h["weather_code"][i]
    return dict(
        temp=round(h["temperature_2m"][i]), wind=round(h["wind_speed_10m"][i]),
        hum=round(h["relative_humidity_2m"][i]),
        rain=(h["precipitation"][i] or 0) > 0.1 or code in range(51, 68) or code in range(80, 83) or code >= 95,
        snow=(h["snowfall"][i] or 0) > 0 or code in range(71, 78) or code in (85, 86),
    )


def parse_players(s):
    """'1 Uğurcan, 42 Abdülkerim (K), ...' -> [(no, isim, kaptan)]"""
    out = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        cap = "(K)" in part.upper()
        part = part.replace("(K)", "").replace("(k)", "").strip()
        num, _, name = part.partition(" ")
        out.append((num, name.strip() or num, cap))
    return out


def send(path, caption):
    if tg_configured():
        tg_send_photo(path, caption)
        print("Telegram'a gonderildi")
    else:
        print("DRY RUN:", path)


def hava():
    sol, sag, std = env("SOL", "Galatasaray"), env("SAG"), env("STADYUM")
    city, saat, tarih = env("SEHIR"), env("SAAT"), env("TARIH")
    if not (sag and city and saat and tarih):
        print("Eksik bilgi: SAG, SEHIR, SAAT, TARIH gerekli")
        return 1
    w = fetch_weather(city, tarih, saat)
    d = datetime.strptime(tarih, "%Y-%m-%d")
    dt = f"{d.day} {MONTHS[d.month - 1]} {DAYS[d.weekday()]}"
    OUT.mkdir(exist_ok=True)
    path = OUT / "hava.png"
    make_weather(sol, sag, std or city, saat, dt, w, path)
    send(path, f"Hava durumu · {sol} - {sag}\n{city} {saat}\n(Tahmindir, maça yakın tekrar kontrol et.)")
    return 0


def ilk11():
    sol, sag = env("SOL", "Galatasaray"), env("SAG")
    players = parse_players(env("KADRO"))
    if len(players) < 5:
        print("KADRO bos ya da eksik")
        return 1
    subs = [x.strip() for x in env("YEDEKLER").split(",") if x.strip()]
    OUT.mkdir(exist_ok=True)
    path = OUT / "ilk11.png"
    make_lineup(sol, sag, players, env("TD", "Okan Buruk"), subs, path, title=env("BASLIK", "İLK 11"))
    send(path, f"İlk 11 · {sol} - {sag}")
    return 0


if __name__ == "__main__":
    m = env("MOD")
    sys.exit(hava() if m == "hava" else ilk11() if m == "ilk11" else 1)
