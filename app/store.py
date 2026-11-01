"""Base de datos local (SQLite): progreso, tarjetas, respuestas, sesiones, apuntes y ajustes."""
import json
import os
import sqlite3
import sys
import threading
import time

DEFAULTS = {
    "minutes": 30,
    "block_size": 8,
    "level": None,
    "placement_done": False,
    "voice_engine": "system",
    "system_voice": "",
    "rate": 0.95,
    "azure_key": "",
    "azure_region": "westeurope",
    "azure_voice": "de-DE-SeraphinaMultilingualNeural",
    "azure_voice_ch": "de-CH-LeniNeural",
    "theme": "light",
    "show_timer": True,
    "name": "",
    # juego
    "gems": 0,
    "freezes": 0,
    "frozen_days": [],
    "daily_goal": 50,
    "sound": True,
    "xp_boost_until": 0,
    # conversación con IA
    "ai_provider": "gemini",
    "ai_keys": {},
    "ai_model": "",
    "ai_url": "",
    "ai_corrections": True,
    "call_mode": True,
    "talk_voice_f": "de-DE-SeraphinaMultilingualNeural",
    "talk_voice_m": "de-DE-FlorianMultilingualNeural",
}

# ajustes que solo cambia el servidor (la interfaz no puede escribirlos directamente)
PRIVATE = {"gems", "freezes", "frozen_days", "xp_boost_until", "ai_keys"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
  item TEXT PRIMARY KEY, data TEXT NOT NULL, due REAL NOT NULL DEFAULT 0,
  introduced REAL NOT NULL, state INTEGER NOT NULL DEFAULT 0,
  reps INTEGER NOT NULL DEFAULT 0, lapses INTEGER NOT NULL DEFAULT 0, s REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS cards_due ON cards(due);
CREATE TABLE IF NOT EXISTS answers (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, day TEXT NOT NULL, item TEXT NOT NULL,
  type TEXT NOT NULL, skill TEXT, level TEXT, correct INTEGER NOT NULL, ms INTEGER, requeue INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS answers_day ON answers(day);
CREATE INDEX IF NOT EXISTS answers_item ON answers(item);
CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT NOT NULL, started REAL, finished REAL,
  seconds INTEGER, total INTEGER, correct INTEGER, xp INTEGER, kind TEXT
);
CREATE TABLE IF NOT EXISTS notes (
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, body TEXT NOT NULL,
  color TEXT DEFAULT 'amber', created REAL, updated REAL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, day TEXT NOT NULL, kind TEXT NOT NULL,
  ref TEXT, value INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS events_day ON events(day, kind);
CREATE TABLE IF NOT EXISTS achievements (id TEXT PRIMARY KEY, ts REAL NOT NULL);
CREATE TABLE IF NOT EXISTS conversations (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, day TEXT NOT NULL, scenario TEXT NOT NULL,
  turns INTEGER, ok_turns INTEGER, tasks_done INTEGER, tasks_total INTEGER, xp INTEGER, seconds INTEGER,
  transcript TEXT
);
CREATE TABLE IF NOT EXISTS listenings (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, level TEXT, topic TEXT, data TEXT NOT NULL,
  best INTEGER DEFAULT -1
);
"""


def data_dir():
    if os.environ.get("DEUTSCH_DATA"):
        d = os.environ["DEUTSCH_DATA"]
    elif sys.platform == "darwin":
        d = os.path.expanduser("~/Library/Application Support/DeutschLernen/datos")
    else:
        d = os.path.expanduser("~/.deutschlernen/datos")
    os.makedirs(os.path.join(d, "audio"), exist_ok=True)
    return d


class Store:
    def __init__(self, path=None):
        self.dir = data_dir()
        self.path = path or os.path.join(self.dir, "deutsch.db")
        self.lock = threading.RLock()
        self._open()

    def _open(self):
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()

    def reopen(self):
        with self.lock:
            self.db.close()
            self._open()

    # ---------------------------------------------------------------- ajustes
    def settings(self):
        with self.lock:
            out = dict(DEFAULTS)
            for r in self.db.execute("SELECT key, value FROM settings"):
                out[r["key"]] = json.loads(r["value"])
            return out

    def set_settings(self, values):
        with self.lock:
            for k, v in values.items():
                if k in DEFAULTS:
                    self.db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (k, json.dumps(v)))
            self.db.commit()

    def log_event(self, day, kind, ref="", value=0):
        with self.lock:
            self.db.execute("INSERT INTO events (ts, day, kind, ref, value) VALUES (?,?,?,?,?)",
                            (time.time(), day, kind, ref, int(value)))
            self.db.commit()

    # ---------------------------------------------------------------- tarjetas
    def card(self, item):
        with self.lock:
            r = self.db.execute("SELECT data FROM cards WHERE item = ?", (item,)).fetchone()
            return json.loads(r["data"]) if r else None

    def cards(self):
        with self.lock:
            return {r["item"]: dict(json.loads(r["data"]), introduced=r["introduced"])
                    for r in self.db.execute("SELECT item, data, introduced FROM cards")}

    def save_card(self, item, c):
        with self.lock:
            self.db.execute(
                """INSERT INTO cards (item, data, due, introduced, state, reps, lapses, s)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(item) DO UPDATE SET data=excluded.data, due=excluded.due,
                   state=excluded.state, reps=excluded.reps, lapses=excluded.lapses, s=excluded.s""",
                (item, json.dumps(c), c["due"], time.time(), c["state"], c["reps"], c["lapses"], c["s"]))
            self.db.commit()

    def due_items(self, until):
        with self.lock:
            return [r["item"] for r in self.db.execute(
                "SELECT item FROM cards WHERE due <= ? ORDER BY due", (until,))]

    # ---------------------------------------------------------------- respuestas
    def log_answer(self, day, item, etype, skill, level, correct, ms, requeue):
        with self.lock:
            self.db.execute(
                "INSERT INTO answers (ts, day, item, type, skill, level, correct, ms, requeue) VALUES (?,?,?,?,?,?,?,?,?)",
                (time.time(), day, item, etype, skill, level, int(bool(correct)), ms, int(bool(requeue))))
            self.db.commit()

    def query(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args)]

    def execute(self, sql, args=()):
        with self.lock:
            cur = self.db.execute(sql, args)
            self.db.commit()
            return cur.lastrowid

    # ---------------------------------------------------------------- exportar
    def export(self):
        with self.lock:
            out = {}
            for t in ("cards", "answers", "sessions", "notes", "settings", "events", "achievements",
                      "conversations", "listenings"):
                out[t] = [dict(r) for r in self.db.execute(f"SELECT * FROM {t}")]
            for s in out["settings"]:
                if s["key"] == "azure_key":
                    s["value"] = json.dumps("")
                if s["key"] == "ai_keys":
                    s["value"] = json.dumps({})
            return out

    def backup_to(self, dest):
        with self.lock:
            target = sqlite3.connect(dest)
            self.db.backup(target)
            target.close()
