#!/usr/bin/env python3
"""Deutsch Lernen — servidor local. Solo usa la biblioteca estándar de Python.

Uso:  python3 server.py [--port 8765] [--auto-exit] [--no-browser]
Abre http://127.0.0.1:8765 en el navegador.
"""
import argparse
import hashlib
import io
import json
import mimetypes
import os
import random
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zipfile
from collections import Counter, defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import fsrs  # noqa: E402
from content import CONTENT, LEVELS, SKILLS  # noqa: E402
from store import Store  # noqa: E402

VERSION = "1.2 · fase 1"
STATIC = os.path.join(HERE, "static")
STORE = None
LAST_PING = time.time()
AZURE_VOICES = [
    ("de-DE-SeraphinaMultilingualNeural", "Seraphina · Alemania · mujer · la más natural"),
    ("de-DE-FlorianMultilingualNeural", "Florian · Alemania · hombre · la más natural"),
    ("de-DE-KatjaNeural", "Katja · Alemania · mujer"),
    ("de-DE-ConradNeural", "Conrad · Alemania · hombre"),
    ("de-CH-LeniNeural", "Leni · Suiza · mujer"),
    ("de-CH-JanNeural", "Jan · Suiza · hombre"),
    ("de-AT-IngridNeural", "Ingrid · Austria · mujer"),
    ("de-AT-JonasNeural", "Jonas · Austria · hombre"),
]


# ====================================================================== tiempo
def today():
    return time.strftime("%Y-%m-%d")


def end_of_today():
    t = time.localtime()
    return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 23, 59, 59, 0, 0, -1))


def day_str(offset_days):
    return time.strftime("%Y-%m-%d", time.localtime(time.time() - offset_days * 86400))


# ====================================================================== nivel y ruta
def user_level():
    lv = STORE.settings().get("level") or "A1"
    return lv if lv in LEVELS else "A1"


def recent_accuracy(n=80):
    rows = STORE.query("SELECT correct FROM answers WHERE requeue = 0 ORDER BY id DESC LIMIT ?", (n,))
    if len(rows) < 10:
        return 0.8
    return sum(r["correct"] for r in rows) / len(rows)


def frontier_unit(cards=None):
    cards = cards if cards is not None else STORE.cards()
    lv_idx = LEVELS.index(user_level())
    for lv in CONTENT.plan["levels"][lv_idx:]:
        for u in lv["units"]:
            ids = CONTENT.unit_items(u)
            if any(i not in cards for i in ids):
                return lv["id"], u
    last = CONTENT.plan["levels"][-1]
    return last["id"], last["units"][-1]


def new_candidates(cards, kinds=("vocab", "verb", "phrase")):
    lv_idx = LEVELS.index(user_level())
    allowed = set(LEVELS[: lv_idx + 1])
    pool = [i for i in CONTENT.ordered_new_pool()
            if i not in cards and CONTENT.items[i]["kind"] in kinds
            and CONTENT.items[i].get("level", "A1") in allowed]
    current = [i for i in pool if CONTENT.items[i].get("level") == LEVELS[lv_idx]]
    lower = [i for i in pool if CONTENT.items[i].get("level") != LEVELS[lv_idx]]
    # 80 % del nivel actual (en orden de la ruta), 20 % de huecos de niveles anteriores
    out, ci, li = [], 0, 0
    while ci < len(current) or li < len(lower):
        for _ in range(4):
            if ci < len(current):
                out.append(current[ci])
                ci += 1
        if li < len(lower):
            out.append(lower[li])
            li += 1
    return out


def pick_type(it, card):
    reps = card["reps"] if card else 0
    types = CONTENT.exercise_types(it, reps)
    return random.choice(types) if types else None


