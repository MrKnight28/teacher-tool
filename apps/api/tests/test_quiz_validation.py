import datetime as dt
import json
from pathlib import Path

from tutor import quiz as Q
from tutor import lesson as L
from tutor.lesson_writer import write_lesson
from tutor.pack import load_pack
from tutor.store import Store

PACKS = Path(__file__).resolve().parents[3] / "packs"
DAY = dt.date(2026, 10, 5)


class Scripted:
    """Stands in for LLM: returns the scripted replies in order and records the calls."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def complete(self, messages, model, task):
        self.calls.append(messages)
        return self.replies.pop(0)


def lesson(objective, n=3):
    items = [{"objective": objective, "type": "free_text", "q": f"Question {i}?", "answer": "phishing", "why": "x"}
             for i in range(n)]
    return "# Lesson\n\nTeach it.\n\n```quiz\n" + json.dumps(items) + "\n```\n"


# The structured plan is asked for first. These replies are not a plan, so the plan is rejected twice
# (two calls) and the Markdown lesson below runs as the fallback.
NOT_A_PLAN = "Here is your lesson, no JSON."


def setup(tmp_path):
    p = load_pack(PACKS, "security-plus-sy0-701", tmp_path)
    return p, p.objectives[0]["id"], Store(tmp_path / "t.db")


def test_valid_quiz_first_time_needs_one_call(tmp_path):
    p, oid, s = setup(tmp_path)
    llm = Scripted(NOT_A_PLAN, NOT_A_PLAN, NOT_A_PLAN, lesson(oid))
    write_lesson(p, s, tmp_path, DAY, model="m", llm=llm)
    assert len(llm.calls) == 4  # three rejected plans, then one Markdown lesson
    assert "backup" not in (tmp_path / "lessons" / f"{DAY}.md").read_text().lower()


def test_bad_quiz_is_retried_once_with_the_problem(tmp_path):
    p, oid, s = setup(tmp_path)
    llm = Scripted(NOT_A_PLAN, NOT_A_PLAN, NOT_A_PLAN, lesson("9.9"), lesson(oid))
    write_lesson(p, s, tmp_path, DAY, model="m", llm=llm)
    assert len(llm.calls) == 5
    assert "unknown objective ids 9.9" in llm.calls[4][-1]["content"]
    assert Q.problem((tmp_path / "lessons" / f"{DAY}.md").read_text(), {o["id"] for o in p.objectives}) is None


def test_still_bad_after_retry_gets_backup_quiz(tmp_path):
    p, oid, s = setup(tmp_path)
    llm = Scripted(NOT_A_PLAN, NOT_A_PLAN, NOT_A_PLAN, lesson("9.9"), lesson("9.9"))
    write_lesson(p, s, tmp_path, DAY, model="m", llm=llm)
    text = (tmp_path / "lessons" / f"{DAY}.md").read_text()
    items = L.quiz_items(text)
    assert 1 <= len(items) <= 3
    assert all(q["objective"] in {o["id"] for o in p.objectives} for q in items)
    assert "Backup question" in items[0]["why"]
    assert any(e["kind"] == "quiz" and "backup" in e["detail"] for e in s.events(limit=20))


def test_backup_quiz_does_not_leak_into_student_text():
    block = Q.backup_quiz({"4.1": "phishing"})
    assert L.student_text("Intro\n\n" + block).strip() == "Intro"
