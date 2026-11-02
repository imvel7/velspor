"""Vel Spor haber botu: haberleri toplar, gorsele cevirir, Telegram'a yollar.
HEADLINE ortam degiskeni doluysa elle kart uretir."""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ai
from ozet import build_post, fetch_paragraphs
from net import rss_fetch, tg_configured, tg_send_message, tg_send_photo
from render import CATS, LEVELS, make
from rules import FEEDS, classify, clean_title, is_claim, level_for, note_for, short_for, tr_lower


ROOT = Path(__file__).resolve().parent
STATE = ROOT / "state" / "seen.json"
OUT = ROOT / "out"

MAX_PER_RUN = 4      # tek calismada en fazla kac gorsel
MAX_FIRST_RUN = 3    # ilk calismada kac gorsel (geri kalani sessizce 'goruldu' isaretlenir)
MAX_AGE_HOURS = 12   # bundan eski haberler atlanir
MAX_TITLE = 95
MAX_AI_CALLS = 12     # tek calismada en fazla yapay zeka istegi
SEND_UNMATCHED = False  # kisa basligi bulunamayan haberler gonderilmesin


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=0), encoding="utf-8")


def tokens(title):
    return {w[:4] for w in re.findall(r"\w+", tr_lower(title)) if len(w) > 2}


def similar(a, b):
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= 0.5


def short_title(t):
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) <= MAX_TITLE:
        return t
    cut = t[:MAX_TITLE].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:-") + "…"


def collect(feed):
    """Bir kaynaktan haberleri al. (haberler, hata) dondurur."""
    try:
        raw = rss_fetch(feed["url"])
    except Exception as e:  # noqa: BLE001
        return [], f"{type(e).__name__}: {e}"
    now = datetime.now(timezone.utc)
    out = []
    for it in raw:
        title = it["title"]
        source = feed["name"]
        if "news.google.com" in feed["url"]:
            if it["source"]:
                source = it["source"]
                suffix = " - " + it["source"]
                if title.endswith(suffix):
                    title = title[: -len(suffix)]
            elif " - " in title:
                title, source = title.rsplit(" - ", 1)
        if feed["filter"] and "galatasaray" not in tr_lower(title + " " + it["summary"]):
            continue
        if it["date"] and now - it["date"] > timedelta(hours=MAX_AGE_HOURS):
            continue
        out.append(dict(
            id=it["id"], title=title, link=it["link"], source=source,
            ts=(it["date"] or now).timestamp(), hint=feed["hint"], official=feed["official"],
        ))
    return out, None


