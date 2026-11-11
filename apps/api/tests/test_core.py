import datetime as dt
from pathlib import Path
from tutor.lesson_writer import write_lesson
from tutor.mastery import status
from tutor.pack import load_pack
from tutor.planner import plan_objectives
from tutor.store import Store

PACKS = Path(__file__).resolve().parents[3] / "packs"
D = dt.date


def pack():
    return load_pack(PACKS, "security-plus-sy0-701")


def test_pack_loads_and_weights_sum_to_100():
    p = pack()
    assert len(p.objectives) == 28
    assert sum(d["weight"] for d in p.domains.values()) == 100


def test_study_days_respect_rest_pause_and_exam():
    p = pack()
    assert p.is_study_day(D(2026, 10, 5))        # Monday
    assert not p.is_study_day(D(2026, 10, 10))   # Saturday
    assert not p.is_study_day(D(2027, 4, 7))     # example pause in the pack
    assert p.is_study_day(D(2027, 4, 12))        # after that pause
    assert not p.is_study_day(D(2027, 6, 30))    # example exam day


def test_new_objectives_start_with_heaviest_domain(tmp_path):
    p, s = pack(), Store(tmp_path / "t.db")
    assert plan_objectives(p, s, D(2026, 10, 5))[0].startswith("4.")


def test_saying_understood_is_not_mastery():
    assert status([], D(2026, 10, 5)) == "not_started"
    ev = [("2026-10-01", "recognise", 1)]
    assert status(ev, D(2026, 10, 5)) == "introduced"


def test_two_recent_misses_need_reinforcement_and_get_replanned(tmp_path):
    p, s = pack(), Store(tmp_path / "t.db")
    s.add_evidence("4.8", D(2026, 10, 5), "recall", False)
    s.add_evidence("4.8", D(2026, 10, 5), "apply_familiar", False)
    assert plan_objectives(p, s, D(2026, 10, 6))[0] == "4.8"


def test_missed_lesson_rolls_into_next(tmp_path):
    p, s = pack(), Store(tmp_path / "t.db")
    s.save_lesson(D(2026, 10, 5), ["2.4", "2.5"], status="missed")
    assert plan_objectives(p, s, D(2026, 10, 6))[:2] == ["2.4", "2.5"]


def test_demonstrated_then_due_for_review():
    ev = [("2026-10-01", "apply_familiar", 1), ("2026-10-02", "delayed_recall", 1)]
    assert status(ev, D(2026, 10, 3)) == "demonstrated"
    assert status(ev, D(2026, 10, 9)) == "due_for_review"


def test_write_lesson_offline_and_skips_rest_day(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    p, s = pack(), Store(tmp_path / "t.db")
    out = write_lesson(p, s, tmp_path, D(2026, 10, 6))
    assert out and out.read_text().startswith("<!-- objectives:")
    assert s.lesson(D(2026, 10, 6))["status"] == "planned"
    assert write_lesson(p, s, tmp_path, D(2026, 10, 10)) is None
