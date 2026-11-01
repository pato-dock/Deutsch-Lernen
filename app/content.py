"""Carga el contenido incluido y genera ejercicios a partir de él.

Todo el contenido está escrito y revisado de antemano, así que los ejercicios
son siempre correctos: se generan combinando datos verificados, sin IA.
"""
import json
import os
import random
import re
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(HERE, "content")
LEVELS = ["A1", "A2", "B1", "B2"]
TENSES = {
    "prs": "Präsens (presente)",
    "perf": "Perfekt",
    "prt": "Präteritum",
    "k2": "Konjunktiv II",
}
AUX = {
    "haben": ["habe", "hast", "hat", "haben", "habt", "haben"],
    "sein": ["bin", "bist", "ist", "sind", "seid", "sind"],
}
WUERDE = ["würde", "würdest", "würde", "würden", "würdet", "würden"]
SKILLS = {
    "vocab": "Vocabulario",
    "gram": "Gramática",
    "listen": "Escucha",
    "read": "Lectura",
    "write": "Escritura",
    "speak": "Pronunciación",
}


def _load(name):
    with open(os.path.join(CONTENT_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def slug(text):
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


class Content:
    def __init__(self):
        self.vocab = _load("vocab.json")
        self.verbs_raw = _load("verbs.json")
        self.grammar = _load("grammar.json")
        self.phrases = _load("phrases.json")
        self.swiss = _load("swiss.json")
        self.plan = _load("plan.json")
        self.grammar_tr = _load("grammar_tr.json")
        self.talk = _load("talk.json")
        self.items = {}
        self.themes = {}
        self.sheets = {s["id"]: s for s in self.grammar["sheets"]}
        self._build()

    # ------------------------------------------------------------------ catálogo
    def _build(self):
        for th in self.vocab["themes"]:
            ids = []
            for row in th["items"]:
                row = row + [""] * (9 - len(row))
                de, art, pl, es, ex, exs, emoji, ch, note = row[:9]
                iid = f"v:{th['id']}:{slug(de)}"
                self.items[iid] = {
                    "id": iid, "kind": "vocab", "theme": th["id"], "level": th["level"],
                    "de": de, "art": art, "pl": pl, "es": es, "ex": ex, "exs": exs,
                    "emoji": emoji, "ch": ch, "note": note, "noun": art in ("der", "die", "das", "pl"),
                }
                ids.append(iid)
            self.themes[th["id"]] = {k: th[k] for k in ("id", "title", "level", "icon")}
            self.themes[th["id"]]["items"] = ids
        for v in self.verbs_raw["verbs"]:
            iid = f"verb:{slug(v['inf'])}"
            self.items[iid] = dict(v, id=iid, kind="verb")
        for i, e in enumerate(self.grammar["exercises"]):
            topic, level, q, opts, ans, expl = e
            iid = f"g:{topic}:{i}"
            full, full_es = self.grammar_tr[i]
            self.items[iid] = {"id": iid, "kind": "gram", "topic": topic, "level": level,
                               "q": q, "o": opts, "a": ans, "x": expl, "full": full, "full_es": full_es}
        for g in self.swiss["groups"]:
            for i, row in enumerate(g["items"]):
                row = row + [""] * (5 - len(row))
                iid = f"ch:{g['id']}:{i}"
                self.items[iid] = {"id": iid, "kind": "swiss", "group": g["id"], "level": "A1",
                                   "ch": row[0], "std": row[1], "es": row[2], "type": row[3], "note": row[4]}
        for g in self.phrases["groups"]:
            for i, row in enumerate(g["items"]):
                row = row + [""] * (3 - len(row))
                iid = f"p:{g['id']}:{i}"
                self.items[iid] = {"id": iid, "kind": "phrase", "group": g["id"], "level": g["level"],
                                   "de": row[0], "es": row[1], "note": row[2]}

    # ------------------------------------------------------------------ ruta
    def unit_items(self, unit):
        ids = []
        for t in unit.get("vocab", []):
            ids += self.themes[t]["items"]
        for gid in unit.get("grammar", []):
            ids += [i for i, it in self.items.items() if it["kind"] == "gram" and it["topic"] == gid]
        for pg in unit.get("phrases", []):
            ids += [i for i, it in self.items.items() if it["kind"] == "phrase" and it["group"] == pg]
        return ids

    def level_items(self, level):
        lv = next(l for l in self.plan["levels"] if l["id"] == level)
        ids = []
        for u in lv["units"]:
            ids += self.unit_items(u)
        ids += [i for i, it in self.items.items() if it["kind"] == "verb" and it["level"] == level]
        return ids

    def ordered_new_pool(self):
        """Todos los elementos en el orden de la ruta (A1 → B2)."""
        order = []
        for lv in self.plan["levels"]:
            for u in lv["units"]:
                order += self.unit_items(u)
            order += [i for i, it in self.items.items() if it["kind"] == "verb" and it["level"] == lv["id"]]
        seen, out = set(), []
        for i in order:
            if i not in seen:
                seen.add(i)
                out.append(i)
        return out

    # ------------------------------------------------------------------ presentación
    @staticmethod
    def display(it):
        if it["kind"] == "vocab":
            if it["art"] in ("der", "die", "das"):
                return f"{it['art']} {it['de']}"
            if it["art"] == "pl":
                return f"die {it['de']}"
            return it["de"]
        if it["kind"] == "verb":
            return it["inf"]
        if it["kind"] == "phrase":
            return it["de"]
        if it["kind"] == "swiss":
            return it["ch"]
        return it.get("q", "")

    def card(self, it):
        """Información para la tarjeta de presentación / feedback."""
        k = it["kind"]
        if k == "vocab":
            return {"kind": k, "de": it["de"], "art": it["art"], "pl": it["pl"], "es": it["es"],
                    "ex": it["ex"], "exs": it["exs"], "emoji": it["emoji"], "ch": it["ch"],
                    "note": it["note"], "display": self.display(it), "theme": self.themes[it["theme"]]["title"]}
        if k == "verb":
            return {"kind": k, "de": it["inf"], "es": it["es"], "ex": it["ex"], "exs": it["exs"],
                    "note": it.get("note", ""), "prep": it.get("prep", ""), "display": it["inf"],
                    "prs": it["prs"], "part": it["part"], "aux": it["aux"], "tags": it["tags"]}
        if k == "swiss":
            return {"kind": k, "de": it["ch"], "std": it["std"], "es": it["es"], "type": it["type"],
                    "note": it["note"], "display": it["ch"]}
        if k == "phrase":
            return {"kind": k, "de": it["de"], "es": it["es"], "note": it["note"], "display": it["de"]}
        return {"kind": k}

    # ------------------------------------------------------------------ utilidades
    def _distractors(self, it, field_fn, n=3, same_group=True):
        correct = field_fn(it)
        pool = [x for x in self.items.values() if x["kind"] == it["kind"] and x["id"] != it["id"]]
        if it["kind"] == "vocab":
            pool = [x for x in pool if x["noun"] == it["noun"]]
            group = [x for x in pool if x["theme"] == it["theme"]] if same_group else []
        elif it["kind"] == "swiss":
            group = [x for x in pool if x["group"] == it["group"]]
        elif it["kind"] == "phrase":
            group = [x for x in pool if x["group"] == it["group"]]
        else:
            group = [x for x in pool if x.get("level") == it.get("level")]
        random.shuffle(group)
        random.shuffle(pool)
        out, seen = [], {correct.lower()}
        for x in group + pool:
            v = field_fn(x)
            if v and v.lower() not in seen:
                out.append(v)
                seen.add(v.lower())
            if len(out) >= n:
                break
        return out

    @staticmethod
    def _mc(correct, distractors):
        opts = [correct] + list(distractors)
        random.shuffle(opts)
        return opts, opts.index(correct)

    @staticmethod
    def _umlaut(w):
        if "au" in w:
            i = w.rfind("au")
            return w[:i] + "äu" + w[i + 2:]
        best = -1
        for v in "aouAOU":
            best = max(best, w.rfind(v))
        if best < 0:
            return w
        m = {"a": "ä", "o": "ö", "u": "ü", "A": "Ä", "O": "Ö", "U": "Ü"}
        return w[:best] + m[w[best]] + w[best + 1:]

    def _plural_distractors(self, it):
        w, correct = it["de"], it["pl"]
        u = self._umlaut(w)
        if w.endswith("e"):
            cands = [w + "n", w + "s", w, u + "n", w[:-1] + "en" if w[:-1] else w]
        elif w[-2:] in ("er", "el", "en") or w.endswith("chen"):
            cands = [w, w + "n", w + "s", u, w + "e"]
        else:
            cands = [w + "e", w + "en", w + "er", w + "s", u + "e", u + "er", w]
        out = []
        for c in cands:
            if c.lower() != correct.lower() and c not in out:
                out.append(c)
        random.shuffle(out)
        return [f"die {c}" for c in out[:3]]

    @staticmethod
    def tokens(sentence):
        return sentence.split()

    # ------------------------------------------------------------------ ejercicios
    def exercise_types(self, it, reps=0):
        """Tipos posibles para un elemento según su clase y lo bien que se conoce."""
        k = it["kind"]
        if k == "vocab":
            easy = ["meaning", "reverse"]
            if it["noun"] and it["art"] != "pl":
                easy.append("article")
            hard = ["listen", "type"]
            if it["noun"] and it["art"] != "pl" and it["pl"] not in ("—", "", it["de"]):
                hard.append("plural")
            if self._cloze_ok(it):
                hard.append("cloze")
            if len(self.tokens(it["ex"])) <= 9:
                hard.append("order")
            if it["level"] != "A1":
                hard.append("dictation")
            return easy if reps < 1 else (easy + hard if reps < 3 else hard + ["article"] * (it["noun"] and it["art"] != "pl"))
        if k == "verb":
            return ["verb_meaning", "conj"] if reps < 1 else ["conj", "conj", "verb_type"]
        if k == "gram":
            return ["gram"]
        if k == "swiss":
            return ["swiss_std", "swiss_es"]
        if k == "phrase":
            t = ["phrase_meaning"]
            if len(self.tokens(it["de"])) <= 9 and "…" not in it["de"] and "/" not in it["de"]:
                t.append("order")
            return t
        return []

    def _cloze_ok(self, it):
        return bool(re.search(r"\b" + re.escape(it["de"]) + r"\b", it["ex"]))

    def sentence(self, it):
        """Frase completa con su traducción, para mostrarla siempre junto al ejercicio."""
        k = it["kind"]
        if k in ("vocab", "verb"):
            return {"de": it["ex"], "es": it["exs"]}
        if k == "gram":
            return {"de": it["full"], "es": it["full_es"]}
        if k == "phrase":
            return {"de": it["de"], "es": it["es"]}
        if k == "swiss":
            return {"de": it["ch"], "es": f"{it['es']} · estándar: {it['std']}", "swiss": True}
        return None

    def make(self, it, etype, user_level="A1"):
        ex = self._make(it, etype, user_level)
        ex["sentence"] = self.sentence(it)
        return ex

    def _make(self, it, etype, user_level="A1"):
        base = {"item": it["id"], "type": etype, "card": self.card(it), "level": it.get("level", "A1")}
        k = it["kind"]
        if etype == "intro":
            return dict(base, skill=None, audio=self.display(it) if k != "gram" else None)

        if etype == "article":
            ans = ["der", "die", "das"].index(it["art"])
            return dict(base, skill="vocab", prompt={"text": it["de"], "emoji": it["emoji"], "hint": it["es"]},
                        options=["der", "die", "das"], answer=ans, audio=self.display(it),
                        explain=it["note"] or "")
        if etype == "meaning":
            opts, ans = self._mc(it["es"], self._distractors(it, lambda x: x["es"]))
            return dict(base, skill="vocab", prompt={"text": self.display(it), "art": it["art"]},
                        options=opts, answer=ans, audio=self.display(it))
        if etype == "reverse":
            opts, ans = self._mc(self.display(it), self._distractors(it, self.display))
            return dict(base, skill="vocab", prompt={"text": it["es"], "emoji": it["emoji"]},
                        options=opts, answer=ans, audio=self.display(it), options_de=True)
        if etype == "listen":
            opts, ans = self._mc(self.display(it), self._distractors(it, self.display))
            return dict(base, skill="listen", prompt={"listen": True}, options=opts, answer=ans,
                        audio=self.display(it), options_de=True)
        if etype == "plural":
            opts, ans = self._mc(f"die {it['pl']}", self._plural_distractors(it))
            return dict(base, skill="vocab", prompt={"text": self.display(it), "art": it["art"]},
                        options=opts, answer=ans, audio=f"die {it['pl']}", options_de=True)
        if etype in ("type", "dictation"):
            target = self.display(it)
            return dict(base, skill="write" if etype == "type" else "listen",
                        prompt={"text": it["es"], "emoji": it["emoji"], "listen": etype == "dictation",
                                "needs_article": it["noun"]},
                        accept=self.accept_forms(target), answer_text=target, audio=target)
        if etype == "cloze":
            word = it["de"]
            sent = re.sub(r"\b" + re.escape(word) + r"\b", "___", it["ex"], count=1)
            same = lambda x: x["de"] if x.get("art") == it["art"] else ""
            dis = self._distractors(it, same)
            if len(dis) < 3:
                dis += [d for d in self._distractors(it, lambda x: x["de"]) if d not in dis][: 3 - len(dis)]
            opts, ans = self._mc(word, dis)
            return dict(base, skill="read", prompt={"text": sent, "hint": it["exs"]},
                        options=opts, answer=ans, audio=it["ex"], options_de=True)
        if etype == "order":
            sentence = it["ex"] if k == "vocab" else it["de"]
            toks = self.tokens(sentence)
            shuffled = toks[:]
            for _ in range(10):
                random.shuffle(shuffled)
                if shuffled != toks:
                    break
            return dict(base, skill="gram", prompt={"hint": it["exs"] if k == "vocab" else it["es"]},
                        tokens=shuffled, answer_tokens=toks, audio=sentence)

        if etype == "verb_meaning":
            opts, ans = self._mc(it["es"], self._distractors(it, lambda x: x["es"]))
            return dict(base, skill="vocab", prompt={"text": it["inf"]}, options=opts, answer=ans, audio=it["inf"])
        if etype == "verb_type":
            return dict(base, skill="write", prompt={"text": it["es"], "needs_article": False},
                        accept=self.accept_forms(it["inf"]), answer_text=it["inf"], audio=it["inf"])
        if etype == "conj":
            return self._conj(it, base, user_level)

        if etype == "gram":
            opts = list(it["o"])
            correct = opts[it["a"]]
            random.shuffle(opts)
            return dict(base, skill="gram", prompt={"text": it["q"], "topic": self.sheets[it["topic"]]["title"]},
                        options=opts, answer=opts.index(correct), explain=it["x"],
                        options_de=True, audio=it["full"] if "→" not in it["full"] else None, sheet=it["topic"])

        if etype == "swiss_std":
            opts, ans = self._mc(it["std"], self._distractors(it, lambda x: x["std"]))
            return dict(base, skill="listen", prompt={"text": it["ch"], "swiss": True, "kind": it["type"]},
                        options=opts, answer=ans, audio=it["ch"], swiss=True, options_de=True,
                        explain=it["note"])
        if etype == "swiss_es":
            opts, ans = self._mc(it["es"], self._distractors(it, lambda x: x["es"]))
            return dict(base, skill="listen", prompt={"text": it["ch"], "swiss": True, "kind": it["type"]},
                        options=opts, answer=ans, audio=it["ch"], swiss=True, explain=it["note"])
        if etype == "phrase_meaning":
            opts, ans = self._mc(it["es"], self._distractors(it, lambda x: x["es"]))
            return dict(base, skill="read", prompt={"text": it["de"]}, options=opts, answer=ans,
                        audio=it["de"], explain=it["note"])
        raise ValueError(etype)

    def _conj(self, it, base, user_level):
        lv = LEVELS.index(user_level) if user_level in LEVELS else 0
        tenses = ["prs"]
        if lv >= 1:
            tenses += ["perf", "perf"]
        if lv >= 2:
            tenses += ["prt", "k2"]
        tense = random.choice(tenses)
        forms = self.verb_forms(it)
        person = random.randrange(6)
        correct = forms[tense][person]
        pron = self.verbs_raw["pronouns"][person]
        distract = []
        for p in random.sample(range(6), 6):
            f = forms[tense][p]
            if f != correct and f not in distract:
                distract.append(f)
            if len(distract) >= 2:
                break
        for t in random.sample(list(forms), len(forms)):
            f = forms[t][person]
            if f != correct and f not in distract:
                distract.append(f)
                break
        while len(distract) < 3:
            f = forms["prs"][random.randrange(6)] + ("t" if len(distract) % 2 else "e")
            if f != correct and f not in distract:
                distract.append(f)
        opts, ans = self._mc(correct, distract[:3])
        return dict(base, skill="gram", prompt={"text": it["inf"], "pronoun": pron, "tense": TENSES[tense],
                                                "es": it["es"]},
                    options=opts, answer=ans, audio=f"{pron.split('/')[0]} {correct}", options_de=True,
                    explain=it.get("note", ""))

    def verb_forms(self, it):
        aux = AUX[it["aux"]]
        perf = [f"{aux[i]} {it['part']}" for i in range(6)]
        k2 = it["k2"] if it.get("k2") else [f"{WUERDE[i]} {it['inf'].replace('sich ', '')}" for i in range(6)]
        if it.get("k2") is None and it["inf"].startswith("sich "):
            refl = ["mich", "dich", "sich", "uns", "euch", "sich"]
            base = it["inf"].replace("sich ", "")
            k2 = [f"{WUERDE[i]} {refl[i]} {base}" for i in range(6)]
            perf = [f"{aux[i]} {refl[i]} {it['part']}" for i in range(6)]
        return {"prs": it["prs"], "perf": perf, "prt": it["prt"], "k2": k2}

    @staticmethod
    def normalize(s):
        s = s.strip().lower()
        s = s.replace("ß", "ss")
        s = re.sub(r"[.,!?¿¡;:«»\"“”„]", "", s)
        s = re.sub(r"\s+", " ", s)
        return s

    def accept_forms(self, target):
        n = self.normalize(target)
        alt = n.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
        return sorted({n, alt})


CONTENT = Content()