def main():
    state = load_state()
    first_run = not state.get("ids")
    seen_ids = set(state.get("ids", []))
    seen_titles = list(state.get("titles", []))
    dry = not tg_configured()
    if dry:
        print("Telegram bilgileri yok: DRY RUN (gorseller out/ klasorune yazilir)")

    # 1) topla
    health, items = [], []
    for feed in FEEDS:
        got, err = collect(feed)
        health.append((feed["name"], len(got), err))
        items.extend(got)
        print(f"{'OK ' if not err else 'ERR'} {feed['name']}: {len(got)} {err or ''}")

    # 2) yeni olanlari ayikla
    fresh, seen_in_run = [], set()
    for it in sorted(items, key=lambda x: -x["ts"]):
        if it["id"] in seen_ids or it["id"] in seen_in_run:
            continue
        seen_in_run.add(it["id"])
        fresh.append(it)

    # 3) benzer basliklari ele (ayni haber farkli sitelerde)
    chosen, dropped_ids = [], []
    known = list(seen_titles)
    for it in fresh:
        if any(similar(it["title"], k) for k in known):
            dropped_ids.append(it["id"])
            continue
        known.append(it["title"])
        it["short"] = short_for(it["title"])
        if not it["short"] and not SEND_UNMATCHED:
            dropped_ids.append(it["id"])
            continue
        it["cat"] = classify(it["title"], it["hint"])
        it["claim"] = is_claim(it["title"], it["cat"], it["official"])
        it["level"] = level_for(it["title"], it["cat"], it["claim"])
        chosen.append(it)

    # 4) oncelik: A, sonra B, sonra C; kendi icinde yeniden eskiye
    order = {"A": 0, "B": 1, "C": 2}
    chosen.sort(key=lambda x: (order[x["level"]], -x["ts"]))
    limit = MAX_FIRST_RUN if first_run else MAX_PER_RUN

    OUT.mkdir(exist_ok=True)
    sent, idx, busy, ai_calls, ai_err = 0, 0, False, 0, ""
    for i, it in enumerate(chosen):
        if sent >= limit:
            break
        idx = i + 1
        paras = fetch_paragraphs(it["link"]) if it["link"] else []
        claim, post = it["claim"], None
        if ai.ENABLED and not ai_err:
            if busy or ai_calls >= MAX_AI_CALLS:
                continue  # limit dolu: haber isaretlenmez, sonraki calismada tekrar denenir
            try:
                ai_calls += 1
                ok, post, ai_claim, why = ai.analyze(it["title"], paras or [it.get("summary", "")], it["source"])
            except ai.AiBusy as e:
                busy = True
                print("Yapay zeka mesgul, sonra denenecek:", e)
                continue
            except Exception as e:  # noqa: BLE001
                ai_err = str(e)[:150]
                print("Yapay zeka hatasi:", ai_err)
                post = None
            else:
                if not ok:
                    print("Elendi:", it["title"][:60], "|", why)
                    dropped_ids.append(it["id"])
                    continue
                claim = claim or ai_claim
        if post is None:
            post = build_post(it["title"], it.get("summary", ""), paras, claim)
        path = OUT / f"haber_{int(it['ts'])}_{i}.png"
        make(it["cat"], it["level"], it["short"] or it["cat"], it["source"], path, claim=claim, note=note_for(it["short"]))
        btn = f"🔗 Kaynak · {it['source']}"
        if not paras and not it.get("summary"):
            btn += " (sadece başlık)"
        try:
            if not dry:
                tg_send_photo(path, post, button=(btn, it["link"]))
            sent += 1
            seen_ids.add(it["id"])
            seen_titles.append(it["title"])
        except Exception as e:  # noqa: BLE001
            print("Gonderim hatasi:", e)
    rest = chosen[idx:]
    if ai_err and not dry:
        try:
            tg_send_message("⚠️ Yapay zeka çalışmadı, bu haberler eski yöntemle yazıldı.\nHata: " + ai_err)
        except Exception:  # noqa: BLE001
            pass

    # ilk calismada kalanlari sessizce 'goruldu' say; sonraki calismalarda kalanlar siraya girer
    if first_run:
        for it in rest:
            seen_ids.add(it["id"])
            seen_titles.append(it["title"])
    for i in dropped_ids:
        seen_ids.add(i)

    # 5) saglik raporu
    if first_run or os.environ.get("HEALTH_REPORT") == "1":
        lines = ["Kaynak sağlık raporu:"]
        for name, n, err in health:
            lines.append(f"{'✅' if not err else '❌'} {name}: {n} haber" + (f" ({err[:60]})" if err else ""))
        report = "\n".join(lines)
        print(report)
        if not dry:
            try:
                tg_send_message(report)
            except Exception as e:  # noqa: BLE001
                print("Rapor gonderilemedi:", e)

    state["ids"] = list(seen_ids)[-1500:]
    state["titles"] = seen_titles[-300:]
    save_state(state)
    print(f"Bitti: {sent} gorsel hazirlandi, {len(rest)} haber siraya kaldi.")
    return 0


def manual_main():
    cat = os.environ.get("CATEGORY", "Gündem")
    level = os.environ.get("LEVEL", "A")
    text = os.environ.get("HEADLINE", "").strip()
    source = os.environ.get("SOURCE", "Vel Spor").strip() or "Vel Spor"
    claim = os.environ.get("CLAIM", "false").lower() == "true"
    note = os.environ.get("NOTE", "").strip() or note_for(text.upper())
    if not text:
        print("Baslik bos")
        return 1
    if cat not in CATS:
        cat = "Gündem"
    if level not in LEVELS:
        level = "B"
    OUT.mkdir(exist_ok=True)
    path = OUT / "manuel.png"
    make(cat, level, text, source, path, claim=claim, note=note)
    caption = f"{cat} · {LEVELS[level].title()}{' · İDDİA' if claim else ''}\n\n{text}\n\nKaynak: {source}"
    if tg_configured():
        tg_send_photo(path, caption)
        print("Telegram'a gonderildi")
    else:
        print("DRY RUN:", path)
    return 0


if __name__ == "__main__":
    if os.environ.get("HEADLINE", "").strip():
        sys.exit(manual_main())
    sys.exit(main())
