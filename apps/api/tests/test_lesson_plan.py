import copy
import datetime as dt
import json
from pathlib import Path

from tutor import lesson as L
from tutor import lesson_plan as P
from tutor.lesson_writer import write_lesson
from tutor.pack import load_pack
from tutor.planner import plan_objectives
from tutor.store import Store

PACKS = Path(__file__).resolve().parents[3] / "packs"
DAY = dt.date(2026, 10, 5)
D = dt.date


class Scripted:
    """Stands in for LLM: returns the scripted replies in order and records the calls."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def complete(self, messages, model, task):
        self.calls.append(messages)
        return self.replies.pop(0)


def fenced(plan) -> str:
    return "Here is the plan.\n```json\n" + json.dumps(plan, indent=1) + "\n```\n"


def good_plan(ids):
    return {
        "title": "Incident response and indicators",
        "sections": [{
            "stage": "teaching", "title": f"Concept {oid}", "objectives": [oid],
            "content": ["Plain meaning of the concept.", "How it is worded in practice material."],
            "examples": ["A worked scenario from a help desk."],
            "say": [f"Start with what {oid} means, then see where it matters on a real network.",
                    "Hold on to the key idea, because the scenario that follows depends on it."],
            "checks": [{"question": f"Explain {oid} in your own words?", "expect": "the key idea", "objective": oid}],
            "misconceptions": [{"belief": "it means the same as a related term", "correction": "it is narrower"}],
            "application": {"scenario": "A user reports a slow laptop.", "question": "What is the first step?",
                            "expect": "check the indicators", "objective": oid},
        } for oid in ids],
        "retrieval": [{"question": "What does CIA stand for?", "expect": "confidentiality, integrity, availability",
                       "objective": ids[0]}],
        "exam_questions": [{"objective": oid, "q": f"Exam question {n} on {oid}?",
                            "options": ["Alpha", "Beta", "Gamma", "Delta"], "answer": "Beta", "why": "Beta is right."}
                           for oid in ids for n in range(2)],
        "homework": [{"objective": ids[0], "task": "Read the notes on the concept."}],
    }


def setup(tmp_path):
    p = load_pack(PACKS, "security-plus-sy0-701", tmp_path)
    s = Store(tmp_path / "t.db")
    return p, s, plan_objectives(p, s, DAY)


def test_valid_plan_needs_one_call_and_renders_a_lesson(tmp_path):
    p, s, ids = setup(tmp_path)
    llm = Scripted(fenced(good_plan(ids)))
    out = write_lesson(p, s, tmp_path, DAY, model="m", llm=llm)
    assert len(llm.calls) == 1
    lesson = L.Lesson.parse(out.read_text(), p.config["stages"])
    assert lesson.title == "Incident response and indicators"
    assert lesson.objectives == ids
    assert [st["name"] for st in lesson.stages] == ["Retrieval", "Teaching"]
    assert [st["minutes"] for st in lesson.stages] == [5, 15]
    assert "Concept " + ids[0] in [sl["title"] for sl in lesson.slides]
    assert s.lesson(DAY)["status"] == "planned"
    saved = json.loads((tmp_path / "lessons" / f"{DAY}.plan.json").read_text())
    assert saved == good_plan(ids)  # the plan is kept for the homework build


def test_exam_questions_are_marked_and_separate_from_teaching_checks(tmp_path):
    p, s, ids = setup(tmp_path)
    out = write_lesson(p, s, tmp_path, DAY, model="m", llm=Scripted(fenced(good_plan(ids))))
    lesson = L.Lesson.parse(out.read_text(), p.config["stages"])
    assert lesson.quiz and all(q["source"] == "exam" for q in lesson.quiz)
    assert all(q["type"] == "multiple_choice" and len(q["options"]) == 4 for q in lesson.quiz)
    says = [i for sl in lesson.scripts.values() for i in sl]
    checks = [i["text"] for i in says if i["question"]]
    assert checks and not set(checks) & {q["q"] for q in lesson.quiz}
    # exam questions are not spoken and not shown on the slides; only the quiz block carries them
    spoken = " ".join(i["text"] for i in says)
    assert "Exam question" not in spoken and "Exam question" not in L.student_text(out.read_text())


def test_each_objective_is_attached_to_teaching_and_exam_content(tmp_path):
    p, s, ids = setup(tmp_path)
    stages = list(p.config["stages"])
    assert P.problem(good_plan(ids), ids, stages) is None
    bad = copy.deepcopy(good_plan(ids))
    bad["sections"] = bad["sections"][:1]  # the second objective loses its teaching section
    assert "no teaching section for objective " + ids[1] in P.problem(bad, ids, stages)
    bad = copy.deepcopy(good_plan(ids))
    bad["exam_questions"] = [q for q in bad["exam_questions"] if q["objective"] == ids[0]] * 2  # 4 items, none on ids[1]
    assert "no exam question for objective " + ids[1] in P.problem(bad, ids, stages)
    bad = copy.deepcopy(good_plan(ids))
    bad["sections"][0]["checks"][0]["objective"] = "9.9"
    assert "not in this lesson" in P.problem(bad, ids, stages)


def test_invalid_or_missing_sections_are_named(tmp_path):
    p, s, ids = setup(tmp_path)
    stages = list(p.config["stages"])
    assert P.problem(None, ids, stages) == "the reply has no JSON object"
    no_sections = {k: v for k, v in good_plan(ids).items() if k != "sections"}
    assert P.problem(no_sections, ids, stages) == "missing sections"
    empty = dict(good_plan(ids), sections=[])
    assert P.problem(empty, ids, stages) == "missing sections"
    wrong_stage = copy.deepcopy(good_plan(ids))
    wrong_stage["sections"][0]["stage"] = "lecture"
    assert "unknown stage 'lecture'" in P.problem(wrong_stage, ids, stages)
    few = copy.deepcopy(good_plan(ids))
    few["exam_questions"] = few["exam_questions"][:2]
    assert P.problem(few, ids, stages) == "exam_questions needs at least 3 items"
    three_opts = copy.deepcopy(good_plan(ids))
    three_opts["exam_questions"][0]["options"] = ["Alpha", "Beta", "Gamma"]
    assert "exactly 4 different options" in P.problem(three_opts, ids, stages)
    not_option = copy.deepcopy(good_plan(ids))
    not_option["exam_questions"][0]["answer"] = "B"  # the answer must be the option text the student picks
    assert "answer must be exactly one of the options" in P.problem(not_option, ids, stages)
    no_check = copy.deepcopy(good_plan(ids))
    no_check["sections"][0]["checks"] = []
    assert "needs 1 or 2 checks" in P.problem(no_check, ids, stages)


def test_bad_plan_is_retried_once_with_the_problem(tmp_path):
    p, s, ids = setup(tmp_path)
    broken = {k: v for k, v in good_plan(ids).items() if k != "sections"}
    llm = Scripted(fenced(broken), fenced(good_plan(ids)))
    out = write_lesson(p, s, tmp_path, DAY, model="m", llm=llm)
    assert len(llm.calls) == 2
    assert "The plan was rejected: missing sections" in llm.calls[1][-1]["content"]
    assert "```quiz" in out.read_text() and (tmp_path / "lessons" / f"{DAY}.plan.json").exists()
    assert any(e["kind"] == "lesson_plan" and "missing sections" in e["detail"] for e in s.events(limit=10))


def test_plan_invalid_twice_falls_back_to_the_markdown_lesson(tmp_path):
    p, s, ids = setup(tmp_path)
    broken = {k: v for k, v in good_plan(ids).items() if k != "sections"}
    markdown = "# Fallback lesson\n\nTeach it.\n\n```quiz\n" + json.dumps(
        [{"objective": ids[0], "type": "free_text", "q": f"Q{i}?", "answer": "x", "why": "y"} for i in range(3)]) + "\n```\n"
    llm = Scripted(fenced(broken), fenced(broken), fenced(broken), markdown)
    out = write_lesson(p, s, tmp_path, DAY, model="m", llm=llm)
    assert len(llm.calls) == 4
    assert "# Fallback lesson" in out.read_text()
    assert not (tmp_path / "lessons" / f"{DAY}.plan.json").exists()


def test_previous_evidence_and_weak_objectives_reach_the_prompt(tmp_path):
    p, s, ids = setup(tmp_path)
    s.save_lesson(D(2026, 10, 2), ["4.8"], status="done", summary="Covered phishing and vishing.")
    s.add_evidence("4.8", D(2026, 10, 2), "recall", False)
    s.add_evidence("4.8", D(2026, 10, 2), "apply_familiar", False)
    s.add_evidence("2.4", D(2026, 10, 2), "recognise", True)
    ids = plan_objectives(p, s, DAY)  # the weak objective 4.8 comes first
    assert ids[0] == "4.8"
    llm = Scripted(fenced(good_plan(ids)))
    write_lesson(p, s, tmp_path, DAY, model="m", llm=llm)
    prompt = llm.calls[0][-1]["content"]
    assert "Covered phishing and vishing." in prompt
    assert "4.8 needs_reinforcement" in prompt and "2.4 introduced" in prompt
    assert "Weak objectives to revisit (use retrieval and checks on these): 4.8" in prompt


def test_parse_plan_reads_a_fence_or_bare_json():
    assert P.parse_plan(fenced({"a": 1})) == {"a": 1}
    assert P.parse_plan('{"a": 2}') == {"a": 2}
    assert P.parse_plan("no json here") is None
    assert P.parse_plan("") is None


def test_rendered_text_cannot_break_the_lesson_markup(tmp_path):
    p, s, ids = setup(tmp_path)
    plan = good_plan(ids)
    plan["sections"][0]["content"] = ["Use ```bash rm -rf``` as a trap"]
    # bare JSON, because the backticks would close a ```json fence
    out = write_lesson(p, s, tmp_path, DAY, model="m", llm=Scripted(json.dumps(plan)))
    text = out.read_text()
    assert "```bash" not in text
    assert len(L.Lesson.parse(text, p.config["stages"]).quiz) == len(ids) * 2
