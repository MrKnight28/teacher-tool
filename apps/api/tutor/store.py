"""SQLite progress store: evidence per objective, lessons, homework.

Three kinds of record, kept apart:
  transcript  - what happened in a lesson, word for word (debugging, review). Not progress. Cleared with chat.
  evidence    - what the student demonstrated, per objective, with the verdict and any misconception. Drives mastery.
  outcomes    - a lesson's end-of-lesson summary, built from its evidence. The next lesson's plan reads this.
"""
from __future__ import annotations
import datetime as dt
import json
import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence (
  id INTEGER PRIMARY KEY, objective_id TEXT NOT NULL, day TEXT NOT NULL,
  kind TEXT NOT NULL, correct INTEGER NOT NULL, note TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS lessons (
  day TEXT PRIMARY KEY, objectives TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'planned',
  summary TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS chat (id INTEGER PRIMARY KEY, day TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS transcript (
  id INTEGER PRIMARY KEY, day TEXT NOT NULL, ts TEXT NOT NULL, role TEXT NOT NULL,
  step TEXT NOT NULL DEFAULT '', objective TEXT NOT NULL DEFAULT '', text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outcomes (day TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sent (day TEXT NOT NULL, kind TEXT NOT NULL, PRIMARY KEY(day, kind));
CREATE TABLE IF NOT EXISTS usage (id INTEGER PRIMARY KEY, day TEXT NOT NULL, task TEXT, model TEXT, cost_usd REAL NOT NULL);
CREATE TABLE IF NOT EXISTS attempts (day TEXT NOT NULL, kind TEXT NOT NULL, n INTEGER NOT NULL, last TEXT NOT NULL, PRIMARY KEY(day, kind));
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, ts TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ev_obj ON evidence(objective_id, day);
CREATE INDEX IF NOT EXISTS tr_day ON transcript(day, id);
"""
# Columns added after the first release. Old databases get them on open; existing rows keep their values.
EVIDENCE_COLUMNS = {"source": "TEXT DEFAULT ''", "verdict": "TEXT DEFAULT ''",
                    "misconception": "TEXT DEFAULT ''", "event_key": "TEXT"}
KINDS = {"recognise", "recall", "apply_familiar", "apply_new", "delayed_recall"}
TRANSCRIPT_ROLES = ("student", "tutor")


class Store:
    def __init__(self, path: Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False, timeout=30)   # api and scheduler share this file: wait for a lock
        self.lock = threading.RLock()  # the web server is threaded
        self.db.executescript(SCHEMA)
        have = {r[1] for r in self.db.execute("PRAGMA table_info(evidence)")}
        for name, ddl in EVIDENCE_COLUMNS.items():
            if name not in have:
                self.db.execute(f"ALTER TABLE evidence ADD COLUMN {name} {ddl}")
        # One row per event: a repeated request or event with the same key is ignored (NULL keys are not compared).
        self.db.execute("CREATE UNIQUE INDEX IF NOT EXISTS ev_key ON evidence(event_key)")
        self.db.commit()

    def add_evidence(self, objective_id: str, day: dt.date, kind: str, correct: bool, note: str = "",
                     source: str = "", verdict: str = "", misconception: str = "", event_key: str | None = None) -> bool:
        """Records one piece of evidence. Returns False if an event with the same event_key was already recorded."""
        if kind not in KINDS:
            raise ValueError(f"unknown evidence kind {kind}")
        with self.lock:
            cur = self.db.execute(
                "INSERT OR IGNORE INTO evidence(objective_id,day,kind,correct,note,source,verdict,misconception,event_key) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (objective_id, day.isoformat(), kind, int(correct), note, source, verdict, misconception, event_key))
            self.db.commit()
            return cur.rowcount == 1

    def evidence(self, objective_id: str) -> list[tuple]:
        """(day, kind, correct) per objective, in order. Mastery is worked out from these."""
        return self.db.execute("SELECT day,kind,correct FROM evidence WHERE objective_id=? ORDER BY day,id",
                               (objective_id,)).fetchall()

    def evidence_on(self, day: dt.date) -> list[dict]:
        """Every evidence row recorded on one lesson day, with its source, verdict and misconception."""
        rows = self.db.execute(
            "SELECT objective_id,kind,correct,note,source,verdict,misconception FROM evidence WHERE day=? ORDER BY id",
            (day.isoformat(),)).fetchall()
        return [{"objective": o, "kind": k, "correct": bool(c), "note": n, "source": s, "verdict": v, "misconception": m}
                for o, k, c, n, s, v, m in rows]

    def add_transcript(self, day: dt.date, when: dt.datetime, role: str, text: str, step: str = "", objective: str = ""):
        """A raw line of the lesson: the student's words or the tutor's. Kept for review; never read as progress."""
        if role not in TRANSCRIPT_ROLES:
            raise ValueError(role)
        with self.lock:
            self.db.execute("INSERT INTO transcript(day,ts,role,step,objective,text) VALUES(?,?,?,?,?,?)",
                            (day.isoformat(), when.isoformat(timespec="seconds"), role, step, objective, text[:1000]))
            self.db.commit()

    def transcript(self, day: dt.date) -> list[dict]:
        rows = self.db.execute("SELECT ts,role,step,objective,text FROM transcript WHERE day=? ORDER BY id",
                               (day.isoformat(),)).fetchall()
        return [{"ts": t, "role": r, "step": s, "objective": o, "text": x} for t, r, s, o, x in rows]

    def save_outcome(self, day: dt.date, outcome: dict):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO outcomes(day,body) VALUES(?,?)",
                            (day.isoformat(), json.dumps(outcome, ensure_ascii=False)))
            self.db.commit()

    def outcome(self, day: dt.date) -> dict | None:
        r = self.db.execute("SELECT body FROM outcomes WHERE day=?", (day.isoformat(),)).fetchone()
        return json.loads(r[0]) if r else None

    def last_outcome(self, before: dt.date) -> dict | None:
        """The most recent lesson outcome before this day: what the next lesson should pick up."""
        r = self.db.execute("SELECT body FROM outcomes WHERE day<? ORDER BY day DESC LIMIT 1", (before.isoformat(),)).fetchone()
        return json.loads(r[0]) if r else None

    def save_lesson(self, day: dt.date, objectives: list[str], status="planned", summary=""):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO lessons(day,objectives,status,summary) VALUES(?,?,?,?)",
                            (day.isoformat(), ",".join(objectives), status, summary))
            self.db.commit()

    def lesson(self, day: dt.date):
        r = self.db.execute("SELECT objectives,status,summary FROM lessons WHERE day=?", (day.isoformat(),)).fetchone()
        return None if r is None else {"objectives": r[0].split(",") if r[0] else [], "status": r[1], "summary": r[2]}

    def missed_objectives(self, before: dt.date) -> list[str]:
        rows = self.db.execute("SELECT objectives FROM lessons WHERE status='missed' AND day<?",
                               (before.isoformat(),)).fetchall()
        out: list[str] = []
        for (o,) in rows:
            out += [x for x in o.split(",") if x and x not in out]
        return out

    def last_summary(self, before: dt.date) -> str:
        r = self.db.execute("SELECT summary FROM lessons WHERE day<? AND status='done' ORDER BY day DESC LIMIT 1",
                            (before.isoformat(),)).fetchone()
        return r[0] if r else ""

    def add_chat(self, day: dt.date, role: str, content: str):
        if role not in ("user", "assistant"):
            raise ValueError(role)
        with self.lock:
            self.db.execute("INSERT INTO chat(day,role,content) VALUES(?,?,?)", (day.isoformat(), role, content[:4000]))
            self.db.commit()

    def chat_history(self, day: dt.date, limit: int = 12) -> list[dict]:
        rows = self.db.execute("SELECT role,content FROM chat WHERE day=? ORDER BY id DESC LIMIT ?",
                               (day.isoformat(), limit)).fetchall()
        return [{"role": r, "content": c} for r, c in reversed(rows)]

    def was_sent(self, day: dt.date, kind: str) -> bool:
        return self.db.execute("SELECT 1 FROM sent WHERE day=? AND kind=?", (day.isoformat(), kind)).fetchone() is not None

    def mark_sent(self, day: dt.date, kind: str):
        with self.lock:
            self.db.execute("INSERT OR IGNORE INTO sent(day,kind) VALUES(?,?)", (day.isoformat(), kind))
            self.db.commit()

    def sent_count(self, day: dt.date) -> int:
        """Messages actually delivered today (internal markers excluded)."""
        return self.db.execute("SELECT COUNT(*) FROM sent WHERE day=? AND kind NOT LIKE '%_logged'",
                               (day.isoformat(),)).fetchone()[0]

    def add_usage(self, day: dt.date, task: str, model: str, cost_usd: float):
        with self.lock:
            self.db.execute("INSERT INTO usage(day,task,model,cost_usd) VALUES(?,?,?,?)", (day.isoformat(), task, model, cost_usd))
            self.db.commit()

    def month_cost_usd(self, month: str) -> float:
        return self.db.execute("SELECT COALESCE(SUM(cost_usd),0) FROM usage WHERE substr(day,1,7)=?", (month,)).fetchone()[0]

    def attempt(self, day: dt.date, kind: str, when: dt.datetime):
        with self.lock:
            self.db.execute("INSERT INTO attempts(day,kind,n,last) VALUES(?,?,1,?) ON CONFLICT(day,kind) "
                            "DO UPDATE SET n=n+1, last=excluded.last", (day.isoformat(), kind, when.isoformat()))
            self.db.commit()

    def attempts(self, day: dt.date, kind: str):
        r = self.db.execute("SELECT n,last FROM attempts WHERE day=? AND kind=?", (day.isoformat(), kind)).fetchone()
        return (0, None) if r is None else (r[0], dt.datetime.fromisoformat(r[1]))

    def get_kv(self, key: str) -> str:
        """Small app state (a lesson moved by WhatsApp, the pending WhatsApp quiz question). '' when unset."""
        r = self.db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return r[0] if r else ""

    def set_kv(self, key: str, value: str):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO kv(key,value) VALUES(?,?)", (key, value))
            self.db.commit()

    def log_event(self, when: dt.datetime, kind: str, detail: str):
        with self.lock:
            self.db.execute("INSERT INTO events(ts,kind,detail) VALUES(?,?,?)", (when.isoformat(timespec="seconds"), kind, detail))
            self.db.commit()

    def events(self, limit: int = 10) -> list[dict]:
        rows = self.db.execute("SELECT ts,kind,detail FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{"ts": t, "kind": k, "detail": d} for t, k, d in rows]

    def reset_attempts(self, day: dt.date, kind: str):
        with self.lock:
            self.db.execute("DELETE FROM attempts WHERE day=? AND kind=?", (day.isoformat(), kind))
            self.db.commit()

    TRANSCRIPT_DAYS = 90  # raw words are kept for review for this long; evidence and outcomes are not pruned

    def prune_transcript(self, today: dt.date) -> int:
        """Delete raw transcript older than TRANSCRIPT_DAYS. Returns how many lines were removed."""
        cutoff = (today - dt.timedelta(days=self.TRANSCRIPT_DAYS)).isoformat()
        with self.lock:
            cur = self.db.execute("DELETE FROM transcript WHERE day < ?", (cutoff,))
            self.db.commit()
            return cur.rowcount

    def forget_lessons(self, days: list[str], reset_progress: bool = False):
        """Drop lesson rows (and their write attempts, transcript and outcome) for the given ISO dates.
        Optionally clear all progress, chat and transcripts."""
        with self.lock:
            for d in days:
                self.db.execute("DELETE FROM lessons WHERE day=?", (d,))
                self.db.execute("DELETE FROM attempts WHERE day=?", (d,))
                self.db.execute("DELETE FROM transcript WHERE day=?", (d,))
                self.db.execute("DELETE FROM outcomes WHERE day=?", (d,))
            if reset_progress:
                self.db.execute("DELETE FROM evidence")
                self.db.execute("DELETE FROM chat")
                self.db.execute("DELETE FROM transcript")
                self.db.execute("DELETE FROM outcomes")
            self.db.commit()
