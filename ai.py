"""Haber analizi (GitHub Models, ucretsiz): konu uygun mu + paylasilabilir metin.
GITHUB_TOKEN yoksa ENABLED=False; bot eski kural tabanli metne doner."""
import json
import os
import re
import urllib.error
import urllib.request

URL = "https://models.github.ai/inference/chat/completions"
MODEL = os.environ.get("AI_MODEL") or "openai/gpt-4.1-mini"
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
ENABLED = bool(TOKEN) and os.environ.get("AI_OFF") != "1"
LIMIT = 270
TAG = "#Galatasaray"


class AiBusy(Exception):
    """Limit/gecici hata: haber atlanmaz, sonraki calismada tekrar denenir."""


SYSTEM = """Sen 'Vel Spor' adli Galatasaray taraftar sayfasinin editorusun. Turkce yaz.
Sana bir haberin basligi ve sayfa metni verilecek. Sadece JSON dondur:
{"uygun": true/false, "neden": "kisa", "metin": "...", "iddia": true/false}

UYGUN (true) sadece su durumda: haber Galatasaray'in ERKEK FUTBOL takimiyla ilgili (mac, kadro, transfer,
sakatlik, cezalar, teknik direktor/futbolcu aciklamasi, antrenman, yonetim kararlari ve futbolu ilgilendiren
konular). UYGUN DEGIL (false): basketbol, voleybol, kadin/altyapi/diger branslar, e-spor, magazin/ozel hayat,
reklam/sponsor/kampanya, burs/bilet/uyelik duyurusu, Galatasaray'in sadece gecerek anildigi haberler, ve
metninde basligin vaat ettigi somut bilgi HIC olmayan tiklama-tuzagi haberler.

METIN kurallari (uygun=true ise):
- Tweet olarak yayinlanacak; en fazla 250 karakter, sonuna bos satir ve #Galatasaray eklenecek (sen ekleme).
- Ilk satir: dikkat ceken, sade bir cumle (basligi aynen kopyalama, ama anlamini degistirme).
- Ardindan 1-2 kisa cumle: haberin SOMUT bilgisi (kim ne dedi, ne oldu, kim, kac, ne zaman). Basligin
  vaat ettigi bilgi (ornegin 'X hakkinda aciklama') metinde yoksa uygun=false yap.
- SADECE verilen metindeki bilgiyi kullan. Hicbir sey uydurma, tahmin ekleme, sayi/isim degistirme.
- Sozle alinti varsa kisaca aktar. Emoji, 'son dakika', 'flas', unlem yigini kullanma.
- Iddia/kaynaksiz/'iddiaya gore' tonundaki haberlerde iddia=true yap ve metinde 'iddia' dilini koru.
Kisa ve oz yaz."""


def _post(payload):
    req = urllib.request.Request(
        URL, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
                 "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read()[:200].decode("utf-8", "ignore")
        if e.code in (429, 500, 502, 503, 504):
            raise AiBusy(f"HTTP {e.code}") from e
        raise RuntimeError(f"HTTP {e.code} {body}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise AiBusy(str(e)[:80]) from e


def analyze(title, paragraphs, source=""):
    """(uygun, metin, iddia, neden) dondurur. Hata: AiBusy veya RuntimeError."""
    text = "\n".join(paragraphs)[:3500] or "(sayfa metni alinamadi)"
    user = f"BASLIK: {title}\nKAYNAK: {source}\nMETIN:\n{text}"
    data = _post({
        "model": MODEL, "temperature": 0.2, "max_tokens": 400,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
    })
    raw = data["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", raw, re.S)
    j = json.loads(m.group(0) if m else raw)
    ok = bool(j.get("uygun"))
    body = re.sub(r"\s*#\w+\s*$", "", (j.get("metin") or "").strip()).strip()
    body = body.replace("**", "")
    if ok and len(body) < 20:
        ok = False
    if len(body) > LIMIT - len(TAG) - 2:
        cut = body[: LIMIT - len(TAG) - 3]
        body = (cut.rsplit(".", 1)[0] + "." if "." in cut[40:] else cut.rsplit(" ", 1)[0] + "…")
    return ok, f"{body}\n\n{TAG}", bool(j.get("iddia")), (j.get("neden") or "")[:120]