# ====================================================================== sesiones
def build_daily():
    s = STORE.settings()
    minutes = int(s.get("minutes") or 30)
    target = max(12, round(minutes * 1.8))
    level = user_level()
    cards = STORE.cards()
    eod = end_of_today()
    due = [i for i, c in cards.items() if c["due"] <= eod and i in CONTENT.items]
    # primero lo fallado recientemente y lo más atrasado
    due.sort(key=lambda i: (-cards[i]["lapses"], cards[i]["due"]))
    acc = recent_accuracy()

    new_quota = max(3, round(minutes / 3))
    if acc > 0.86:
        new_quota = round(new_quota * 1.3)
    elif acc < 0.65:
        new_quota = max(2, round(new_quota * 0.5))
    if len(due) > target * 0.7:
        new_quota = min(new_quota, 3)

    review_ids = due[: int(target * 0.55)]
    reviews = [CONTENT.make(CONTENT.items[i], pick_type(CONTENT.items[i], cards[i]), level)
               for i in review_ids if pick_type(CONTENT.items[i], cards[i])]

    news = new_candidates(cards)[:new_quota]

    # gramática: la de la unidad actual + temas débiles
    _, unit = frontier_unit(cards)
    topics = list(unit.get("grammar", [])) + weak_topics(2)
    gram_pool = [i for i, it in CONTENT.items.items()
                 if it["kind"] == "gram" and it["topic"] in topics and i not in review_ids
                 and LEVELS.index(it["level"]) <= LEVELS.index(level)]
    random.shuffle(gram_pool)
    gram_pool.sort(key=lambda i: i in cards)  # primero los no vistos
    gram_n = max(3, round(target * 0.18))
    grams = [CONTENT.make(CONTENT.items[i], "gram", level) for i in gram_pool[:gram_n]]

    # suizo: dos expresiones nuevas al día
    swiss_new = [i for i, it in CONTENT.items.items() if it["kind"] == "swiss" and i not in cards]
    swiss_new = swiss_new[:2]

    seq = interleave(reviews, grams, news + swiss_new, level, target)
    return finalize(seq, "daily", {"reviews": len(reviews), "new": len(news), "swiss": len(swiss_new),
                                   "grammar": len(grams), "topics": [CONTENT.sheets[t]["title"] for t in unit.get("grammar", [])],
                                   "unit": unit["title"]})


def interleave(reviews, grams, news, level, target):
    fillers = reviews + grams
    # repaso primero, gramática mezclada
    random.shuffle(grams)
    fillers = []
    gi = 0
    for idx, r in enumerate(reviews):
        fillers.append(r)
        if idx % 3 == 2 and gi < len(grams):
            fillers.append(grams[gi])
            gi += 1
    fillers += grams[gi:]

    seq, pending = [], deque()
    news = list(news)
    fi = 0
    since_intro = 3
    while news or fi < len(fillers) or pending:
        pos = len(seq)
        if pending and pending[0][0] <= pos:
            seq.append(pending.popleft()[1])
            continue
        if news and since_intro >= 2:
            iid = news.pop(0)
            it = CONTENT.items[iid]
            seq.append(CONTENT.make(it, "intro", level))
            types = CONTENT.exercise_types(it, 0)
            first = random.choice(types)
            pending.append((pos + 3, CONTENT.make(it, first, level)))
            others = [t for t in types if t != first]
            if others and it["kind"] in ("vocab", "verb"):
                pending.append((pos + 9, CONTENT.make(it, random.choice(others), level)))
            pending = deque(sorted(pending, key=lambda x: x[0]))
            since_intro = 0
            continue
        if fi < len(fillers):
            seq.append(fillers[fi])
            fi += 1
            since_intro += 1
            continue
        if pending:
            seq.append(pending.popleft()[1])
            since_intro += 1
            continue
        since_intro = 99
    # relleno: refuerzo de lo aprendido hace poco si sobra tiempo
    if len(seq) < target:
        cards = STORE.cards()
        recent = [i for i, c in cards.items() if c["reps"] < 4 and i in CONTENT.items
                  and CONTENT.items[i]["kind"] in ("vocab", "verb", "phrase")]
        random.shuffle(recent)
        for i in recent[: target - len(seq)]:
            t = pick_type(CONTENT.items[i], cards[i])
            if t:
                seq.append(CONTENT.make(CONTENT.items[i], t, level))
    return seq


