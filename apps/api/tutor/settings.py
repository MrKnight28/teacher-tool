"""User-editable settings (admin panel). Stored in data/settings.json, validated, never in the read-only pack."""
from __future__ import annotations
import json
import re
from pathlib import Path

DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
DEFAULTS = {
    "lesson_time": "09:00", "rest_days": ["sat", "sun"], "paused": False,
    "lesson_generator": True,  # False: no lessons are written; the practice lesson is used for every date
    "max_messages_per_day": 8, "quiet_start": "22:00", "quiet_end": "07:00",
    "tone": "firm", "late_nudges_min": [5, 20, 60], "chat_model": "",
    "timezone": "Europe/London", "monthly_cap_gbp": 20, "gbp_usd_rate": 1.3,
    "voice_provider": "gemini",
    # Speech. Whisper runs on this PC; the lesson voice is the browser's own (free, instant) or Gemini (sentence by sentence).
    "whisper_model": "base.en", "stt_prompt": "off", "auto_advance": "off", "lesson_voice": "kokoro", "tts_fallback": "piper", "gemini_billing": "free",
    # Exam date and one trip pause. null = use the course pack's value; "" pause_start = no pause.
    "exam_date": None, "pause_start": None, "pause_end": None,
    # Course lessons (packs/<pack>/lessons) are given one a study day from this date; then the writer takes over.
    # null = the pack's lessons_from; "" = never (the nightly writer writes every lesson).
    "pack_lessons_from": None,
    # WhatsApp accountability: an evening check-in on study days ("" = off) and a Sunday report at the same time.
    "checkin_time": "20:00", "weekly_report": True,
}


def _hhmm(v):
    if not (isinstance(v, str) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v)):
        raise ValueError("must be HH:MM")
    return v


def _isodate(v):
    import datetime as dt
    try:
        dt.date.fromisoformat(v)
    except (TypeError, ValueError):
        raise ValueError("date must be YYYY-MM-DD")
    return v


def _validate(k, v):
    if k in ("lesson_time", "quiet_start", "quiet_end"):
        return _hhmm(v)
    if k == "checkin_time":
        return "" if v == "" else _hhmm(v)
    if k == "weekly_report":
        if not isinstance(v, bool):
            raise ValueError("weekly_report must be true/false")
        return v
    if k == "exam_date":
        return None if v in (None, "") else _isodate(v)
    if k in ("pause_start", "pause_end", "pack_lessons_from"):
        return None if v is None else ("" if v == "" else _isodate(v))
    if k == "rest_days":
        if not (isinstance(v, list) and set(v) <= DAYS):
            raise ValueError("rest_days must be a list of mon..sun")
        return sorted(set(v))
    if k == "lesson_generator":
        if not isinstance(v, bool):
            raise ValueError("lesson_generator must be true/false")
        return v
    if k == "paused":
        if not isinstance(v, bool):
            raise ValueError("paused must be true/false")
        return v
    if k == "max_messages_per_day":
        if not (isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 8):
            raise ValueError("0-8")
        return v
    if k == "tone":
        if v not in ("gentle", "firm", "strict"):
            raise ValueError("gentle|firm|strict")
        return v
    if k == "late_nudges_min":
        if not (isinstance(v, list) and len(v) <= 4 and all(isinstance(x, int) and 1 <= x <= 240 for x in v)):
            raise ValueError("up to 4 ints, 1-240")
        return sorted(v)
    if k == "chat_model":
        if not (isinstance(v, str) and re.fullmatch(r"[\w.\-:/]{0,100}", v)):
            raise ValueError("bad model id")
        return v
    if k == "voice_provider":
        if v not in ("gemini", "openai", "none"):
            raise ValueError("voice provider: gemini|openai|none")
        return v
    if k == "whisper_model":
        if v not in ("tiny.en", "base.en", "small.en"):
            raise ValueError("speech model: tiny.en|base.en|small.en")
        return v
    if k == "lesson_voice":
        if v not in ("kokoro", "piper", "browser", "gemini"):
            raise ValueError("lesson voice: kokoro|piper|browser|gemini")
        return v
    if k == "auto_advance":
        if v not in ("on", "off"):
            raise ValueError("auto advance: on|off")
        return v
    if k == "stt_prompt":
        if v not in ("on", "off"):
            raise ValueError("speech prompt: on|off")
        return v
    if k == "tts_fallback":
        if v not in ("piper", "none"):
            raise ValueError("fallback voice: piper|none")
        return v
    if k == "gemini_billing":
        if v not in ("free", "paid"):
            raise ValueError("Gemini billing: free|paid")
        return v
    if k == "timezone":
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            raise ValueError("unknown time zone (e.g. Europe/London)")
        return v
    if k == "monthly_cap_gbp":
        if not (isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 500):
            raise ValueError("cap must be 0-500")
        return v
    if k == "gbp_usd_rate":
        if not (isinstance(v, (int, float)) and not isinstance(v, bool) and 0.5 <= v <= 3):
            raise ValueError("rate must be 0.5-3")
        return v
    raise ValueError(f"unknown setting {k}")


class Settings:
    def __init__(self, data_dir: Path):
        self.path = Path(data_dir) / "settings.json"

    def get(self) -> dict:
        out = dict(DEFAULTS)
        if self.path.exists():
            try:
                saved = json.loads(self.path.read_text())
                for k, v in saved.items():
                    if k in DEFAULTS:
                        out[k] = _validate(k, v)
            except (ValueError, json.JSONDecodeError):
                pass  # corrupt file falls back to defaults
        return out

    def update(self, changes: dict) -> dict:
        cur = self.get()
        for k, v in changes.items():
            cur[k] = _validate(k, v)
        if cur["pause_start"] and cur["pause_end"] and cur["pause_end"] < cur["pause_start"]:
            raise ValueError("trip pause must end on or after its start")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(cur, indent=2))
        return cur


def local_now(data_dir) -> "dt.datetime":
    """Naive local time in the configured time zone (containers run in UTC)."""
    import datetime as dt
    from zoneinfo import ZoneInfo
    return dt.datetime.now(ZoneInfo(Settings(data_dir).get()["timezone"])).replace(tzinfo=None)
