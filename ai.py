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
GEMINI = os.environ.get("GEMINI_KEY", "").strip()
ENABLED = bool(TOKEN or GEMINI) and os.environ.get("AI_OFF") != "1"
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


GEMINI_MODELS = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
_gm = None   # calisan gemini modeli
_ok = None   # calisan saglayici adi (test mesajinda gosterilir)


def _http(url, headers, payload, label):
    """(json, hata). 429/5xx ve ag zaman asimi AiBusy; digerleri hata metni olarak doner."""
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
            status, ctype = r.status, r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        b = e.read()[:200].decode("utf-8", "ignore")
        if e.code in (429, 500, 502, 503, 504):
            raise AiBusy(f"{label} HTTP {e.code}") from e
        return None, f"{label}:HTTP {e.code} {b!r}"
    except TimeoutError as e:
        raise AiBusy(f"{label} zaman asimi") from e
    except urllib.error.URLError as e:
        return None, f"{label}:ag {str(e.reason)[:60]}"
    try:
        return json.loads(body), ""
    except ValueError:
        return None, f"{label}:HTTP {status} {ctype[:20]} {body[:60]!r}"


def _gemini(system, user, strict):
    global _gm
    models = ([_gm] if _gm else []) + [m for m in GEMINI_MODELS if m != _gm]
    errs = []
    for m in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
        cfg = {"temperature": 0.2, "maxOutputTokens": 800}
        if not strict:
            cfg["responseMimeType"] = "application/json"
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}], "generationConfig": dict(cfg)}
        body["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}
        data, err = _http(url, {"x-goog-api-key": GEMINI}, body, f"g/{m}")
        if data is None and "HTTP 400" in err:  # modelin dusunme ayari yoksa onsuz dene
            body["generationConfig"] = dict(cfg)
            data, err = _http(url, {"x-goog-api-key": GEMINI}, body, f"g/{m}")
        if data is None:
            errs.append(err)
            continue
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
        except Exception:  # noqa: BLE001
            errs.append(f"g/{m}:yanit bos {str(data)[:120]}")
            continue
        _gm = m
        return text, ""
    return None, " | ".join(errs)


def _github(system, user, strict):
    payload = {"model": MODEL, "temperature": 0.2, "max_tokens": 500,
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if not strict:
        payload["response_format"] = {"type": "json_object"}
    for extra in ({}, {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}):
        data, err = _http(URL, {"Authorization": f"Bearer {TOKEN}", **extra}, payload, "gh")
        if data is not None:
            try:
                return (data["choices"][0]["message"].get("content") or "").strip(), ""
            except Exception:  # noqa: BLE001
                err = "gh:yanit bos " + str(data)[:100]
    return None, err


def _complete(system, user, strict=False):
    """Sirayla saglayicilari dener (Gemini, sonra GitHub Models). Metin dondurur."""
    global _ok
    errs, busy = [], None
    for name, fn, on in (("gemini", _gemini, bool(GEMINI)), ("github", _github, bool(TOKEN))):
        if not on:
            continue
        try:
            text, err = fn(system, user, strict)
        except AiBusy as e:
            busy = e
            continue
        if text is not None:
            _ok = name
            return text
        errs.append(err)
    if busy and not errs:
        raise busy
    raise RuntimeError("v5 " + " | ".join(errs + ([str(busy)] if busy else [])))


def analyze(title, paragraphs, source="", tg=False):
    """(uygun, metin, iddia, neden, baslik, kategori) dondurur. Hata: AiBusy veya RuntimeError."""
    text = "\n".join(paragraphs)[:3500] or "(sayfa metni alinamadi)"
    extra = ("\nNOT: Bu metin bir Telegram kanalindan alindi. Emoji, etiket, kanal reklami, 'katil/takip et' "
             "cagrilarini ve link satirlarini yok say; sadece haberi yaz.") if tg else ""
    user = f"BASLIK: {title}\nPAYLASAN: {source}\nMETIN:\n{text}{extra}"
    def ask(strict):
        return _complete(SYSTEM, user + ("\n\nSadece JSON nesnesi dondur, baska hicbir sey yazma." if strict else ""), strict)

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
        raise RuntimeError("v5 JSON degil: " + repr(raw[:150]))
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