def finalize(seq, kind, summary):
    for n, ex in enumerate(seq):
        ex["n"] = n
    return {"kind": kind, "created": time.time(), "exercises": seq, "summary": summary,
            "block_size": int(STORE.settings().get("block_size") or 8)}


def build_practice(kind, ref):
    level = user_level()
    cards = STORE.cards()
    if kind == "theme":
        ids = list(CONTENT.themes.get(ref, {}).get("items", []))
    elif kind == "sheet":
        ids = [i for i, it in CONTENT.items.items() if it["kind"] == "gram" and it["topic"] == ref]
    elif kind == "swiss":
        ids = [i for i, it in CONTENT.items.items() if it["kind"] == "swiss" and (not ref or it["group"] == ref)]
    elif kind == "phrases":
        ids = [i for i, it in CONTENT.items.items() if it["kind"] == "phrase" and it["group"] == ref]
    elif kind == "verbs":
        ids = [i for i, it in CONTENT.items.items() if it["kind"] == "verb"
               and LEVELS.index(it["level"]) <= LEVELS.index(level)]
        random.shuffle(ids)
        ids = ids[:16]
    elif kind == "weak":
        ids = [w["item"] for w in weak_items(20)]
    else:
        ids = []
    random.shuffle(ids)
    ids = ids[:18]
    seq = []
    new = [i for i in ids if i not in cards and CONTENT.items[i]["kind"] != "gram"]
    known = [i for i in ids if i not in new]
    exercises = []
    for i in known:
        t = pick_type(CONTENT.items[i], cards.get(i))
        if t:
            exercises.append(CONTENT.make(CONTENT.items[i], t, level))
    seq = interleave(exercises, [], new, level, 0)
    title = {"theme": CONTENT.themes.get(ref, {}).get("title"), "sheet": CONTENT.sheets.get(ref, {}).get("title"),
             "weak": "Puntos débiles", "verbs": "Verbos", "swiss": "Suizo-alemán", "phrases": "Expresiones"}.get(kind)
    return finalize(seq, kind, {"title": title or "Práctica", "new": len(new), "reviews": len(known)})


def answer(data):
    iid = data.get("item")
    if iid not in CONTENT.items:
        return {"ok": False}
    correct = bool(data.get("correct"))
    requeue = bool(data.get("requeue"))
    it = CONTENT.items[iid]
    STORE.log_answer(today(), iid, data.get("type", ""), data.get("skill"), it.get("level"),
                     correct, int(data.get("ms") or 0), requeue)
    if not requeue:
        card = STORE.card(iid) or fsrs.new_card()
        STORE.save_card(iid, fsrs.review(card, 3 if correct else 1))
    return {"ok": True}


def introduce(iid):
    """Crea la tarjeta al ver la presentación (aún sin nota)."""
    if iid in CONTENT.items and STORE.card(iid) is None:
        c = fsrs.new_card()
        c["due"] = time.time() + 600
        STORE.save_card(iid, c)
    return {"ok": True}


def finish(data):
    total = int(data.get("total") or 0)
    correct = int(data.get("correct") or 0)
    seconds = int(data.get("seconds") or 0)
    xp = correct * 10 + (total - correct) * 2 + (50 if data.get("complete") else 0)
    STORE.execute("INSERT INTO sessions (day, started, finished, seconds, total, correct, xp, kind) VALUES (?,?,?,?,?,?,?,?)",
                  (today(), time.time() - seconds, time.time(), seconds, total, correct, xp, data.get("kind", "daily")))
    msg = maybe_level_up()
    return {"ok": True, "xp": xp, "streak": streak(), "level_up": msg}


