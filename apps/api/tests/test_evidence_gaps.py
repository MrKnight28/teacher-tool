"""Gaps in the evidence work: a free-text exam answer with the marker down records nothing, and a database written
before the evidence columns existed opens with its rows intact."""
import datetime as dt
import json
import sqlite3
from pathlib import Path

from tutor.pack import load_pack
from tutor.server import App
from tutor.store import Store

PACKS = Path(__file__).resolve().parents[3] / "packs"
DAY = dt.date(2026, 10, 6)


class Broken:
    def complete(self, msgs, model, task):
        raise RuntimeError("marker down")

    def stream(self, msgs, model, task, timing=None):
        yield "ok"


def free_text_lesson(tmp_path):
    quiz = [{"objective": "4.8", "type": "free_text", "q": "What does a fuse do?", "answer": "breaks the circuit", "why": "x"}]
    (tmp_path / "lessons").mkdir(exist_ok=True)
    (tmp_path / "lessons" / f"{DAY}.md").write_text("<!-- objectives: 4.8 -->\n# L\n## S\n### T\nx\n```quiz\n" + json.dumps(quiz) + "\n```\n")


def test_free_text_exam_answer_with_the_marker_down_records_no_evidence(tmp_path):
    pack = load_pack(PACKS, "security-plus-sy0-701", tmp_path)
    store = Store(tmp_path / "t.db")
    store.save_lesson(DAY, ["4.8"])
    free_text_lesson(tmp_path)
    app = App(pack, store, tmp_path, token="secret")
    app.llm = Broken()
    r = app.answer(DAY, 0, "it breaks the circuit")
    assert r is not None                                   # the student still gets feedback
    assert store.evidence_on(DAY) == []                    # but nothing is claimed about the student
    assert any(e["kind"] == "evaluation_failed" for e in store.events(limit=10))
    assert len(store.transcript(DAY)) == 2                 # the words are kept


def test_a_database_from_before_the_evidence_columns_opens_and_keeps_its_rows(tmp_path):
    db = tmp_path / "old.db"
    con = sqlite3.connect(db)   # the schema as it was before source, verdict, misconception and event_key
    con.executescript("""
      CREATE TABLE evidence (id INTEGER PRIMARY KEY, objective_id TEXT NOT NULL, day TEXT NOT NULL,
        kind TEXT NOT NULL, correct INTEGER NOT NULL, note TEXT DEFAULT '');
      INSERT INTO evidence(objective_id,day,kind,correct,note) VALUES('4.8','2026-10-05','recall',1,'old answer');
      CREATE TABLE lessons (day TEXT PRIMARY KEY, objectives TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'planned', summary TEXT DEFAULT '');
    """)
    con.commit()
    con.close()
    store = Store(db)
    assert store.evidence("4.8") == [("2026-10-05", "recall", 1)]        # the old row, unchanged
    rows = store.evidence_on(dt.date(2026, 10, 5))
    assert rows[0]["note"] == "old answer" and rows[0]["source"] == "" and rows[0]["misconception"] == ""
    # new writes work on the upgraded table, and a repeated key is still ignored
    assert store.add_evidence("4.8", DAY, "recall", True, source="checkin", event_key="k1")
    assert not store.add_evidence("4.8", DAY, "recall", True, source="checkin", event_key="k1")
    assert len(store.evidence("4.8")) == 2


def test_opening_twice_does_not_fail(tmp_path):
    Store(tmp_path / "t.db")
    Store(tmp_path / "t.db")   # the migration is idempotent
