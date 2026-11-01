"""Arranca el servidor con datos temporales y simula una sesión completa por la API."""
import json, os, random, socket, subprocess, sys, tempfile, time, urllib.request
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
    nid = post("/api/notes", {"title": "Test", "body": "Hallo"})["id"]; assert any(n["id"] == nid for n in get("/api/notes"))
    zipdata = urllib.request.urlopen(B + "/api/backup").read()
    assert json.load(urllib.request.urlopen(urllib.request.Request(B + "/api/restore", zipdata)))["ok"]
    print(f"OK · {len(sess)} ejercicios en la sesión simulada")
finally:
    proc.terminate()