def maybe_level_up():
    level = user_level()
    if level == LEVELS[-1]:
        return None
    cards = STORE.cards()
    ids = [i for i in CONTENT.level_items(level) if CONTENT.items[i]["kind"] != "gram"]
    if not ids:
        return None
    seen = sum(1 for i in ids if i in cards) / len(ids)
    if seen >= 0.85 and recent_accuracy(120) >= 0.75:
        nxt = LEVELS[LEVELS.index(level) + 1]
        STORE.set_settings({"level": nxt})
        return nxt
    return None


# ====================================================================== estadísticas
def active_days():
    rows = STORE.query("SELECT day, COUNT(*) AS n FROM answers GROUP BY day")
    return {r["day"]: r["n"] for r in rows}


def streak():
    """Racha flexible: un día sin practicar cada 7 días no la rompe."""
    days = active_days()

    def active(o):
        return days.get(day_str(o), 0) >= 10

    o = 0 if active(0) else 1
    count, last_freeze = 0, None
    while o < 400:
        if active(o):
            count += 1
            o += 1
            continue
        if count > 0 and (last_freeze is None or o - last_freeze >= 7) and active(o + 1):
            last_freeze = o
            o += 1
            continue
        break
    return count


def weak_topics(n=3):
    rows = STORE.query("""SELECT item, correct FROM answers WHERE item LIKE 'g:%' AND requeue = 0
                          ORDER BY id DESC LIMIT 400""")
    stats = defaultdict(lambda: [0, 0])
    for r in rows:
        topic = r["item"].split(":")[1]
        stats[topic][0] += r["correct"]
        stats[topic][1] += 1
    scored = [(c / t, k) for k, (c, t) in stats.items() if t >= 3 and c / t < 0.75]
    return [k for _, k in sorted(scored)[:n]]


def weak_items(n=10):
    since = day_str(30)
    rows = STORE.query("""SELECT item, SUM(1 - correct) AS wrong, COUNT(*) AS total FROM answers
                          WHERE day >= ? AND requeue = 0 GROUP BY item HAVING wrong > 0
                          ORDER BY wrong DESC, total DESC LIMIT ?""", (since, n * 2))
    out = []
    for r in rows:
        it = CONTENT.items.get(r["item"])
        if not it:
            continue
        label = CONTENT.display(it) if it["kind"] != "gram" else CONTENT.sheets[it["topic"]]["title"]
        out.append({"item": r["item"], "label": label, "kind": it["kind"], "wrong": r["wrong"],
                    "total": r["total"], "es": it.get("es", it.get("x", "")),
                    "art": it.get("art", "")})
        if len(out) >= n:
            break
    return out


