"""Siniflandirma kurallari ve haber kaynaklari."""
import re
from urllib.parse import quote_plus


def tr_lower(s):
    return s.replace("İ", "i").replace("I", "ı").lower()


# Sira onemli: ustteki kural once denenir.
RULES = [
    ("Disiplin ve Ceza", r"pfdk|disipline sevk|\bceza|kırmızı kart|sarı kart|hak mahrumiyeti"),
    ("Sakatlık", r"sakatl|\bsakat\b|ameliyat|tedavi|kas yırtığı|sezonu kapattı|dönüş tarihi|forma giyemeyecek"),
    ("Özel Gün", r"doğum günü|yıl dönümü|anıyoruz|rahmetle|vefat|hatırlıyoruz"),
    ("Transfer", r"transfer|bonservis|imzay|imza at|kiralık|teklif|ilgileniyor|sözleşme|anlaşma sağla|anlaştı|takip ediyor|peşinde|gözüne kestirdi|renklerine"),
    ("Avrupa", r"uefa|şampiyonlar ligi|avrupa ligi|konferans ligi|\bkura\b"),
    ("Maç Öncesi", r"hakem|ilk 11|muhtemel 11|maç kadrosu|saat kaçta|hangi kanalda|şifresiz|maç öncesi"),
    ("Puan Durumu", r"puan durumu|puan farkı|liderlik|şampiyonluk yarışı|averaj"),
    ("Antrenman", r"antrenman|idman|\bkamp"),
    ("Taraftar ve Stadyum", r"bilet|taraftar|kombine|tribün|stadyum|koreografi|deplasman yasağı"),
    ("Kulüp ve Yönetim", r"başkan|yönetim|\bkap\b|resmi açıklama|sponsor|kongre|divan|kulüpten"),
    ("Oyuncu Performansı", r"asist|istatistik|rekor|gol sayısı|maçın adamı|maçın oyuncusu|gol krallığı|performans"),
    ("Maç İçi", r"\bgol(ü|le|ler|ünü)?\b|penaltı|\bvar\b|maç sonucu|maç sona erdi|ilk yarı|devre arası|canlı anlatım"),
    ("Açıklamalar", r"açıklama|konuştu|röportaj|basın toplantısı|\bdedi\b|okan buruk"),
]

OFFICIAL = re.compile(r"resmen|resmi olarak|imzayı attı|imzaladı|kap'a|kap’a|duyurdu|açıkladı|açıklandı")
CLAIM = re.compile(
    r"iddia(?!lı)|kulis|ilgileniyor|takip ediyor|gündemde|gelebilir|\?|görüşme|istiyor|peşinde|masada|hedefte|"
    r"gelecek mi|ayrılacak mı|olabilir|bekleniyor"
)
BREAKING = re.compile(r"son dakika|resmen|ilk 11|kırmızı kart|imzayı attı|ameliyat edildi|ayrıldı")


def classify(title, hint=None):
    t = tr_lower(title)
    for cat, pattern in RULES:
        if re.search(pattern, t):
            return cat
    return hint or "Gündem"


def is_claim(title, category, official_source):
    if official_source:
        return False
    t = tr_lower(title)
    if OFFICIAL.search(t):
        return False
    if category == "Transfer":
        return True  # resmi dil yoksa transfer haberi 'iddia' sayilir
    return bool(CLAIM.search(t))


def level_for(title, category, claim):
    t = tr_lower(title)
    if category == "Özel Gün":
        return "C"
    if claim and "son dakika" not in t:
        return "B"
    if category == "Maç İçi" or BREAKING.search(t):
        return "A"
    return "B"


GN = "https://news.google.com/rss/search?q={q}&hl=tr&gl=TR&ceid=TR:tr"


def gn(query):
    return GN.format(q=quote_plus(query + " when:1d"))


FEEDS = [
    dict(name="Galatasaray SK", url="https://www.galatasaray.org/xml/gs.rss", official=True, filter=False, hint=None),
    dict(name="A Spor", url="https://www.aspor.com.tr/rss/galatasaray.xml", official=False, filter=False, hint=None),
    dict(name="Fotomaç", url="https://www.fotomac.com.tr/rss/Galatasaray.xml", official=False, filter=False, hint=None),
    dict(name="Ajansspor", url="https://ajansspor.com/rss", official=False, filter=True, hint=None),
]


PREFIX = re.compile(r"^\s*(son dakika( spor haberi)?|flaş|flas|özel haber)\s*[|:!\-–—]+\s*", re.IGNORECASE)


def clean_title(t):
    """Basligin basindaki 'SON DAKIKA |' gibi tekrar eden onekleri at."""
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+[-–|]\s+[^-–|]{0,40}(haberleri|haber|spor)\s*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+[-–|]\s+galatasaray\s*$", "", t, flags=re.IGNORECASE)
    for _ in range(2):
        t2 = PREFIX.sub("", tr_lower(t))
        if len(t2) < len(tr_lower(t)):
            t = t[len(t) - len(t2):] if len(t) == len(tr_lower(t)) else t
            t = t[:1].upper() + t[1:]
        else:
            break
    return t
