"""Course lessons: reading a source pack, checking and writing plans, the committed lessons, and the daily queue."""
import datetime as dt
import json
import zipfile
from collections import Counter
from pathlib import Path

import pytest

from tutor import importer as I
from tutor import lesson_plan
from tutor.lesson import Lesson, student_text
from tutor.lesson_writer import write_lesson
from tutor.pack import load_pack
from tutor.settings import Settings
from tutor.store import Store

ROOT = Path(__file__).resolve().parents[3]
PACKS = ROOT / "packs"
PACK_ID = "security-plus-sy0-701"
LESSONS = PACKS / PACK_ID / "lessons"
STAGES = {"retrieval": 5, "intro": 5, "teaching": 15, "guided_practice": 10, "independent_practice": 15, "qa": 5, "review": 5}

SOURCE = """# Lesson 01: Security Controls

**Source:** notes
**CompTIA mapping:** Domain 1.1

## Lesson content

TECHNICAL MANAGERIAL Machine enforces it Document says it must happen

## Check-in questions

### Check-in 1
Which category is a policy?

Discuss before revealing the answer.

**Answer:** B
**Reason:** It is a document.

## Exam questions

### Question 1
A company policy requires annual training. Which control category is this?

A. Technical
B. Managerial
C. Operational
D. Physical

**Answer key:** B
**Explanation:** A policy is managerial.

## Source boundary

Derived from notes.
"""


def make_zip(path, manifest=None, files=None):
    manifest = manifest or {"format": I.FORMAT, "lessons": [
        {"lesson_number": 1, "title": "Security Controls", "mapping": "Domain 1.1", "file": "lessons/01-security-controls.md"}]}
    files = files if files is not None else {"lessons/01-security-controls.md": SOURCE}
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
        for name, text in files.items():
            z.writestr(name, text)
    return path


def good_plan(ids=("1.1",), title="Security Controls"):
    o = ids[0]
    section = lambda stage, t, said: {
        "stage": stage, "title": t, "objectives": list(ids),
        "content": [f"{t} point one", f"{t} point two"], "examples": [f"{t} worked case"],
        "say": [said], "checks": [{"question": f"Why does {t.lower()} matter?", "expect": "it protects data", "objective": o}]}
    return {"objectives": list(ids), "title": title,
            "sections": [section("intro", "Today", "We look at how safeguards are grouped."),
                         section("teaching", "Grouping", "A safeguard can be grouped by who enforces it.")],
            "retrieval": [{"question": "What is a safeguard?", "expect": "a protection", "objective": o}],
            "exam_questions": [{"objective": oid, "q": f"Question {n} about quarterly reviews of zebra {oid}?",
                                "options": [f"Alpha {n}", f"Bravo {n}", f"Charlie {n}", f"Delta {n}"],
                                "answer": f"Alpha {n}", "why": "Because."} for n, oid in enumerate(list(ids) * 3)]}


# ---------- reading a source pack ----------

def test_reads_a_zip_pack_with_keys_server_side(tmp_path):
    lessons = I.read_pack(make_zip(tmp_path / "p.zip"))
    assert len(lessons) == 1
    les = lessons[0]
    assert les["number"] == 1 and les["objectives"] == ["1.1"] and "TECHNICAL" in les["notes"]
    assert les["checkins"][0]["q"] == "Which category is a policy?"
    q = les["exam"][0]
    assert q["options"] == ["Technical", "Managerial", "Operational", "Physical"]
    assert q["key"] == "B" and q["answer"] == "Managerial" and q["why"] == "A policy is managerial."


def test_reads_a_pack_folder(tmp_path):
    (tmp_path / "lessons").mkdir()
    (tmp_path / "lessons" / "01-security-controls.md").write_text(SOURCE)
    (tmp_path / "manifest.json").write_text(json.dumps({"format": I.FORMAT, "lessons": [
        {"lesson_number": 1, "title": "Security Controls", "mapping": "Domains 3.1 / 3.2", "file": "lessons/01-security-controls.md"}]}))
    assert I.read_pack(tmp_path)[0]["objectives"] == ["3.1", "3.2"]