def progress():
    cards = STORE.cards()
    days = active_days()
    heat = [{"day": day_str(o), "n": days.get(day_str(o), 0)} for o in range(83, -1, -1)]
    skills = {}
    for sk, label in SKILLS.items():
        rows = STORE.query("SELECT level, correct FROM answers WHERE skill = ? AND requeue = 0 ORDER BY id DESC LIMIT 300", (sk,))
        acc = sum(r["correct"] for r in rows) / len(rows) if rows else None
        est = None
        for lv in LEVELS:
            sub = [r for r in rows if r["level"] == lv]
            if len(sub) >= 8 and sum(r["correct"] for r in sub) / len(sub) >= 0.7:
                est = lv
        skills[sk] = {"label": label, "accuracy": acc, "n": len(rows), "level": est}
    vocab = [i for i in cards if i.startswith("v:")]
    learned = [i for i in vocab if cards[i]["state"] == fsrs.REVIEW and cards[i]["reps"] >= 2]
    mastered = [i for i in vocab if cards[i]["s"] >= 21]
    levels = []
    for lv in CONTENT.plan["levels"]:
        units = []
        for u in lv["units"]:
            ids = CONTENT.unit_items(u)
            seen = sum(1 for i in ids if i in cards)
            known = sum(1 for i in ids if i in cards and cards[i]["state"] == fsrs.REVIEW and cards[i]["s"] >= 3)
            units.append({"title": u["title"], "total": len(ids), "seen": seen, "known": known,
                          "vocab": [CONTENT.themes[t]["title"] for t in u.get("vocab", [])],
                          "grammar": [{"id": g, "title": CONTENT.sheets[g]["title"]} for g in u.get("grammar", [])],
                          "themes": u.get("vocab", [])})
        levels.append({"id": lv["id"], "title": lv["title"], "cando": lv["cando"], "exam": lv["exam"], "units": units})
    xp = STORE.query("SELECT COALESCE(SUM(xp),0) AS xp, COALESCE(SUM(seconds),0) AS sec FROM sessions")[0]
    today_row = STORE.query("SELECT COUNT(*) AS n, COALESCE(SUM(correct),0) AS c FROM answers WHERE day = ? AND requeue = 0", (today(),))[0]
    week = [{"day": day_str(o), "n": days.get(day_str(o), 0)} for o in range(6, -1, -1)]
    return {"streak": streak(), "heat": heat, "week": week, "skills": skills,
            "words": {"seen": len(vocab), "learned": len(learned), "mastered": mastered.__len__(),
                      "total": sum(1 for i in CONTENT.items if i.startswith("v:"))},
            "weak": weak_items(8), "weak_topics": [{"id": t, "title": CONTENT.sheets[t]["title"]} for t in weak_topics(3)],
            "levels": levels, "level": user_level(), "xp": xp["xp"], "minutes": round(xp["sec"] / 60),
            "today": today_row, "due": len([1 for c in cards.values() if c["due"] <= end_of_today()])}


def home():
    s = STORE.settings()
    cards = STORE.cards()
    lv, unit = frontier_unit(cards)
    due = len([1 for i, c in cards.items() if c["due"] <= end_of_today() and i in CONTENT.items])
    done = STORE.query("SELECT COUNT(*) AS n FROM sessions WHERE day = ? AND kind = 'daily'", (today(),))[0]["n"]
    days = active_days()
    week = [{"day": day_str(o), "n": days.get(day_str(o), 0),
             "label": "LMXJVSD"[time.localtime(time.time() - o * 86400).tm_wday]} for o in range(6, -1, -1)]
    return {"level": user_level(), "placement_done": s.get("placement_done"), "minutes": s.get("minutes"),
            "due": due, "new": len(new_candidates(cards)[: max(3, round(int(s.get('minutes') or 30) / 3))]),
            "unit": {"level": lv, "title": unit["title"],
                     "grammar": [{"id": g, "title": CONTENT.sheets[g]["title"]} for g in unit.get("grammar", [])],
                     "vocab": [{"id": t, "title": CONTENT.themes[t]["title"], "icon": CONTENT.themes[t]["icon"]} for t in unit.get("vocab", [])]},
            "done_today": done > 0, "streak": streak(), "week": week, "version": VERSION,
            "cards": len(cards), "name": s.get("name", "")}


# ====================================================================== biblioteca
def status_of(card):
    if not card:
        return "new"
    if card["state"] == fsrs.REVIEW and card["s"] >= 7:
        return "known"
    return "learning"


