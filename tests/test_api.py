"""Arranca el servidor con datos temporales y simula una sesión completa por la API."""
import json, os, random, socket, subprocess, sys, tempfile, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeAI(BaseHTTPRequestHandler):
    """Imita una API de chat compatible con OpenAI para probar sin internet."""
    def log_message(self, *a): pass
    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        prompt = req["messages"][-1]["content"]
        if "listening practice" in prompt:
            out = {"title": "Beim Bäcker", "title_es": "En la panadería",
                   "speakers": {"A": {"name": "Anna", "g": "f"}, "B": {"name": "Tom", "g": "m"}},
                   "lines": [["A", "Guten Morgen!", "¡Buenos días!"], ["B", "Hallo! Ein Brot, bitte.", "¡Hola! Un pan, por favor."],
                             ["A", "Gern. Sonst noch etwas?", "Claro. ¿Algo más?"], ["B", "Nein, danke.", "No, gracias."]],
                   "questions": [["¿Qué compra?", ["Pan", "Leche", "Fruta"], 0]], "vocab": [["das Brot", "el pan"]]}
            content = "```json\n" + json.dumps(out) + "\n```"
        else:
            content = json.dumps({"reply": "Gern! Das macht 8 Franken.", "es": "¡Claro! Son 8 francos.",
                                  "correction": {"wrong": "Ich möchte zwei Brezel", "right": "Ich möchte zwei Brezeln.", "why": "Plural."},
                                  "done": [0, 1, 7], "hints": ["Hier, bitte."], "end": False})
        body = json.dumps({"choices": [{"message": {"role": "assistant", "content": content}}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)


ai_srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeAI)
threading.Thread(target=ai_srv.serve_forever, daemon=True).start()
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app")
s = socket.socket(); s.bind(("127.0.0.1", 0)); PORT = s.getsockname()[1]; s.close()
B = f"http://127.0.0.1:{PORT}"
tmp = tempfile.mkdtemp()
proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "server.py"), "--port", str(PORT), "--no-browser"],
                        env=dict(os.environ, DEUTSCH_DATA=tmp), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
def get(p): return json.load(urllib.request.urlopen(B + p))
def post(p, d): return json.load(urllib.request.urlopen(urllib.request.Request(B + p, json.dumps(d).encode(), {"Content-Type": "application/json"})))
try:
    for _ in range(50):
        try: get("/api/ping"); break
        except Exception: time.sleep(0.1)
    assert post("/api/placement", {"scores": {"A1": 6, "A2": 2}})["level"] == "A2"
    sess = get("/api/session")["exercises"]; assert sess, "sesión vacía"
    for e in sess:
        if e["type"] == "intro": post("/api/introduce", {"item": e["item"]})
        else: post("/api/answer", {"item": e["item"], "type": e["type"], "skill": e["skill"], "correct": random.random() < .8})
    r = post("/api/finish", {"total": len(sess), "correct": 10, "seconds": 600, "complete": True}); assert r["streak"] == 1
    p = get("/api/progress"); assert p["words"]["seen"] > 0
    assert get("/api/library")["themes"]
    for kind, ref in [("theme", "grafik"), ("sheet", "dativ"), ("verbs", ""), ("swiss", ""), ("phrases", "arbeit")]:
        assert get(f"/api/practice?kind={kind}&ref={ref}")["exercises"], kind
    # juego
    g = get("/api/game")
    assert g["xp_today"] > 0 and g["quests"] and g["rank"]["n"] >= 1
    assert any(a["id"] == "first" and a["got"] for a in g["achievements"]), "falta el logro de la primera sesión"
    assert g["gems"] >= 25, g["gems"]
    post("/api/settings", {"gems": 99999})  # la interfaz no puede cambiar las brezeln
    assert get("/api/game")["gems"] == g["gems"]
    b = post("/api/shop", {"item": "freeze"})
    assert b["ok"] == (g["gems"] >= 50), b
    # conversación con una IA simulada
    assert post("/api/talk/turn", {"scenario": "baeckerei", "messages": []})["error"] == "sin-ia"
    post("/api/settings", {"ai_provider": "custom", "ai_url": f"http://127.0.0.1:{ai_srv.server_address[1]}/v1/chat/completions", "ai_model": "test"})
    st = get("/api/settings"); assert st["ai_ready"] and "ai_keys" not in st
    assert post("/api/talk/test", {})["ok"]
    t = get("/api/talk"); assert t["ai_ready"] and len(t["scenarios"]) >= 10
    msgs = [{"role": "assistant", "text": "Grüezi! Was darf es sein?"}, {"role": "user", "text": "ich möchte zwei brezel"}]
    turn = post("/api/talk/turn", {"scenario": "baeckerei", "messages": msgs})
    assert turn["reply"] and turn["correction"]["right"] and turn["done"] == [0, 1], turn
    msgs += [{"role": "assistant", "text": turn["reply"]}]
    msgs[1]["correction"] = turn["correction"]
    fin = post("/api/talk/finish", {"scenario": "baeckerei", "messages": msgs, "done": turn["done"], "seconds": 90})
    assert fin["xp"] > 0 and fin["stars"] == 2 and fin["corrections"] == 1, fin
    assert any(a["id"] == "talk1" and a["got"] for a in fin["game"]["achievements"])
    # audios
    L = get("/api/listen"); assert len(L["items"]) >= 4
    item = get("/api/listen/item?id=b:cafe"); assert item["lines"] and item["speakers"]["A"]["voice"]
    new = post("/api/listen/new", {"topic": "Bäckerei", "level": "A1"}); assert new["id"].startswith("u:"), new
    lf = post("/api/listen/finish", {"id": new["id"], "correct": 1, "total": 1, "seconds": 60}); assert lf["xp"] == 30, lf
    assert get("/api/progress")["skills"]["speak"]["n"] == 1
    nid = post("/api/notes", {"title": "Test", "body": "Hallo"})["id"]; assert any(n["id"] == nid for n in get("/api/notes"))
    zipdata = urllib.request.urlopen(B + "/api/backup").read()
    assert json.load(urllib.request.urlopen(urllib.request.Request(B + "/api/restore", zipdata)))["ok"]
    print(f"OK · {len(sess)} ejercicios en la sesión simulada, conversación y audio con IA simulada")
finally:
    proc.terminate()
