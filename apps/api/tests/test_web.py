import datetime as dt, json, threading, urllib.request, urllib.error
from http.server import ThreadingHTTPServer
from pathlib import Path
import pytest
from tutor import quiz as Q
from tutor import lesson as L
from tutor.pack import load_pack
from tutor.server import App, make_handler
from tutor.store import Store

PACKS = Path(__file__).resolve().parents[3] / "packs"
LESSON = '''<!-- objectives: 4.8 -->
# Lesson
```quiz
[{"objective":"4.8","type":"multiple_choice","q":"First IR phase?","options":["Preparation","Eradication"],"answer":"Preparation","why":"Prepare first."},
 {"objective":"1.2","type":"acronym_recall","q":"What does CIA stand for?","answer":"Confidentiality, Integrity, Availability","why":""},
 {"objective":"4.8","type":"free_text","q":"Why isolate a host?","answer":"contain the incident spread","why":"Containment."}]
```
'''


def test_extract_and_mark():
    qs = L.quiz_items(LESSON)
    assert len(qs) == 3
    assert Q.mark(qs[0], "preparation")[0] and not Q.mark(qs[0], "Eradication")[0]
    assert Q.mark(qs[1], "confidentiality integrity availability")[0]
    assert not Q.mark(qs[1], "cats")[0]
    assert Q.mark(qs[2], "to contain the spread of the incident")[0]
    assert not Q.mark(qs[2], "no idea")[0]
    assert L.quiz_items("no quiz here") == []


@pytest.fixture
def server(tmp_path):
    day = dt.date(2026, 10, 6)
    (tmp_path / "lessons").mkdir()
    (tmp_path / "lessons" / f"{day}.md").write_text(LESSON)
    store = Store(tmp_path / "t.db")
    store.save_lesson(day, ["4.8"])
    app = App(load_pack(PACKS, "security-plus-sy0-701"), store, tmp_path, token="secret")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}", store, day
    srv.shutdown()


def call(url, body=None, tok="secret"):
    req = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None,
                                 {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def test_auth_required(server):
    base, _, day = server
    assert call(f"{base}/api/lesson?date={day}", tok="wrong")[0] == 401


def test_answer_key_not_sent_to_client(server):
    base, _, day = server
    code, data = call(f"{base}/api/lesson?date={day}")
    assert code == 200 and len(data["quiz"]) == 3
    assert all("answer" not in q and "why" not in q for q in data["quiz"])


def test_answer_records_evidence_and_finish_saves(server):
    base, store, day = server
    code, r = call(f"{base}/api/answer", {"date": str(day), "id": 0, "answer": "Eradication"})
    assert code == 200 and r["correct"] is False
    assert store.evidence("4.8")[0][2] == 0
    assert call(f"{base}/api/finish", {"date": str(day), "summary": "IR phases hard"})[1]["ok"]
    assert store.lesson(day)["status"] == "done"
    assert call(f"{base}/api/answer", {"date": str(day), "id": 99, "answer": "x"})[0] == 404


def test_refuses_public_bind_without_token(tmp_path):
    from tutor.server import serve
    app = App(load_pack(PACKS, "security-plus-sy0-701"), Store(tmp_path / "t.db"), tmp_path, token=None)
    with pytest.raises(SystemExit):
        serve(app, host="0.0.0.0")


def test_lesson_markdown_has_no_answer_key(server):
    base, _, day = server
    _, data = call(f"{base}/api/lesson?date={day}")
    assert "Preparation" not in data["markdown"] and "```" not in data["markdown"]
    assert "# Lesson" in data["markdown"]
