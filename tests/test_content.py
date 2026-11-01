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
# conversaciones y audios
T = CONTENT.talk
ids = [sc["id"] for sc in T["scenarios"]]
if len(ids) != len(set(ids)):
    errors.append("talk.json: ids de escena repetidos")
for sc in T["scenarios"]:
    for k in ("id", "icon", "title", "partner", "g", "voice", "role", "setting", "tasks", "opener"):
        if not sc.get(k):
            errors.append(f"talk.json: a la escena {sc.get('id')} le falta «{k}»")
    if sc.get("level") not in ("", "A1", "A2", "B1", "B2") or sc.get("g") not in ("f", "m") or sc.get("voice") not in ("de", "ch"):
        errors.append(f"talk.json: nivel, género o voz raros en {sc['id']}")
    if len(sc.get("opener", [])) != 2 or not all(sc["opener"]):
        errors.append(f"talk.json: la escena {sc['id']} necesita frase inicial y traducción")
for li in T["listenings"]:
    if set(li["speakers"]) != {"A", "B"}:
        errors.append(f"talk.json: el audio {li['id']} necesita los hablantes A y B")
    for row in li["lines"]:
        if len(row) != 3 or row[0] not in ("A", "B") or not row[1] or not row[2]:
            errors.append(f"talk.json: línea incompleta en {li['id']}: {row}")
    for q, opts, ans in li["questions"]:
        if not (0 <= ans < len(opts)) or len(set(opts)) != len(opts):
            errors.append(f"talk.json: pregunta mal formada en {li['id']}: {q}")
print(f"{len(T['scenarios'])} escenas de conversación, {len(T['listenings'])} audios")
print(f"{len(CONTENT.items)} elementos, {count} ejercicios generados")
if errors:
    print("ERRORES:"); [print(" -", e) for e in errors[:40]]
    sys.exit(1)
print("OK")
