"""Compañera de conversación con IA. Solo biblioteca estándar.

Usa la API «chat completions» compatible con OpenAI, que ofrecen gratis:
  · Google Gemini (plan gratuito con una cuenta de Google, sin tarjeta)
  · Groq (plan gratuito)
  · Ollama (gratis, se ejecuta en el propio Mac y funciona sin internet)
"""
import json
import os
import re
import urllib.error
import urllib.request

PROVIDERS = {
    "gemini": {"label": "Google Gemini", "note": "gratis con tu cuenta de Google",
               "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
               "model": "gemini-flash-latest", "key": True},
    "groq": {"label": "Groq", "note": "gratis, muy rápido",
             "url": "https://api.groq.com/openai/v1/chat/completions",
             "model": "llama-3.3-70b-versatile", "key": True},
    "ollama": {"label": "Ollama", "note": "en tu Mac, sin internet",
               "url": "http://127.0.0.1:11434/v1/chat/completions",
               "model": "gemma3:4b", "key": False},
    "custom": {"label": "Otro servicio", "note": "compatible con OpenAI",
               "url": "", "model": "", "key": False},
}

LEVEL_GUIDE = {
    "A1": "Use only very simple sentences (max. about 8 words), present tense, the most common everyday words. No subordinate clauses.",
    "A2": "Use simple sentences, present tense and Perfekt, common everyday vocabulary, occasionally 'weil' or 'dass'.",
    "B1": "Use natural everyday German with subordinate clauses, Perfekt and Präteritum of common verbs and some common idioms.",
    "B2": "Use fluent, natural German with varied structures, idiomatic expressions and Konjunktiv II where it is natural.",
}


def config(s):
    """Configuración efectiva de la IA a partir de los ajustes guardados."""
    p = s.get("ai_provider") or "gemini"
    pr = PROVIDERS.get(p, PROVIDERS["gemini"])
    url = (s.get("ai_url") or "").strip() if p == "custom" else pr["url"]
    url = os.environ.get("DL_AI_URL") or url
    model = (s.get("ai_model") or "").strip() or pr["model"]
    key = ((s.get("ai_keys") or {}).get(p) or "").strip()
    ready = bool(url and model and (key or not pr["key"]))
    return {"provider": p, "label": pr["label"], "url": url, "model": model, "key": key,
            "needs_key": pr["key"], "ready": ready}


def _error(code, cfg, detail=""):
    p, m = cfg["provider"], cfg["model"]
    if code in (401, 403):
        return "La clave de la IA no es válida. Revísala en Ajustes."
    if code == 404:
        if p == "ollama":
            return f"Ollama no tiene el modelo «{m}». Descárgalo en Terminal con: ollama pull {m}"
        return f"No encuentro el modelo «{m}». Revisa su nombre en Ajustes o déjalo vacío."
    if code == 429:
        return "Has llegado al límite gratuito de este momento. Espera un minuto y vuelve a probar."
    if code == 400:
        return f"La IA no ha aceptado la petición. Revisa el modelo en Ajustes. ({detail[:120]})"
    if code >= 500:
        return "El servicio de IA no responde ahora mismo. Prueba de nuevo en un rato."
    return f"Error de la IA ({code})."


