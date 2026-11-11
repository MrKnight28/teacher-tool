"""Structured evidence: answers are transcribed, mapped to their objective and misconception, recorded once, summarised
at the end of the lesson, and read by the next lesson. The raw transcript and the evidence stay separate."""
import datetime as dt
import json
from pathlib import Path

from tutor import lesson_plan as LP
from tutor.pack import load_pack
from tutor.server import App
from tutor.store import Store

PACKS = Path(__file__).resolve().parents[3] / "packs"
DAY = dt.date(2026, 10, 6)
NEXT = dt.date(2026, 10, 7)
QUESTION = "Kyle, what does a fuse do?"
QUIZ = [{"objective": "4.8", "type": "multiple_choice", "q": "Which part cuts power on overload?",
         "options": ["Firewall", "Fuse", "Router", "Proxy"], "answer": "Fuse", "why": "A fuse does."}]


class FakeLLM:
    """Returns the scripted marker verdicts in order. 'RAISE' makes the marker fail."""

    def __init__(self, *verdicts):
        self.verdicts = list(verdicts)

    def complete(self, msgs, model, task):
        v = self.verdicts.pop(0) if self.verdicts else ""
        if v == "RAISE":
            raise RuntimeError("marker down")
        return v

    def stream(self, msgs, model, task, timing=None):
        yield "Good try."


def lesson_md():
    return ("<!-- objectives: 4.8,4.2 -->\n# Lesson\n## Stage one\n### Fuses\nA fuse is a safety part.\n"
            "```say\nKyle, a fuse protects a circuit.\n"
            f"? {QUESTION}\nexpect: a safety part that breaks the circuit\n```\n"
            "```quiz\n" + json.dumps(QUIZ) + "\n```\n")


def plan_json():
    return {
        "title": "Fuses", "retrieval": [],
        "sections": [{"stage": "teaching", "title": "Fuses", "objectives": ["4.2"], "content": ["A fuse breaks."],
                      "examples": ["A kettle fuse."], "say": ["A fuse protects the circuit."],
                      "checks": [{"question": QUESTION, "expect": "a safety part that breaks the circuit", "objective": "4.2"}],
                      "misconceptions": [{"belief": "A fuse resets itself.", "correction": "It must be replaced."}]}],
        "exam_questions": [], "homework": [{"objective": "4.2", "task": "Read the fuse notes."}],
    }


def setup(tmp_path, *verdicts, plan=True):
    pack = load_pack(PACKS, "security-plus-sy0-701", tmp_path)
    store = Store(tmp_path / "t.db")
    (tmp_path / "lessons").mkdir(exist_ok=True)
    (tmp_path / "lessons" / f"{DAY}.md").write_text(lesson_md())
    if plan:
        (tmp_path / "lessons" / f"{DAY}.plan.json").write_text(json.dumps(plan_json()))
    store.save_lesson(DAY, ["4.8", "4.2"])
    app = App(pack, store, tmp_path, token="secret")
    app.llm = FakeLLM(*verdicts)
    return app, store


def check(app, answer, chain):
    return list(app.checkin(DAY, 1, 1, answer, chain=chain))   # the question is line 1 of slide 1's say block


# transcript

def test_a_student_answer_creates_a_transcript_event_and_the_tutor_reply_too(tmp_path):
    app, store = setup(tmp_path, "WRONG")
    check(app, "it breaks the circuit", "c1")
    lines = store.transcript(DAY)
    assert [r["role"] for r in lines] == ["student", "tutor"]
    assert lines[0]["text"] == "it breaks the circuit" and lines[0]["step"] == "slide 1 line 1"


# association with the step and objective

def test_an_answer_is_associated_with_the_objective_of_its_check_not_the_first_objective(tmp_path):
    app, store = setup(tmp_path, "CORRECT")
    check(app, "it cuts power", "c1")
    rows = store.evidence_on(DAY)
    assert [r["objective"] for r in rows] == ["4.2"]          # the lesson's first objective is 4.8
    assert store.transcript(DAY)[0]["objective"] == "4.2"


def test_without_a_plan_the_first_objective_is_used_as_before(tmp_path):
    app, store = setup(tmp_path, "CORRECT", plan=False)
    check(app, "it cuts power", "c1")
    assert [r["objective"] for r in store.evidence_on(DAY)] == ["4.8"]


# verdicts

def test_correct_partial_and_wrong_are_recorded_with_their_verdict(tmp_path):
    app, store = setup(tmp_path, "CORRECT", "PARTIAL", "WRONG")
    for i, chain in enumerate(["a", "b", "c"]):
        check(app, f"answer {i}", chain)
    rows = store.evidence_on(DAY)
    assert [r["verdict"] for r in rows] == ["correct", "partial", "wrong"]
    assert [r["correct"] for r in rows] == [True, False, False]
    assert all(r["source"] == "checkin" for r in rows)


def test_a_misconception_is_recorded_only_when_the_marker_names_one(tmp_path):
    app, store = setup(tmp_path, "CORRECT", "WRONG\nMISCONCEPTION: 1")
    check(app, "it cuts power", "a")
    check(app, "it resets itself", "b")
    right, wrong = store.evidence_on(DAY)
    assert right["misconception"] == ""
    assert wrong["misconception"] == "A fuse resets itself."