def library():
    cards = STORE.cards()
    themes = []
    for th in CONTENT.vocab["themes"]:
        items = []
        for iid in CONTENT.themes[th["id"]]["items"]:
            it = CONTENT.items[iid]
            items.append(dict(CONTENT.card(it), id=iid, status=status_of(cards.get(iid))))
        themes.append({"id": th["id"], "title": th["title"], "level": th["level"], "icon": th["icon"], "items": items})
    verbs = []
    for it in (x for x in CONTENT.items.values() if x["kind"] == "verb"):
        f = CONTENT.verb_forms(it)
        verbs.append({"id": it["id"], "inf": it["inf"], "es": it["es"], "level": it["level"], "tags": it["tags"],
                      "prep": it.get("prep", ""), "note": it.get("note", ""), "ex": it["ex"], "exs": it["exs"],
                      "forms": f, "imp": it.get("imp"), "aux": it["aux"], "part": it["part"],
                      "futur": [f"{w} {it['inf'].replace('sich ', '')}" for w in ["werde", "wirst", "wird", "werden", "werdet", "werden"]],
                      "status": status_of(cards.get(it["id"]))})
    phrases = []
    for g in CONTENT.phrases["groups"]:
        phrases.append({"id": g["id"], "title": g["title"], "level": g["level"], "icon": g["icon"],
                        "items": [{"de": r[0], "es": r[1], "note": r[2] if len(r) > 2 else ""} for r in g["items"]]})
    return {"themes": themes, "verbs": verbs, "pronouns": CONTENT.verbs_raw["pronouns"],
            "sheets": [{k: s[k] for k in ("id", "level", "icon", "title", "summary", "html")} for s in CONTENT.grammar["sheets"]],
            "phrases": phrases, "swiss": CONTENT.swiss}


def placement_questions():
    out = []
    for lv, q, opts, ans in CONTENT.plan["placement"]:
        o = list(opts)
        correct = o[ans]
        random.shuffle(o)
        out.append({"level": lv, "q": q, "options": o, "answer": o.index(correct)})
    return out


def placement_result(data):
    scores = data.get("scores", {})
    start = LEVELS[-1]
    for lv in LEVELS:
        if scores.get(lv, 0) < 5:      # 5 de 6 = nivel superado
            start = lv
            break
    STORE.set_settings({"level": start, "placement_done": True})
    return {"level": start}


