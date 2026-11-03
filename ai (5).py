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
LIMIT = 280


class AiBusy(Exception):
    """Limit/gecici hata: haber atlanmaz, sonraki calismada tekrar denenir."""


SYSTEM = """Sen 'Vel Spor' adli Galatasaray taraftar sayfasinin editorusun. Turkce yaz.
Sana bir haberin basligi ve sayfa metni verilecek. Sadece JSON dondur:
{"uygun": true/false, "neden": "kisa", "baslik": "...", "kategori": "...", "kaynak": "...", "metin": "...", "iddia": true/false}

UYGUN (true) sadece su durumda: haber Galatasaray'in ERKEK FUTBOL takimiyla ilgili (mac, kadro, transfer,
sakatlik, cezalar, teknik direktor/futbolcu aciklamasi, antrenman, yonetim kararlari ve futbolu ilgilendiren
konular). UYGUN DEGIL (false): basketbol, voleybol, kadin/altyapi/diger branslar, e-spor, magazin/ozel hayat,
reklam/sponsor/kampanya, burs/bilet/uyelik duyurusu, Galatasaray'in sadece gecerek anildigi haberler, ve
metninde basligin vaat ettigi somut bilgi HIC olmayan tiklama-tuzagi haberler.

BASLIK: gorselde buyuk harfle yazilacak 2-3 kelimelik, en fazla 26 karakterlik net baslik; haberin ozunu soyler,
tiklama dili yok. Ornekler: OKAN BURUK AÇIKLADI, OSIMHEN SAKATLANDI, HAKEM BELLİ OLDU, İLK 11 BELLİ.
KAYNAK: mesajda/metinde haberi ilk veren muhabir, hesap veya gazete acikca belirtilmisse (ornek: 'Kaynak: Yağız
Sabuncuoğlu', '@hesap', 'Fanatik'e gore') onun adi; yoksa bos birak. Uydurma.
KATEGORI: sunlardan tam biri: Maç Öncesi, Maç İçi, Transfer, Oyuncu Performansı, Oyuncu Değişikliği,
Disiplin ve Ceza, Sakatlık, Kulüp ve Yönetim, Özel Gün, Puan Durumu, Antrenman, Taraftar ve Stadyum, Gündem.

METIN kurallari (uygun=true ise). Metin X'te dogrudan paylasilacak, haber ajansi tarzinda, SADE ve KISA olacak:
- 1. cumle: haberin ozu. Ozneyle basla (kisi/kulup adi), duz cumle: "Dursun Özbek, yeni görev dağılımını maçtan
  sonra çarşamba günü yapmayı planlıyor." Dikkat cekici giris cumlesi, soru, unlem, hashtag, emoji YOK.
- Onemli bir ikinci bilgi varsa yeni satirda "🔸 " ile tek kisa cumle ekle. Yoksa ekleme. Baska emoji kullanma.
- Birinin sozu varsa dogrudan alinti kullan, kisi adi once: Dursun Özbek: "Abdullah Kavukcu'nun istifasini ben
  istedim." Alintiyi aynen, kelimelerini degistirmeden ve sadece onemli kismini ver.
- Toplam genelde 1-2 cumle, en fazla 230 karakter. Gereksiz sifat, yorum, tahmin, baglam ekleme.
- SADECE verilen metindeki bilgiyi kullan; hicbir sey uydurma; sayi, isim, tarih degistirme. Basligin vaat ettigi
  somut bilgi metinde yoksa uygun=false.
- Haberin kendisi kesin degilse ('iddia', 'öne sürüldü', 'bekleniyor', 'gündemde') bu temkini metinde koru;
  kesin olmayan bilgiyi kesin gibi yazma. Bu durumda iddia=true yap. Resmi/kesin haberde temkin ekleme.
- Sonuna kaynak, hashtag veya link EKLEME; bunlari sistem ekler.

Ornek ciktilar (sadece tarz icin):
Dursun Özbek, yeni görev dağılımını maçtan sonra çarşamba günü yapmayı planlıyor.

Matvey Kislyak, Galatasaray'ın transfer listesinde.
🔸 Genç oyuncu, sarı-kırmızılılarda forma giymeye sıcak bakıyor.

Dursun Özbek: "Abdullah Kavukcu'nun istifasını ben istedim. Habersiz medya üzerinden istifa eden Öztürk'e ise kırgınım."
Kisa ve oz yaz."""