def test_a_wrong_answer_with_no_named_belief_records_none(tmp_path):
    app, store = setup(tmp_path, "WRONG\nMISCONCEPTION: none")
    check(app, "no idea", "a")
    assert store.evidence_on(DAY)[0]["misconception"] == ""


def test_a_belief_number_outside_the_list_is_ignored(tmp_path):
    app, store = setup(tmp_path, "WRONG\nMISCONCEPTION: 9")
    check(app, "no idea", "a")
    assert store.evidence_on(DAY)[0]["misconception"] == ""


# end-of-lesson summary

def test_the_end_of_lesson_summary_is_built_from_the_evidence(tmp_path):
    app, store = setup(tmp_path, "CORRECT", "WRONG\nMISCONCEPTION: 1")
    check(app, "it cuts power", "a")
    check(app, "it resets itself", "b")
    app.answer(DAY, 0, "Firewall")                    # exam item wrong
    app.finish(DAY, "Fuses and exams.")
    out = store.outcome(DAY)
    assert out["demonstrated"] == []                 # 4.2 had a wrong answer too, so it is developing
    assert out["developing"] == ["4.2"]
    assert out["weak"] == ["4.8"]
    assert out["focus"] == ["4.8", "4.2"]
    assert out["misconceptions"] == [{"objective": "4.2", "belief": "A fuse resets itself."}]
    assert out["assessment"] == {"correct": 0, "total": 1}
    assert out["homework"] == [{"objective": "4.2", "task": "Read the fuse notes."}]
    assert out["not_assessed"] == []


def test_a_fully_correct_objective_is_demonstrated(tmp_path):
    app, store = setup(tmp_path, "CORRECT")
    check(app, "it cuts power", "a")
    app.answer(DAY, 0, "Fuse")
    app.finish(DAY, "")
    out = store.outcome(DAY)
    assert "4.2" in out["demonstrated"] and "4.8" in out["demonstrated"]
    assert out["assessment"] == {"correct": 1, "total": 1}


def test_a_lesson_without_a_plan_still_gets_an_outcome(tmp_path):
    app, store = setup(tmp_path, "WRONG", plan=False)
    check(app, "no idea", "a")
    app.finish(DAY, "")
    out = store.outcome(DAY)
    assert out["weak"] == ["4.8"] and out["homework"] == []


# the next lesson

def test_the_next_lesson_is_given_the_focus_and_misconceptions_as_fenced_data(tmp_path):
    app, store = setup(tmp_path, "WRONG\nMISCONCEPTION: 1")
    check(app, "it resets itself", "a")
    app.finish(DAY, "")
    pack = app.pack
    ctx = LP.evidence_context(pack, store, NEXT)
    assert "Last lesson focus (weak first): 4.2" in ctx
    assert '<data name="misconceptions seen last lesson">' in ctx
    assert "4.2: A fuse resets itself." in ctx


def test_nothing_is_added_for_the_next_lesson_before_any_outcome(tmp_path):
    app, store = setup(tmp_path)
    assert "Last lesson focus" not in LP.evidence_context(app.pack, store, NEXT)


# separation and progress

def test_raw_transcript_and_structured_evidence_are_separate_records(tmp_path):
    app, store = setup(tmp_path, "CORRECT")
    check(app, "it cuts power", "a")
    assert len(store.transcript(DAY)) == 2          # student + tutor lines
    assert len(store.evidence_on(DAY)) == 1         # one piece of evidence for one answer
    assert not any(k in store.evidence_on(DAY)[0] for k in ("ts", "role"))   # evidence has no transcript fields


def test_existing_progress_tracking_still_reads_the_evidence(tmp_path):
    app, store = setup(tmp_path, "CORRECT", "CORRECT")
    check(app, "one", "a")
    check(app, "two", "b")
    row = next(r for r in app.progress(NEXT)["objectives"] if r["id"] == "4.2")
    assert row["status"] == "practising"


# duplicates and failures

def test_a_repeated_check_in_event_creates_one_evidence_row(tmp_path):
    app, store = setup(tmp_path, "CORRECT", "CORRECT")
    check(app, "it cuts power", "same-chain")
    check(app, "it cuts power", "same-chain")
    assert len(store.evidence_on(DAY)) == 1
    assert len(store.transcript(DAY)) == 4          # the raw events are still kept


def test_a_repeated_exam_answer_creates_one_evidence_row(tmp_path):
    app, store = setup(tmp_path)
    app.answer(DAY, 0, "Fuse")
    app.answer(DAY, 0, "Fuse")
    rows = [r for r in store.evidence_on(DAY) if r["source"] == "exam"]
    assert len(rows) == 1


def test_a_failed_marker_records_no_evidence_and_says_so_in_the_log(tmp_path):
    app, store = setup(tmp_path, "RAISE")
    events = check(app, "it cuts power", "a")
    assert any(e["type"] == "done" for e in events)           # the lesson still goes on
    assert store.evidence_on(DAY) == []                        # nothing is claimed about the student
    assert len(store.transcript(DAY)) == 2                     # the words are still kept for review
    assert any(e["kind"] == "evaluation_failed" for e in store.events(limit=10))


def test_forgetting_a_lesson_clears_its_transcript_and_outcome(tmp_path):
    app, store = setup(tmp_path, "CORRECT")
    check(app, "it cuts power", "a")
    app.finish(DAY, "")
    store.forget_lessons([str(DAY)])
    assert store.transcript(DAY) == [] and store.outcome(DAY) is None
