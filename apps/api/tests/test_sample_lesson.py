import datetime as dt
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
import pytest
from tutor import classroom, lesson, quiz, say
from tutor.pack import load_pack
from tutor.sample import install
from tutor.lesson import is_sample
from tutor.server import App, make_handler
from tutor.store import Store

PACKS = Path(__file__).resolve().parents[3] / "packs"
SAMPLE = (PACKS / "security-plus-sy0-701" / "sample-lesson.md").read_text()
DAY = dt.date(2026, 10, 6)


def pack():
    return load_pack(PACKS, "security-plus-sy0-701")


def test_sample_is_a_valid_lesson():
    p = pack()
    assert is_sample(SAMPLE)
    assert quiz.problem(SAMPLE, {o["id"] for o in p.objectives}) is None   # 6 valid items on real objectives
    title, stages = lesson.outline(SAMPLE, p.config["stages"])
    assert title.startswith("Sample lesson") and len(stages) == 7
    assert sum(s["minutes"] for s in stages) == 60
    scripts = lesson.scripts(SAMPLE)
    questions = [i for items in scripts.values() for i in items if i["question"]]
    assert len(scripts) >= 9 and len(questions) >= 5 and all(q["expect"] for q in questions)


def test_sample_diagram_is_safe_svg():
    svg = SAMPLE.split("```svg", 1)[1].split("```", 1)[0]
    assert "<svg" in svg and "viewBox" in svg
    for bad in ("<script", "foreignObject", "href=", "onload"):
        assert bad not in svg


def test_install_marks_lesson_as_sample_and_protects_real_lessons(tmp_path):
    p, store = pack(), Store(tmp_path / "t.db")
    out = install(p, store, tmp_path, DAY)
    assert out.read_text() == SAMPLE
    assert store.lesson(DAY)["status"] == "sample" and store.lesson(DAY)["objectives"] == ["4.8", "2.4"]
    install(p, store, tmp_path, DAY)                       # re-installing a sample is fine
    out.write_text("<!-- objectives: 1.1 -->\n# Real lesson\n")
    with pytest.raises(FileExistsError):
        install(p, store, tmp_path, DAY)                   # a real lesson is never overwritten by accident
    install(p, store, tmp_path, DAY, force=True)
    assert is_sample(out.read_text())


def test_sample_answers_and_summary_are_not_recorded(tmp_path):
    p, store = pack(), Store(tmp_path / "t.db")
    install(p, store, tmp_path, DAY)
    app = App(p, store, tmp_path, token="t")
    r = app.answer(DAY, 0, "Eradication")
    assert r and r["correct"] is False                     # still marked, with feedback
    assert store.evidence("4.8") == []                     # but not stored as progress
    assert app.finish(DAY, "practice run")
    assert store.lesson(DAY)["summary"] == ""              # never feeds the next real lesson
    assert store.last_summary(DAY + dt.timedelta(days=1)) == ""


def test_real_lesson_answers_still_recorded(tmp_path):
    p, store = pack(), Store(tmp_path / "t.db")
    (tmp_path / "lessons").mkdir()
    (tmp_path / "lessons" / f"{DAY}.md").write_text(SAMPLE.replace("<!-- sample", "<!-- note"))
    store.save_lesson(DAY, ["4.8", "2.4"])
    App(p, store, tmp_path, token="t").answer(DAY, 0, "Containment")
    assert store.evidence("4.8")


def test_sample_lesson_is_served_without_secrets(tmp_path):
    p, store = pack(), Store(tmp_path / "t.db")
    install(p, store, tmp_path, DAY)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(App(p, store, tmp_path, token="t")))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{srv.server_port}/api/lesson?date={DAY}",
                                     headers={"Authorization": "Bearer t"})
        body = urllib.request.urlopen(req).read().decode()
    finally:
        srv.shutdown()
    data = json.loads(body)
    assert len(data["quiz"]) == 6 and "expect:" not in body
    assert "isolate the laptop" not in body                # an expect line's wording stays on the server
    assert all("answer" not in q for q in data["quiz"])


def test_lessons_off_archives_real_lessons_and_keeps_samples(tmp_path):
    from tutor.sample import lessons_off
    from tutor.settings import Settings
    p, store = pack(), Store(tmp_path / "t.db")
    (tmp_path / "lessons").mkdir()
    real = tmp_path / "lessons" / "2026-10-05.md"
    real.write_text("<!-- objectives: 1.1 -->\n# Real\n")
    store.save_lesson(dt.date(2026, 10, 5), ["1.1"])
    store.add_evidence("1.1", dt.date(2026, 10, 5), "recall", True)
    install(p, store, tmp_path, DAY, build_audio=False)
    r = lessons_off(store, tmp_path, dt.datetime(2026, 10, 6, 17, 0))
    assert r["archived"] == ["2026-10-05"] and not real.exists()
    assert (tmp_path / "lessons-archive" / "20261006-170000" / "2026-10-05.md").exists()   # moved, not deleted
    assert store.lesson(dt.date(2026, 10, 5)) is None and store.lesson(DAY)["status"] == "sample"
    assert store.evidence("1.1")                                           # progress kept unless asked
    assert Settings(tmp_path).get()["lesson_generator"] is False
    lessons_off(store, tmp_path, dt.datetime(2026, 10, 6, 17, 1), reset_progress=True)
    assert store.evidence("1.1") == []


def test_generator_off_scheduler_writes_nothing(tmp_path):
    from tutor.notify import Console
    from tutor.scheduler import tick
    from tutor.settings import Settings
    Settings(tmp_path).update({"lesson_generator": False})
    calls = []
    p, store = load_pack(PACKS, "security-plus-sy0-701", tmp_path), Store(tmp_path / "t.db")
    for h in (8, 21):
        tick(p, store, Settings(tmp_path), Console(), tmp_path, dt.datetime(2026, 10, 5, h, 0),
             write=lambda *a: calls.append(a))
    assert calls == []


def test_generator_off_every_date_opens_the_sample(tmp_path):
    from tutor.settings import Settings
    Settings(tmp_path).update({"lesson_generator": False})
    p, store = pack(), Store(tmp_path / "t.db")
    app = App(p, store, tmp_path, token="t")
    l = app.lesson(dt.date(2026, 10, 8))
    assert l and l["title"].startswith("Sample lesson")
    assert store.lesson(dt.date(2026, 10, 8))["status"] == "sample"
    Settings(tmp_path).update({"lesson_generator": True})
    assert App(p, store, tmp_path, token="t").lesson(dt.date(2026, 10, 9)) is None   # on: no auto sample