VARIANTS = [  # (ad, adres, ek basliklar, model on eki cikar)
    ("a", "https://models.github.ai/inference/chat/completions", {}, False),
    ("b", "https://models.github.ai/inference/chat/completions",
     {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}, False),
    ("c", "https://models.inference.ai.azure.com/chat/completions", {}, True),
]
_ok = None  # calisan varyant (ayni calismada hatirlanir)


def _try(variant, payload):
    name, url, extra, strip = variant
    p = dict(payload)
    if strip:
        p["model"] = p["model"].split("/", 1)[-1]
    h = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json", **extra}
    req = urllib.request.Request(url, data=json.dumps(p).encode(), headers=h)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
            status, ctype = r.status, r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        b = e.read()[:150].decode("utf-8", "ignore")
        if e.code in (429, 500, 502, 503, 504):
            raise AiBusy(f"HTTP {e.code}") from e
        return None, f"{name}:HTTP {e.code} {b!r}"
    except (urllib.error.URLError, TimeoutError) as e:
        raise AiBusy(str(e)[:80]) from e
    try:
        return json.loads(body), ""
    except ValueError:
        return None, f"{name}:HTTP {status} {ctype[:20]} {body[:60]!r}"


def _post(payload):
    global _ok
    order = ([v for v in VARIANTS if v[0] == _ok] if _ok else []) + [v for v in VARIANTS if v[0] != _ok]
    errs = []
    for v in order:
        data, err = _try(v, payload)
        if data is not None:
            _ok = v[0]
            return data
        errs.append(err)
    raise RuntimeError("v4 " + " | ".join(errs))


def analyze(title, paragraphs, source="", tg=False):
    """(uygun, metin, iddia, neden, baslik, kategori) dondurur. Hata: AiBusy veya RuntimeError."""
    text = "\n".join(paragraphs)[:3500] or "(sayfa metni alinamadi)"
    extra = ("\nNOT: Bu metin bir Telegram kanalindan alindi. Emoji, etiket, kanal reklami, 'katil/takip et' "
             "cagrilarini ve link satirlarini yok say; sadece haberi yaz.") if tg else ""
    user = f"BASLIK: {title}\nPAYLASAN: {source}\nMETIN:\n{text}{extra}"
    def ask(strict):
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user + ("\n\nSadece JSON nesnesi dondur, baska hicbir sey yazma." if strict else "")}]
        payload = {"model": MODEL, "temperature": 0.2, "max_tokens": 500, "messages": msgs}
        if not strict:
            payload["response_format"] = {"type": "json_object"}
        data = _post(payload)
        try:
            return (data["choices"][0]["message"].get("content") or "").strip()
        except Exception:  # noqa: BLE001
            return "[beklenmeyen yanit: " + str(data)[:150] + "]"

    j = None
    raw = ""
    for strict in (False, True):
        raw = ask(strict)
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            try:
                j = json.loads(m.group(0))
                break
            except ValueError:
                pass
    if j is None:
        raise RuntimeError("v4 JSON degil: " + repr(raw[:150]))
    ok = bool(j.get("uygun"))
    body = (j.get("metin") or "").replace("**", "").strip()
    body = re.sub(r"\s*#\w+", "", body).strip()  # etiket gelirse at
    body = re.sub(r"\n{3,}", "\n\n", body)
    if ok and len(body) < 20:
        ok = False
    src = re.sub(r"\s+", " ", (j.get("kaynak") or "")).strip(" ()@")[:40] or (source if not tg else "")
    credit = f"\n\n({src})" if src else ""
    room = LIMIT - len(credit)
    if len(body) > room:
        cut = body[:room]
        body = cut.rsplit(".", 1)[0] + "." if "." in cut[40:] else cut.rsplit(" ", 1)[0] + "…"
    bas = re.sub(r"\s+", " ", (j.get("baslik") or "")).strip()[:28]
    return ok, f"{body}{credit}", bool(j.get("iddia")), (j.get("neden") or "")[:120], bas, (j.get("kategori") or "").strip()
