"""Valida el contenido y genera todos los tipos de ejercicio para cada elemento."""
import json, os, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")
sys.path.insert(0, ROOT)
from content import CONTENT  # noqa: E402

errors = []
g = CONTENT.grammar
if len(g["exercises"]) != len(CONTENT.grammar_tr):
    errors.append(f"grammar_tr.json tiene {len(CONTENT.grammar_tr)} entradas y grammar.json {len(g['exercises'])} ejercicios")
sheets = {s["id"] for s in g["sheets"]}
for e in g["exercises"]:
    if e[0] not in sheets:
        errors.append(f"ejercicio con ficha inexistente: {e[0]}")
for lv in CONTENT.plan["levels"]:
    for u in lv["units"]:
        for t in u.get("vocab", []):
            if t not in CONTENT.themes:
                errors.append(f"plan.json: tema inexistente {t}")
        for s in u.get("grammar", []):
            if s not in sheets:
                errors.append(f"plan.json: ficha inexistente {s}")
for it in CONTENT.items.values():
    if it["kind"] == "vocab" and it["art"] not in ("der", "die", "das", "pl", ""):
        errors.append(f"artículo raro en {it['id']}: {it['art']}")
count = 0
for iid, it in CONTENT.items.items():
    for reps in (0, 1, 3):
        for t in set(CONTENT.exercise_types(it, reps)):
            try:
                ex = CONTENT.make(it, t, "B2")
                count += 1
                if "options" in ex:
                    assert len(ex["options"]) >= 2, "menos de 2 opciones"
                    assert len({o.lower() for o in ex["options"]}) == len(ex["options"]), f"opciones repetidas {ex['options']}"
                    assert 0 <= ex["answer"] < len(ex["options"])
                assert ex.get("sentence") and ex["sentence"]["de"] and ex["sentence"]["es"], "falta frase traducida"
            except Exception as e:
                errors.append(f"{iid} / {t}: {e}")
print(f"{len(CONTENT.items)} elementos, {count} ejercicios generados")
if errors:
    print("ERRORES:"); [print(" -", e) for e in errors[:40]]
    sys.exit(1)
print("OK")