@pytest.mark.parametrize("name", ["../secret.md", "lessons/../../x.md", "/etc/passwd", "lessons/evil.sh"])
def test_only_lesson_files_the_manifest_names_are_read(tmp_path, name):
    z = make_zip(tmp_path / "p.zip", {"format": I.FORMAT, "lessons": [
        {"lesson_number": 1, "title": "x", "mapping": "Domain 1.1", "file": name}]})
    with pytest.raises(I.ImportProblem):
        I.read_pack(z)


def test_unknown_format_and_oversized_files_are_refused(tmp_path):
    with pytest.raises(I.ImportProblem, match="format"):
        I.read_pack(make_zip(tmp_path / "a.zip", {"format": "other", "lessons": []}))
    big = make_zip(tmp_path / "b.zip", files={"lessons/01-security-controls.md": "x" * (I.MAX_FILE + 1)})
    with pytest.raises(I.ImportProblem, match="too large"):
        I.read_pack(big)


def test_an_exam_question_without_a_key_is_refused():
    with pytest.raises(I.ImportProblem):
        I.parse_lesson(SOURCE.replace("**Answer key:** B", ""))


# ---------- plans -> lesson files ----------

def test_balance_spreads_answers_and_keeps_the_answer_text():
    plans = [good_plan(), good_plan()]
    I.balance(plans)
    qs = [q for p in plans for q in p["exam_questions"]]
    assert [q["options"].index(q["answer"]) for q in qs] == [0, 1, 2, 3, 0, 1]
    assert all(sorted(q["options"]) == sorted([f"Alpha {n}", f"Bravo {n}", f"Charlie {n}", f"Delta {n}"])
               for n, q in zip([0, 1, 2] * 2, qs))
    again = json.loads(json.dumps(plans))
    assert I.balance(again) == plans          # running it twice changes nothing


def test_build_writes_lessons_and_a_bad_plan_writes_nothing(tmp_path):
    plans, out = tmp_path / "plans", tmp_path / "out"
    plans.mkdir()
    (plans / "01-security-controls.plan.json").write_text(json.dumps(good_plan()))
    written = I.build(plans, out, STAGES, {"1.1"})
    md = written[0].read_text()
    assert md.startswith("<!-- objectives: 1.1 -->\n<!-- pack-lesson: 1 -->\n# Security Controls")
    assert Lesson.parse(md).quiz and (out / "01-security-controls.plan.json").exists()
    bad = good_plan()
    bad["sections"][0]["say"] = ["Example: this starts with a label."]
    (plans / "02-bad.plan.json").write_text(json.dumps(bad))
    for f in out.iterdir():
        f.unlink()
    with pytest.raises(I.ImportProblem, match="lesson 2"):
        I.build(plans, out, STAGES, {"1.1"})
    assert list(out.iterdir()) == []


def test_build_refuses_objectives_that_are_not_in_the_course(tmp_path):
    (tmp_path / "01-x.plan.json").write_text(json.dumps(good_plan(ids=("9.9",))))
    with pytest.raises(I.ImportProblem, match="objective"):
        I.build(tmp_path, tmp_path / "out", STAGES, {"1.1"})


# ---------- the committed course lessons ----------

def committed():
    return sorted(LESSONS.glob("[0-9][0-9]-*.plan.json"))


def test_the_course_has_17_lessons_in_order():
    assert [int(p.name[:2]) for p in committed()] == list(range(1, 18))


@pytest.mark.parametrize("plan_file", committed(), ids=lambda p: p.name[:2])
def test_each_course_lesson_is_valid_and_matches_its_plan(plan_file):
    pack = load_pack(PACKS, PACK_ID)
    plan = json.loads(plan_file.read_text())
    ids = plan["objectives"]
    assert set(ids) <= {o["id"] for o in pack.objectives}
    assert lesson_plan.problem(plan, ids, list(pack.config["stages"])) is None
    md = plan_file.with_name(plan_file.name.replace(".plan.json", ".md")).read_text()
    assert md == I.lesson_markdown(int(plan_file.name[:2]), plan, ids, pack.config["stages"]), "rerun import-pack"
    les = Lesson.parse(md)
    assert les.objectives == ids and les.scripts and len(les.quiz) >= 3
    for q in les.quiz:
        assert len(q["options"]) == 4 and q["answer"] in q["options"] and q["why"]
        assert q["answer"] not in student_text(md) or len(q["answer"]) < 12   # keys stay out of what the page shows
    assert {q["objective"] for q in les.quiz} == set(ids)