def chat(cfg, messages, temperature=0.7, timeout=90):
    """Devuelve (texto, error)."""
    if not cfg["ready"]:
        return None, "sin-ia"
    body = {"model": cfg["model"], "messages": messages, "temperature": temperature}
    headers = {"Content-Type": "application/json", "User-Agent": "DeutschLernen"}
    if cfg["key"]:
        headers["Authorization"] = "Bearer " + cfg["key"]
    req = urllib.request.Request(cfg["url"], json.dumps(body).encode("utf-8"), headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read()[:400].decode("utf-8", "replace")
        return None, _error(e.code, cfg, detail)
    except (urllib.error.URLError, OSError) as e:
        if cfg["provider"] == "ollama":
            return None, "Ollama no está abierto. Abre la app Ollama y vuelve a probar."
        return None, f"No hay conexión con la IA ({e.__class__.__name__}). Comprueba tu internet."
    try:
        msg = data["choices"][0]["message"]
        text = msg.get("content") or ""
        if isinstance(text, list):  # algunos servicios devuelven partes
            text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
        return text.strip(), None
    except (KeyError, IndexError, TypeError):
        return None, "La IA ha devuelto una respuesta vacía. Vuelve a probar."


def parse_json(text):
    """Extrae el primer objeto JSON de la respuesta (tolera ```json … ``` y texto alrededor)."""
    if not text:
        return None
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        return None
    try:
        return json.loads(t[a:b + 1])
    except ValueError:
        return None


# ====================================================================== conversación
def talk_system(sc, level, name, corrections=True):
    tasks = "\n".join(f"{i}. {t}" for i, t in enumerate(sc["tasks"]))
    learner = name or "the learner"
    corr = ('"correction": null, or, ONLY if her last message has a real grammar or vocabulary mistake, '
            '{"wrong": "the wrong part as she said it", "right": "the corrected, natural German sentence", '
            '"why": "a very short, kind explanation in Spanish (max. 20 words)"}'
            if corrections else '"correction": null')
    return f"""You are {sc['partner']}. Role: {sc['role']}
Scene: {sc['setting']}
You are having a SPOKEN conversation in German with {learner}, a Spanish speaker who lives near Basel and is learning German (CEFR level {level}).

How to speak:
- Stay in character and sound like a real person, warm and natural, not like a teacher or a robot.
- Keep each turn short: 1 to 3 sentences, as in real speech. Usually end with a question or a prompt that keeps the conversation going.
- {LEVEL_GUIDE.get(level, LEVEL_GUIDE['A2'])}
- Speak standard German (Hochdeutsch); Swiss words like Grüezi, Velo or Gipfeli are fine where natural.
- Her messages come from speech recognition: ignore punctuation, capitalisation and small transcription glitches.
- If she writes in Spanish or seems lost, help her gently in very simple German. Never answer in Spanish in "reply".
- Do not use emojis or stage directions; your text will be read aloud.

Her tasks in this scene (numbered from 0):
{tasks}
Steer the scene so she can complete them, but let her do them herself.

Answer ONLY with a JSON object, no other text:
{{"reply": "your next line in German",
 "es": "Spanish translation of reply",
 {corr},
 "done": [numbers of ALL tasks she has completed so far in the whole conversation],
 "hints": ["two short, different things she could say next, in German, at her level"],
 "end": false}}
Set "end" to true only when the conversation has come to a natural close (for example after saying goodbye)."""


def talk_messages(sc, level, name, history, corrections=True):
    msgs = [{"role": "system", "content": talk_system(sc, level, name, corrections)}]
    for m in history[-24:]:
        role = "assistant" if m.get("role") == "assistant" else "user"
        msgs.append({"role": role, "content": str(m.get("text", ""))[:600]})
    return msgs


def clean_turn(data, raw, n_tasks):
    """Normaliza la respuesta de la IA para que la interfaz no falle nunca."""
    if not isinstance(data, dict) or not str(data.get("reply", "")).strip():
        reply = re.sub(r"\s+", " ", re.sub(r"[{}\"]", "", raw or "")).strip()
        return {"reply": reply[:500] or "Entschuldigung, wie bitte?", "es": "", "correction": None,
                "done": [], "hints": [], "end": False}
    corr = data.get("correction")
    if not (isinstance(corr, dict) and corr.get("right")):
        corr = None
    else:
        corr = {k: str(corr.get(k) or "")[:300] for k in ("wrong", "right", "why")}
    done = []
    for d in data.get("done") or []:
        try:
            d = int(d)
        except (TypeError, ValueError):
            continue
        if 0 <= d < n_tasks and d not in done:
            done.append(d)
    hints = [str(h)[:160] for h in (data.get("hints") or []) if str(h).strip()][:3]
    return {"reply": str(data["reply"]).strip()[:800], "es": str(data.get("es") or "")[:800],
            "correction": corr, "done": sorted(done), "hints": hints, "end": bool(data.get("end"))}


# ====================================================================== audios de escucha
def listen_messages(topic, level):
    prompt = f"""Write a short, natural German dialogue for listening practice.
Learner: a Spanish speaker living near Basel, CEFR level {level}. Topic: {topic}.
- 8 to 10 lines, two speakers: A is a woman, B is a man. Each line 1 or 2 sentences.
- {LEVEL_GUIDE.get(level, LEVEL_GUIDE['A2'])}
- It must sound like real people talking (natural reactions, no textbook phrases). Swiss context is welcome.
- Grammatically perfect standard German. Write numbers and times so they can be read aloud.
- Three multiple-choice comprehension questions in Spanish with three options each; exactly one is correct and it must be clearly answerable from the audio.
- Four useful words or expressions from the dialogue with their Spanish meaning (nouns with article).
Answer ONLY with JSON in this exact shape:
{{"title": "German title", "title_es": "Spanish title",
 "speakers": {{"A": {{"name": "first name", "g": "f"}}, "B": {{"name": "first name", "g": "m"}}}},
 "lines": [["A", "German line", "Spanish translation"], ["B", "...", "..."]],
 "questions": [["question in Spanish", ["option 1", "option 2", "option 3"], index_of_correct_option]],
 "vocab": [["German", "Spanish"]]}}"""
    return [{"role": "system", "content": "You are an expert author of German listening materials. You always answer with valid JSON."},
            {"role": "user", "content": prompt}]


def clean_listening(d):
    """Valida un audio generado. Devuelve el audio limpio o None."""
    try:
        sp = d["speakers"]
        speakers = {k: {"name": str(sp[k].get("name") or k)[:30], "g": "m" if sp[k].get("g") == "m" else "f"}
                    for k in ("A", "B")}
        lines = [[("B" if str(r[0]).strip().upper() == "B" else "A"), str(r[1]).strip(), str(r[2]).strip()]
                 for r in d["lines"] if len(r) >= 3 and str(r[1]).strip()]
        qs = []
        for q in d["questions"]:
            opts = [str(o) for o in q[1]][:4]
            ans = int(q[2])
            if len(opts) >= 2 and 0 <= ans < len(opts):
                qs.append([str(q[0]), opts, ans])
        vocab = [[str(v[0]), str(v[1])] for v in d.get("vocab", []) if len(v) >= 2][:6]
        if len(lines) < 4 or not qs:
            return None
        return {"title": str(d.get("title") or "Hörtext")[:80], "title_es": str(d.get("title_es") or "")[:80],
                "speakers": speakers, "lines": lines[:14], "questions": qs[:4], "vocab": vocab}
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):
        return None