# ====================================================================== voz Azure (opcional)
def azure_tts(text, voice, rate):
    s = STORE.settings()
    key, region = s.get("azure_key"), (s.get("azure_region") or "westeurope").strip()
    if not key:
        return None, "sin-clave"
    voice = voice or s.get("azure_voice") or "de-DE-KatjaNeural"
    rate = float(rate or s.get("rate") or 1.0)
    h = hashlib.sha1(f"{voice}|{rate:.2f}|{text}".encode()).hexdigest()
    path = os.path.join(STORE.dir, "audio", h + ".mp3")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read(), None
    lang = "-".join(voice.split("-")[:2])
    esc = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    pct = round((rate - 1) * 100)
    ssml = (f"<speak version='1.0' xml:lang='{lang}'><voice name='{voice}'>"
            f"<prosody rate='{pct:+d}%'>{esc}</prosody></voice></speak>")
    req = urllib.request.Request(
        os.environ.get("DL_AZURE_URL") or f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
        data=ssml.encode("utf-8"),
        headers={"Ocp-Apim-Subscription-Key": key, "Content-Type": "application/ssml+xml",
                 "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3", "User-Agent": "DeutschLernen"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            audio = r.read()
    except urllib.error.HTTPError as e:
        return None, f"azure-{e.code}"
    except Exception as e:  # sin conexión, etc.
        return None, f"red: {e.__class__.__name__}"
    with open(path, "wb") as f:
        f.write(audio)
    return audio, None


PREFETCH = {"running": False, "done": 0, "total": 0, "errors": 0, "last_error": None}


def all_audio_texts():
    s = STORE.settings()
    std, ch = s.get("azure_voice"), s.get("azure_voice_ch")
    out = []
    for it in CONTENT.items.values():
        k = it["kind"]
        if k == "vocab":
            out += [(CONTENT.display(it), std), (it["ex"], std)]
        elif k == "verb":
            out += [(it["inf"], std), (it["ex"], std)]
        elif k == "gram" and "→" not in it["full"]:
            out.append((it["full"], std))
        elif k == "phrase":
            out.append((it["de"], std))
        elif k == "swiss":
            out.append((it["ch"], ch))
    seen, uniq = set(), []
    for t in out:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def prefetch_job():
    """Descarga en segundo plano todos los audios (respeta el límite del plan gratuito: ~20 por minuto)."""
    global LAST_PING
    texts = all_audio_texts()
    PREFETCH.update(running=True, done=0, total=len(texts), errors=0, last_error=None)
    rate = float(STORE.settings().get("rate") or 0.95)
    for text, voice in texts:
        LAST_PING = time.time()  # que la app no se apague mientras descarga
        h = hashlib.sha1(f"{voice}|{rate:.2f}|{text}".encode()).hexdigest()
        if not os.path.exists(os.path.join(STORE.dir, "audio", h + ".mp3")):
            audio, err = azure_tts(text, voice, rate)
            if err:
                PREFETCH["errors"] += 1
                PREFETCH["last_error"] = err
                if err in ("sin-clave", "azure-401", "azure-403") or PREFETCH["errors"] > 20:
                    break
                time.sleep(10)
            time.sleep(3.2)
        PREFETCH["done"] += 1
    PREFETCH["running"] = False


# ====================================================================== copias de seguridad
def make_backup():
    buf = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmp:
        dbcopy = os.path.join(tmp, "deutsch.db")
        STORE.backup_to(dbcopy)
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(dbcopy, "deutsch.db")
            z.writestr("LEEME.txt", "Copia de seguridad de Deutsch Lernen.\n"
                                    "Para restaurarla: Ajustes → Restaurar copia.\n"
                                    f"Fecha: {time.strftime('%Y-%m-%d %H:%M')}\n")
            adir = os.path.join(STORE.dir, "audio")
            for fn in os.listdir(adir):
                z.write(os.path.join(adir, fn), f"audio/{fn}")
    return buf.getvalue()


def restore_backup(raw):
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
        if "deutsch.db" not in z.namelist():
            return {"ok": False, "error": "El archivo no es una copia de Deutsch Lernen."}
        with tempfile.TemporaryDirectory() as tmp:
            z.extract("deutsch.db", tmp)
            test = sqlite3.connect(os.path.join(tmp, "deutsch.db"))
            test.execute("SELECT COUNT(*) FROM cards").fetchone()
            test.close()
            safety = os.path.join(STORE.dir, f"antes-de-restaurar-{time.strftime('%Y%m%d-%H%M%S')}.db")
            STORE.backup_to(safety)
            with STORE.lock:
                STORE.db.close()
                shutil.copy(os.path.join(tmp, "deutsch.db"), STORE.path)
                STORE._open()
            for n in z.namelist():
                if n.startswith("audio/") and n.endswith(".mp3"):
                    target = os.path.join(STORE.dir, "audio", os.path.basename(n))
                    with open(target, "wb") as f:
                        f.write(z.read(n))
        return {"ok": True}
    except (zipfile.BadZipFile, sqlite3.DatabaseError):
        return {"ok": False, "error": "No se ha podido leer la copia: el archivo está dañado o no es válido."}


# ====================================================================== HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "DeutschLernen"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8", headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _json(self):
        raw = self._body()
        return json.loads(raw.decode("utf-8")) if raw else {}

    def do_GET(self):
        global LAST_PING
        url = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(url.query))
        p = url.path
        try:
            if p == "/api/ping":
                LAST_PING = time.time()
                return self._send(200, {"ok": True, "version": VERSION})
            if p == "/api/home":
                return self._send(200, home())
            if p == "/api/session":
                return self._send(200, build_daily())
            if p == "/api/practice":
                return self._send(200, build_practice(q.get("kind", ""), q.get("ref", "")))
            if p == "/api/progress":
                return self._send(200, progress())
            if p == "/api/library":
                return self._send(200, library())
            if p == "/api/placement":
                return self._send(200, placement_questions())
            if p == "/api/settings":
                s = STORE.settings()
                s["azure_key_set"] = bool(s.get("azure_key"))
                s["azure_key"] = ""
                s["azure_voices"] = AZURE_VOICES
                s["data_dir"] = STORE.dir
                s["version"] = VERSION
                return self._send(200, s)
            if p == "/api/notes":
                return self._send(200, STORE.query("SELECT * FROM notes ORDER BY updated DESC"))
            if p == "/api/tts":
                audio, err = azure_tts(q.get("text", ""), q.get("voice"), q.get("rate"))
                if audio:
                    return self._send(200, audio, "audio/mpeg")
                return self._send(404, {"error": err})
            if p == "/api/audio/status":
                return self._send(200, PREFETCH)
            if p == "/api/backup":
                data = make_backup()
                name = f"deutsch-lernen-copia-{time.strftime('%Y-%m-%d')}.zip"
                return self._send(200, data, "application/zip",
                                  {"Content-Disposition": f'attachment; filename="{name}"'})
            if p == "/api/export":
                data = json.dumps(STORE.export(), ensure_ascii=False, indent=1)
                name = f"deutsch-lernen-datos-{time.strftime('%Y-%m-%d')}.json"
                return self._send(200, data, "application/json; charset=utf-8",
                                  {"Content-Disposition": f'attachment; filename="{name}"'})
            return self._static(p)
        except Exception as e:  # no tumbar el servidor por un error puntual
            import traceback
            traceback.print_exc()
            return self._send(500, {"error": str(e)})

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        p = url.path
        try:
            if p == "/api/restore":
                return self._send(200, restore_backup(self._body()))
            data = self._json()
            if p == "/api/answer":
                return self._send(200, answer(data))
            if p == "/api/introduce":
                return self._send(200, introduce(data.get("item")))
            if p == "/api/finish":
                return self._send(200, finish(data))
            if p == "/api/placement":
                return self._send(200, placement_result(data))
            if p == "/api/audio/prefetch":
                if not PREFETCH["running"]:
                    threading.Thread(target=prefetch_job, daemon=True).start()
                    time.sleep(0.2)
                return self._send(200, PREFETCH)
            if p == "/api/settings":
                if "azure_key" in data and data["azure_key"] == "":
                    data.pop("azure_key")
                if data.pop("azure_key_clear", False):
                    data["azure_key"] = ""
                STORE.set_settings(data)
                return self._send(200, {"ok": True})
            if p == "/api/notes":
                now = time.time()
                if data.get("delete") and data.get("id"):
                    STORE.execute("DELETE FROM notes WHERE id = ?", (data["id"],))
                elif data.get("id"):
                    STORE.execute("UPDATE notes SET title=?, body=?, color=?, updated=? WHERE id=?",
                                  (data.get("title", ""), data.get("body", ""), data.get("color", "amber"), now, data["id"]))
                else:
                    nid = STORE.execute("INSERT INTO notes (title, body, color, created, updated) VALUES (?,?,?,?,?)",
                                        (data.get("title", "Sin título"), data.get("body", ""), data.get("color", "amber"), now, now))
                    return self._send(200, {"ok": True, "id": nid})
                return self._send(200, {"ok": True})
            return self._send(404, {"error": "no encontrado"})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._send(500, {"error": str(e)})

    def _static(self, p):
        if p in ("", "/"):
            p = "/index.html"
        full = os.path.normpath(os.path.join(STATIC, p.lstrip("/")))
        if not full.startswith(STATIC) or not os.path.isfile(full):
            full = os.path.join(STATIC, "index.html")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype)


def watchdog(idle):
    while True:
        time.sleep(30)
        if time.time() - LAST_PING > idle:
            os._exit(0)


def main():
    global STORE
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--auto-exit", action="store_true", help="cerrar tras 20 min sin la app abierta")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    mimetypes.add_type("font/ttf", ".ttf")
    mimetypes.add_type("application/javascript", ".js")
    STORE = Store()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    if args.auto_exit:
        threading.Thread(target=watchdog, args=(20 * 60,), daemon=True).start()
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Deutsch Lernen funcionando en {url}  (datos en {STORE.dir})", flush=True)
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
