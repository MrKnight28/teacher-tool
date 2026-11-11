import datetime as dt, json, threading, urllib.request, urllib.error
from http.server import ThreadingHTTPServer
from pathlib import Path
import pytest
from tutor import classroom as K
from tutor import lesson as L
from tutor.pack import load_pack
from tutor.server import App, make_handler
from tutor.store import Store

PACKS = Path(__file__).resolve().parents[3] / "packs"
LESSON = """<!-- objectives: 4.8 -->
# Security+ SY0-701 Lesson: Incident response
**Date:** 2026-10-06

## Stage 1: Retrieval (5 min)
Ask one at a time.

## Stage 3: Teaching (12 min)
### Part A: Containment
Isolate the host.

## Stage 4: Guided practice
Work one scenario.

## Quiz
```quiz
[{"objective":"4.8","type":"multiple_choice","q":"First IR phase?","options":["Preparation","Eradication"],"answer":"Preparation","why":"Prepare first."}]
```
"""
STAGE_MINUTES = {"retrieval": 5, "guided_practice": 10, "teaching": 15}


def test_outline_reads_title_stages_and_minutes():
    title, stages = L.outline(LESSON, STAGE_MINUTES)
    assert title == "Security+ SY0-701 Lesson: Incident response"
    assert stages == [
        {"name": "Stage 1: Retrieval", "minutes": 5},
        {"name": "Stage 3: Teaching", "minutes": 12},      # tag in the heading wins over config
        {"name": "Stage 4: Guided practice", "minutes": 10},  # no tag: taken from pack config
    ]


def test_outline_excludes_quiz_and_defaults_unknown_stage():
    _, stages = L.outline("## Quiz\n## Mystery\n", STAGE_MINUTES)
    assert [s["name"] for s in stages] == ["Mystery"]
    assert stages[0]["minutes"] == L.DEFAULT_MINUTES


def test_validate_notes_round_trip_and_ids():
    clean = K.validate_notes([{"id": "n-abc123", "title": "Today", "body": "x"},
                              {"id": "../evil", "title": "", "body": ""},
                              {"id": "n-abc123", "title": "dup", "body": ""}])
    assert clean[0]["id"] == "n-abc123"
    assert clean[1]["id"].startswith("n-") and clean[1]["id"] != "../evil"
    assert clean[2]["id"] != "n-abc123"  # duplicate ids get a fresh one


@pytest.mark.parametrize("items, msg", [
    ("nope", "list"),
    ([{}] * 201, "too many"),
    ([{"title": "t" * 121}], "title too long"),
    ([{"body": "x" * 50_001}], "too large"),
    ([{"title": 3}], "must be text"),
    (["x"], "object"),
])
def test_validate_notes_rejects(items, msg):
    with pytest.raises(ValueError, match=msg):
        K.validate_notes(items)


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
    yield f"http://127.0.0.1:{srv.server_port}", tmp_path, day
    srv.shutdown()


def call(url, body=None, tok="secret", method=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data, {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
                                 method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def test_lesson_returns_outline_exam_date_and_domains(server):
    base, _, day = server
    code, data = call(f"{base}/api/lesson?date={day}")
    assert code == 200
    assert data["title"].startswith("Security+ SY0-701 Lesson")
    assert [s["minutes"] for s in data["stages"]] == [5, 12, 10]
    assert data["stage_minutes"]["teaching"] == 15
    assert data["exam_date"] == "2027-06-30"
    assert {d["id"] for d in data["domains"]} == {1, 2, 3, 4, 5}
    assert "answer" not in json.dumps(data)  # answer keys never reach the browser


def test_notes_require_token(server):
    base, _, _ = server
    assert call(f"{base}/api/notes", tok="wrong")[0] == 401
    assert call(f"{base}/api/notes", {"notes": []}, tok="wrong")[0] == 401


def test_notes_empty_then_round_trip(server):
    base, tmp, _ = server
    assert call(f"{base}/api/notes") == (200, {"notes": []})
    notes = [{"id": "n-today1", "title": "Today", "body": "☐ item\n- line"}]
    code, saved = call(f"{base}/api/notes", {"notes": notes})
    assert code == 200 and saved["notes"] == notes
    assert call(f"{base}/api/notes")[1]["notes"] == notes
    assert (tmp / "notes.json").exists() and not (tmp / "notes.json.tmp").exists()


def test_notes_validation_errors_are_400(server):
    base, _, _ = server
    assert call(f"{base}/api/notes", {"notes": [{"title": "t" * 121}]})[0] == 400
    assert call(f"{base}/api/notes", {"notes": [{"body": "x" * 50_001}]})[0] == 400
    assert call(f"{base}/api/notes", {"notes": [{}] * 201})[0] == 400
    assert call(f"{base}/api/notes", {"notes": "text"})[0] == 400
    assert call(f"{base}/api/notes", {"notes": []})[0] == 200  # an empty notebook is valid


def test_notes_body_must_be_an_object(server):
    base, _, _ = server
    code, data = call(f"{base}/api/notes", [1, 2])
    assert code == 400 and data["error"] == "bad request"


def test_page_allows_diagram_images_only_from_self_and_data(server):
    base, _, _ = server
    req = urllib.request.Request(f"{base}/", headers={"Authorization": "Bearer secret"})
    with urllib.request.urlopen(req) as r:
        csp = r.headers["Content-Security-Policy"]
        html = r.read().decode()
    assert "img-src 'self' data:" in csp
    assert "DEMO" not in html and "Demo mode" not in html
