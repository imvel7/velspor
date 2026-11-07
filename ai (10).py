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
{"uygun": true/false, "neden": "kisa", "baslik": "...", "vurgu": "...", "anahtar": "...", "ozet": "...", "tur": "haber|alinti", "soz": "...", "kisi": "...", "unvan": "...", "kategori": "...", "kaynak": "...", "metin": "...", "iddia": true/false}

UYGUN (true) sadece su durumda: haber Galatasaray'in ERKEK FUTBOL takimiyla ilgili (mac, kadro, transfer,
sakatlik, cezalar, teknik direktor/futbolcu aciklamasi, antrenman, yonetim kararlari ve futbolu ilgilendiren
konular). UYGUN DEGIL (false): basketbol, voleybol, kadin/altyapi/diger branslar, e-spor, magazin/ozel hayat,
reklam/sponsor/kampanya, burs/bilet/uyelik duyurusu, Galatasaray'in sadece gecerek anildigi haberler, ve
metninde basligin vaat ettigi somut bilgi HIC olmayan tiklama-tuzagi haberler.

BASLIK: gorselde buyuk harfle yazilacak, haberin SOMUT ozunu soyleyen 3-8 kelimelik, en fazla 44 karakterlik baslik.
Ozel isim (kisi/takim) ve somut bilgi icermeli. 'TRANSFER GÜNDEMİ', 'AÇIKLAMA YAPTI', 'ÖNEMLİ GELİŞME' gibi bos
basliklar YASAK. Tiklama dili, soru, unlem yok. Ornekler: KISLYAK GALATASARAY'IN LİSTESİNDE, GÖREV DAĞILIMI
ÇARŞAMBA GÜNÜ, OSIMHEN SAKATLANDI, HAKEM BELLİ OLDU, İLK 11 BELLİ.
VURGU: basliktaki en onemli 1 (en fazla 2) kelime, basliktaki yazimiyla (gorselde altin renkle vurgulanir).
ANAHTAR: haberin ana kisisinin soyadi veya ana takimin adi, tek kelime (yoksa bos).
OZET: gorselde basligin altinda duracak, basligi tekrar etmeyen yeni bilgi veren tek kisa cumle, en fazla 100 karakter.
TUR: haberin merkezinde bir kisinin dogrudan sozu varsa 'alinti', yoksa 'haber'. alinti ise SOZ: sozun aynisi (en fazla
110 karakter; uzunsa tamamlanmis tek cumleyle sinirla, kelime degistirme), KISI: sozun sahibinin adi soyadi,
UNVAN: gorevi (metinde yaziyorsa; yoksa bos). Alinti degilse soz/kisi/unvan bos birak.
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


GEMINI_MODELS = ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-flash-latest"]  # yedek liste
_found = None   # Google'dan sorulan guncel model listesi


def _discover():
    """Google'a hangi flash modelleri acik diye sorar; en yeniden eskiye siralar. Olmazsa yedek liste."""
    global _found
    if _found is not None:
        return _found
    _found = []
    try:
        req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                                     headers={"x-goog-api-key": GEMINI})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        rows = []
        for m in data.get("models", []):
            n = m.get("name", "").replace("models/", "")
            if "flash" not in n or "generateContent" not in m.get("supportedGenerationMethods", []):
                continue
            if re.search(r"image|tts|live|audio|embed|exp|thinking|robot|vision|computer", n):
                continue
            v = [int(x) for x in re.findall(r"\d+", n.split("flash")[0])] or [0]
            rows.append((1 if "preview" in n else 0, 1 if "lite" in n else 0, [-x for x in v], n))
        rows.sort()  # kararli once, sonra lite degil, sonra en yeni surum
        _found = [r[3] for r in rows][:5]
    except Exception:  # noqa: BLE001
        _found = []
    return _found

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
    """Modelleri sirayla dener; yogunluk (503/429) olursa digerine gecer, hepsi yogunsa bir kez bekleyip yeniden dener."""
    import time
    global _gm
    models = ([_gm] if _gm else []) + [m for m in _discover() + GEMINI_MODELS if m != _gm]
    models = list(dict.fromkeys(models))
    errs, busy = [], None
    for tur in (0, 1):
        errs, busy = [], None
        for m in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
            cfg = {"temperature": 0.2, "maxOutputTokens": 800}
            if not strict:
                cfg["responseMimeType"] = "application/json"
            body = {"systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": user}]}], "generationConfig": dict(cfg)}
            body["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}
            try:
                data, err = _http(url, {"x-goog-api-key": GEMINI}, body, f"g/{m}")
                if data is None and "HTTP 400" in err:  # modelin dusunme ayari yoksa onsuz dene
                    body["generationConfig"] = dict(cfg)
                    data, err = _http(url, {"x-goog-api-key": GEMINI}, body, f"g/{m}")
            except AiBusy as e:
                busy = e
                errs.append(str(e))
                continue
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
        if busy is None:
            break
        if tur == 0:
            time.sleep(4)
    if busy is not None and not any("HTTP 4" in e and "HTTP 429" not in e for e in errs):
        raise busy
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
    if busy:  # gecici yogunluk: hata sayma, sonra yeniden denenir
        raise busy
    raise RuntimeError("v5 " + " | ".join(errs + ([str(busy)] if busy else [])))


def analyze(title, paragraphs, source="", tg=False):
    """(uygun, metin, iddia, neden, baslik, kategori, extra) dondurur; extra: vurgu, anahtar, ozet, tur, soz, kisi, unvan. Hata: AiBusy veya RuntimeError."""
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
    bas = re.sub(r"\s+", " ", (j.get("baslik") or "")).strip()[:48]
    cl = lambda k, n: re.sub(r"\s+", " ", str(j.get(k) or "")).strip()[:n]
    extra = dict(vurgu=cl("vurgu", 40), anahtar=cl("anahtar", 24), ozet=cl("ozet", 110), tur=("alinti" if cl("tur", 10) == "alinti" else "haber"), soz=cl("soz", 140), kisi=cl("kisi", 40), unvan=cl("unvan", 50))
    return ok, f"{body}{credit}", bool(j.get("iddia")), (j.get("neden") or "")[:120], bas, (j.get("kategori") or "").strip(), extra
