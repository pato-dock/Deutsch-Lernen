"""Repetición espaciada FSRS-5 (implementación compacta, sin dependencias).

Una tarjeta guarda: stability (s, en días), difficulty (d, 1–10), state, due, last,
reps y lapses. Las notas: 1 = Again (fallo), 2 = Hard, 3 = Good, 4 = Easy.
"""
import math
import time

W = [0.40255, 1.18385, 3.173, 15.69105, 7.1949, 0.5345, 1.4604, 0.0046,
     1.54575, 0.1192, 1.01925, 1.9395, 0.11, 0.29605, 2.2698, 0.2315,
     2.9898, 0.51655, 0.6621]
DECAY = -0.5
FACTOR = 19 / 81
RETENTION = 0.9
DAY = 86400

NEW, LEARNING, REVIEW, RELEARNING = 0, 1, 2, 3


def new_card():
    return {"s": 0.0, "d": 0.0, "state": NEW, "due": 0, "last": 0, "reps": 0, "lapses": 0}


def retrievability(elapsed_days, s):
    if s <= 0:
        return 0.0
    return (1 + FACTOR * elapsed_days / s) ** DECAY


def _clamp_d(d):
    return min(10.0, max(1.0, d))


def _init_d(g):
    return _clamp_d(W[4] - math.exp(W[5] * (g - 1)) + 1)


def _next_d(d, g):
    delta = -W[6] * (g - 3)
    d2 = d + delta * (10 - d) / 9
    return _clamp_d(W[7] * _init_d(4) + (1 - W[7]) * d2)


def _recall_s(d, s, r, g):
    hard = W[15] if g == 2 else 1.0
    easy = W[16] if g == 4 else 1.0
    return s * (math.exp(W[8]) * (11 - d) * s ** (-W[9]) *
                (math.exp(W[10] * (1 - r)) - 1) * hard * easy + 1)


def _forget_s(d, s, r):
    nxt = W[11] * d ** (-W[12]) * ((s + 1) ** W[13] - 1) * math.exp(W[14] * (1 - r))
    return min(nxt, s)


def interval_days(s):
    ivl = s / FACTOR * (RETENTION ** (1 / DECAY) - 1)
    return int(min(365, max(1, round(ivl))))


def review(card, grade, now=None):
    """Devuelve una tarjeta nueva tras responder con la nota `grade` (1–4)."""
    now = time.time() if now is None else now
    c = dict(card)
    if c["state"] == NEW:
        c["s"] = W[grade - 1]
        c["d"] = _init_d(grade)
        c["state"] = REVIEW if grade >= 3 else LEARNING
    else:
        elapsed = max(0.0, (now - c["last"]) / DAY)
        r = retrievability(elapsed, c["s"])
        if elapsed < 1:
            c["s"] = max(0.1, c["s"] * math.exp(W[17] * (grade - 3 + W[18])))
            if grade == 1:
                c["state"] = RELEARNING if c["state"] == REVIEW else c["state"]
            elif c["state"] in (LEARNING, RELEARNING) and grade >= 3:
                c["state"] = REVIEW
        elif grade == 1:
            c["s"] = max(0.1, _forget_s(c["d"], c["s"], r))
            c["lapses"] += 1
            c["state"] = RELEARNING
        else:
            c["s"] = _recall_s(c["d"], c["s"], r, grade)
            c["state"] = REVIEW
        c["d"] = _next_d(c["d"], grade)
    c["reps"] += 1
    c["last"] = now
    if grade == 1:
        c["due"] = now + 10 * 60          # vuelve en la misma sesión o mañana
    else:
        c["due"] = now + interval_days(c["s"]) * DAY
    return c
