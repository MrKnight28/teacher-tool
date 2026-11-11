"""Misconception judgement, the planner's use of misconceptions, and transcript retention."""
import datetime as dt
from pathlib import Path

from tutor import outcomes as O
from tutor.pack import load_pack
from tutor.planner import plan_objectives
from tutor.services.lessons import judge_check
from tutor.store import Store

PACKS = Path(__file__).resolve().parents[3] / "packs"
DAY = dt.date(2026, 10, 6)
BELIEFS = ["A fuse resets itself.", "Any fuse can be replaced by a coin."]


class Reply:
    def __init__(self, text=None, raise_=False):
        self.text, self.raise_, self.prompt = text, raise_, ""

    def complete(self, msgs, model, task):
        self.prompt = msgs[-1]["content"]
        if self.raise_:
            raise RuntimeError("marker down")
        return self.text


def test_the_marker_names_a_listed_belief_by_number():
    v, b = judge_check(Reply("WRONG\nMISCONCEPTION: 2"), "q", "key", "ans", BELIEFS)
    assert v == "wrong" and b == BELIEFS[1]


def test_no_named_belief_gives_none_and_out_of_range_is_ignored():
    assert judge_check(Reply("WRONG\nMISCONCEPTION: none"), "q", "k", "a", BELIEFS) == ("wrong", None)
    assert judge_check(Reply("WRONG\nMISCONCEPTION: 7"), "q", "k", "a", BELIEFS) == ("wrong", None)


def test_the_beliefs_are_fenced_as_data_in_the_marker_prompt():
    r = Reply("CORRECT\nMISCONCEPTION: none")
    judge_check(r, "q", "k", "a", BELIEFS)
    assert '<data name="beliefs">' in r.prompt and "1. A fuse resets itself." in r.prompt


def test_a_failed_marker_gives_no_verdict_and_no_belief():
    assert judge_check(Reply(raise_=True), "q", "k", "a", BELIEFS) == (None, None)


def test_without_listed_beliefs_only_the_verdict_is_asked_for():
    v, b = judge_check(Reply("PARTIAL"), "q", "k", "a", [])
    assert v == "partial" and b is None


def test_the_planner_puts_last_lessons_misconception_objectives_after_weak_ones(tmp_path):
    pack = load_pack(PACKS, "security-plus-sy0-701", tmp_path)
    store = Store(tmp_path / "t.db")
    store.save_outcome(dt.date(2026, 10, 5), O.build(dt.date(2026, 10, 5), ["2.4"], [
        {"objective": "2.4", "kind": "recall", "correct": False, "note": "", "source": "checkin", "verdict": "wrong",
         "misconception": "x"}], None))
    ids = plan_objectives(pack, store, DAY)
    assert ids[0] == "2.4"


def test_the_planner_still_works_with_no_outcome(tmp_path):
    pack = load_pack(PACKS, "security-plus-sy0-701", tmp_path)
    store = Store(tmp_path / "t.db")
    assert plan_objectives(pack, store, DAY)[0].startswith("4.")


def test_transcript_past_the_retention_limit_is_pruned_and_evidence_is_not(tmp_path):
    store = Store(tmp_path / "t.db")
    old = dt.date(2026, 6, 1)
    store.add_transcript(old, dt.datetime(2026, 6, 1, 9), "student", "old words")
    store.add_evidence("4.8", old, "recall", True, source="checkin", verdict="correct", event_key="old")
    store.add_transcript(DAY, dt.datetime(2026, 10, 6, 9), "student", "new words")
    removed = store.prune_transcript(DAY)
    assert removed == 1
    assert store.transcript(old) == [] and len(store.transcript(DAY)) == 1
    assert len(store.evidence("4.8")) == 1
