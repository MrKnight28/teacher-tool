import datetime as dt
import json
from pathlib import Path

import pytest
from tutor.pack import load_pack
from tutor.settings import Settings
from tutor.setup_core import apply, recommend

PACKS = Path(__file__).resolve().parents[3] / "packs"
D = dt.date


def test_pack_defaults_apply_when_nothing_saved(tmp_path):
    p = load_pack(PACKS, "security-plus-sy0-701", tmp_path)
    assert p.config["exam_date"] == D(2027, 6, 30)
    assert not p.is_study_day(D(2027, 4, 7))  # the pack's example pause


def test_saved_exam_date_and_trip_pause_override_the_pack(tmp_path):
    Settings(tmp_path).update({"exam_date": "2027-07-15", "pause_start": "2026-11-10", "pause_end": "2026-11-12"})
    p = load_pack(PACKS, "security-plus-sy0-701", tmp_path)
    assert p.config["exam_date"] == D(2027, 7, 15)
    assert not p.is_study_day(D(2026, 11, 11))   # new pause
    assert p.is_study_day(D(2027, 4, 7))         # saved pause replaced the pack pause
    assert p.is_study_day(D(2027, 6, 30))        # example exam day is a study day once the date is overridden


def test_blank_pause_start_means_no_trip_pause(tmp_path):
    Settings(tmp_path).update({"pause_start": ""})
    p = load_pack(PACKS, "security-plus-sy0-701", tmp_path)
    assert p.config["pause_ranges"] == []
    assert p.is_study_day(D(2026, 11, 24))


def test_pause_end_defaults_to_start(tmp_path):
    Settings(tmp_path).update({"pause_start": "2026-11-10", "pause_end": ""})
    p = load_pack(PACKS, "security-plus-sy0-701", tmp_path)
    assert not p.is_study_day(D(2026, 11, 10))
    assert p.is_study_day(D(2026, 11, 11))


@pytest.mark.parametrize("changes", [
    {"exam_date": "30/06/2027"}, {"exam_date": "2026-13-01"},
    {"pause_start": "tomorrow"}, {"pause_start": "2026-11-12", "pause_end": "2026-11-10"},
])
def test_bad_dates_are_rejected(tmp_path, changes):
    with pytest.raises(ValueError):
        Settings(tmp_path).update(changes)
    assert not (tmp_path / "settings.json").exists()


def test_wizard_saves_dates_and_keeps_pause_when_field_missing(tmp_path):
    form = {"name": "Kyle", "lesson_time": "08:30", "exam_date": "2027-05-15",
            "pause_start": "2027-08-02", "pause_end": "2027-08-06", "rest_days": "sat,sun"}
    apply(tmp_path, form, recommend([]))
    s = Settings(tmp_path / "data").get()
    assert s["exam_date"] == "2027-05-15" and s["pause_start"] == "2027-08-02" and s["pause_end"] == "2027-08-06"
    # An older form without pause fields must not clear the saved pause.
    apply(tmp_path, {"name": "Kyle", "rest_days": "sat,sun"}, recommend([]))
    s = Settings(tmp_path / "data").get()
    assert s["pause_start"] == "2027-08-02" and s["exam_date"] == "2027-05-15"
    assert json.loads((tmp_path / "data" / "settings.json").read_text())["pause_end"] == "2027-08-06"