def test_course_answers_are_spread_evenly_over_a_to_d():
    positions = Counter("ABCD"[q["options"].index(q["answer"])]
                        for f in committed() for q in json.loads(f.read_text())["exam_questions"])
    assert max(positions.values()) - min(positions.values()) <= 1


# ---------- the queue ----------

@pytest.fixture
def course(tmp_path):
    data = tmp_path / "data"
    (data / "lessons").mkdir(parents=True)
    pack = load_pack(PACKS, PACK_ID, data)
    return pack, Store(data / "progress.db"), data


class NoModel:
    def __getattr__(self, name):
        raise AssertionError("a course lesson must not call the model")


def test_from_the_start_date_each_study_day_gets_the_next_course_lesson(course):
    pack, store, data = course
    mon, tue, wed = dt.date(2027, 1, 4), dt.date(2027, 1, 5), dt.date(2027, 1, 6)
    for day, n in ((mon, 1), (tue, 2), (wed, 3)):
        out = write_lesson(pack, store, data, day, llm=NoModel())
        assert f"<!-- pack-lesson: {n} -->" in out.read_text()
        assert store.lesson(day)["objectives"] == Lesson.parse(out.read_text()).objectives
    assert write_lesson(pack, store, data, dt.date(2027, 1, 9), llm=NoModel()) is None   # Saturday: rest day


def test_a_missed_course_lesson_comes_back(course):
    pack, store, data = course
    mon, tue = dt.date(2027, 1, 4), dt.date(2027, 1, 5)
    write_lesson(pack, store, data, mon, llm=NoModel())
    store.save_lesson(mon, store.lesson(mon)["objectives"], "missed")
    assert "<!-- pack-lesson: 1 -->" in write_lesson(pack, store, data, tue, llm=NoModel()).read_text()


def test_rewriting_the_same_day_gives_the_same_lesson(course):
    pack, store, data = course
    mon = dt.date(2027, 1, 4)
    write_lesson(pack, store, data, mon, llm=NoModel())
    assert "<!-- pack-lesson: 1 -->" in write_lesson(pack, store, data, mon, llm=NoModel()).read_text()


def test_before_the_start_or_when_turned_off_the_queue_gives_nothing(course):
    pack, store, data = course
    assert I.next_lesson(pack.root, data, store, dt.date(2027, 1, 1), "2027-01-04") is None
    assert I.next_lesson(pack.root, data, store, dt.date(2027, 1, 4), None) is None
    Settings(data).update({"pack_lessons_from": ""})
    assert write_lesson.__globals__["_course_lesson"](pack, store, data, dt.date(2027, 1, 4)) is None


def test_when_every_course_lesson_is_used_the_queue_hands_over(course):
    pack, store, data = course
    day = dt.date(2027, 1, 4)
    for n in range(1, 18):
        (data / "lessons" / f"{day}.md").write_text(f"<!-- objectives: 1.1 -->\n<!-- pack-lesson: {n} -->\n# x\n")
        store.save_lesson(day, ["1.1"], "done")
        day += dt.timedelta(days=1)
    assert I.next_lesson(pack.root, data, store, day, "2027-01-04") is None


def test_preview_shows_the_lessons_that_fit_before_the_exam(course):
    pack, store, data = course
    rows = I.preview(pack, data, store, dt.date(2026, 10, 7), "2027-01-04")
    assert rows[0][:2] == (dt.date(2027, 1, 4), 1)
    assert all(pack.is_study_day(d) for d, _, _ in rows) and rows[-1][0] < dt.date(2027, 6, 30)
    nums = [n for _, n, _ in rows]
    assert nums[:17] == list(range(1, 18)) and all(n is None for n in nums[17:])


def test_start_date_setting_is_validated(tmp_path):
    s = Settings(tmp_path)
    s.update({"pack_lessons_from": "2026-12-10"})
    assert s.get()["pack_lessons_from"] == "2026-12-10"
    with pytest.raises(ValueError):
        s.update({"pack_lessons_from": "next week"})
