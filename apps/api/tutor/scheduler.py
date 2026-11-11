"""Scheduler: nightly lesson writing, reminders, late-join ladder, missed-lesson handling.
tick() is pure apart from store/notifier calls, so it is easy to test with any 'now'."""
from __future__ import annotations
import datetime as dt
import os
from .lesson_writer import write_lesson
from .notify import Notifier
from .pack import Pack
from .settings import Settings
from .store import Store
from . import whatsapp as WA

NIGHTLY_AT = dt.time(21, 0)
MAX_WRITE_ATTEMPTS = 3
# OpenClaw runs an agent turn per reminder; its usage isn't reported to us, so each turn is charged this estimate.
OPENCLAW_TURN_USD = 0.01
RETRY_GAP = dt.timedelta(minutes=30)
REMIND_BEFORE_MIN = 15

TEXT = {
    "gentle": {
        "reminder": "Morning! Your Security+ lesson starts at {time}. Today: {topics}.",
        "late": "Your lesson started {mins} min ago. Jump in whenever you're ready.",
        "missed": "No lesson today, that's OK. I've moved today's topics ({topics}) to your next lesson.",
    },
    "firm": {
        "reminder": "Security+ lesson at {time}. Today: {topics}. Be ready.",
        "late": "You're {mins} min late for today's lesson. Open the tutor now.",
        "missed": "Lesson missed. {topics} rolled into the next lesson. Let's not make it two.",
    },
    "strict": {
        "reminder": "Lesson at {time} sharp. Topics: {topics}. Exam is {days} days away.",
        "late": "{mins} min late. The exam is {days} days away. Start the lesson now.",
        "missed": "Missed. {topics} carried over. {days} days to the exam.",
    },
}


def _in_quiet(now: dt.datetime, start: str, end: str) -> bool:
    t, s, e = now.time(), dt.time.fromisoformat(start), dt.time.fromisoformat(end)
    return (s <= t or t < e) if s > e else (s <= t < e)


def _send(store: Store, notifier: Notifier, settings: dict, now: dt.datetime, kind: str, text: str) -> bool:
    """Send once per (day, kind), within the daily cap and outside quiet hours."""
    day = now.date()
    if store.was_sent(day, kind):
        return False
    if store.sent_count(day) >= settings["max_messages_per_day"]:
        return False
    if _in_quiet(now, settings["quiet_start"], settings["quiet_end"]):
        return False
    if notifier.send(text):
        store.mark_sent(day, kind)
        if "openclaw" in notifier.name:  # counts toward the monthly cap, like lesson calls
            model = os.environ.get("MODEL_CHEAP", "")
            store.add_usage(day, f"reminder: {kind} (openclaw turn, estimate)", model,
                            0.0 if model.endswith(":free") else OPENCLAW_TURN_USD)
        return True
    return False


def try_write(pack, store: Store, data_dir, day: dt.date, now: dt.datetime, write=write_lesson) -> str:
    """Write the lesson for `day`, at most MAX_WRITE_ATTEMPTS times, RETRY_GAP apart. Records why it failed."""
    n, last = store.attempts(day, "write")
    if n >= MAX_WRITE_ATTEMPTS or (last is not None and now - last < RETRY_GAP):
        return ""
    store.attempt(day, "write", now)  # counted before the call, so a crash can't cause a retry storm
    try:
        if write(pack, store, data_dir, day):
            store.log_event(now, "write", f"lesson for {day} written")
            return "wrote_lesson"
        return ""
    except Exception as e:  # network/model errors: recorded and shown in admin > Setup & health
        detail = f"{type(e).__name__}: {e}"
        body = getattr(e, "read", None)
        if callable(body):
            try:
                detail += " | " + body().decode(errors="ignore")[:300]
            except Exception:  # noqa: BLE001
                pass
        store.log_event(now, "write_failed", f"lesson for {day}: {detail}"[:600])
        return f"write_failed: {detail}"[:300]


def maybe_backup(data_dir, backup_dir, store: Store, now: dt.datetime) -> list[str]:
    """Once a day, after 02:00, copy data to backup_dir. Off when backup_dir is unset."""
    today = now.date()
    if not backup_dir or now.time() < dt.time(2, 0) or store.was_sent(today, "backup_logged"):
        return []
    store.mark_sent(today, "backup_logged")
    try:
        from .backup import backup
        backup(data_dir, backup_dir, today)
        return ["backup"]
    except OSError as e:
        return [f"backup_failed: {e}"]


def ensure_lessons(pack: Pack, store: Store, s: dict, data_dir, now: dt.datetime, write) -> list[str]:
    """Write today's lesson if missing (catch-up), and tomorrow's after NIGHTLY_AT."""
    today = now.date()
    done: list[str] = []
    # Catch-up: today's lesson is missing (night write failed or the PC was off) -> write it now.
    if not s["paused"] and pack.is_study_day(today) and store.lesson(today) is None:
        r = try_write(pack, store, data_dir, today, now, write)
        if r:
            done.append(r if r.startswith("write_failed") else "wrote_today")
            start_t = dt.time.fromisoformat(s["lesson_time"])
            if not r.startswith("write_failed") and now.time() >= start_t:
                store.mark_sent(today, "catchup_logged")  # written late: no late nudges or 'missed' for today
    # Nightly: write tomorrow's lesson.
    tomorrow = today + dt.timedelta(days=1)
    if now.time() >= NIGHTLY_AT and store.lesson(tomorrow) is None and pack.is_study_day(tomorrow):
        r = try_write(pack, store, data_dir, tomorrow, now, write)
        if r:
            done.append(r)
    return done


def send_reminders(pack: Pack, store: Store, s: dict, notifier: Notifier, now: dt.datetime) -> list[str]:
    """Reminder before the lesson, late nudges, and 'missed' once the last nudge passes."""
    today = now.date()
    if s["paused"] or not pack.is_study_day(today):
        return []
    done: list[str] = []
    lesson = store.lesson(today)
    if lesson is None:
        return done
    when = WA.lesson_time(store, s, today)   # a 'move' sent on WhatsApp changes today's time only
    start = dt.datetime.combine(today, dt.time.fromisoformat(when))
    words = TEXT[s["tone"]]
    topics = ", ".join(lesson["objectives"]) or "review"
    exam = pack.config.get("exam_date")
    days = (exam - today).days if exam else "?"
    fmt = dict(time=when, topics=topics, days=days)
    if lesson["status"] == "planned" and not store.was_sent(today, "catchup_logged"):
        if start - dt.timedelta(minutes=REMIND_BEFORE_MIN) <= now < start:
            if _send(store, notifier, s, now, "reminder", words["reminder"].format(**fmt)):
                done.append("reminder")
        nudges = s["late_nudges_min"]
        mins_late = int((now - start).total_seconds() // 60)
        if nudges and mins_late >= nudges[-1]:
            store.save_lesson(today, lesson["objectives"], "missed")
            store.mark_sent(today, "missed_logged")
            _send(store, notifier, s, now, "missed", words["missed"].format(**fmt))
            done.append("missed")
        else:
            for n in reversed(nudges[:-1]):
                if mins_late >= n:
                    if _send(store, notifier, s, now, f"late_{n}", words["late"].format(mins=mins_late, **fmt)):
                        done.append(f"late_{n}")
                    break
    return done


def send_accountability(pack: Pack, store: Store, s: dict, notifier: Notifier, data_dir, now: dt.datetime) -> list[str]:
    """The evening check-in on study days, and the Sunday report, at checkin_time. Off when checkin_time is ""."""
    if not s.get("checkin_time") or s["paused"] or now.time() < dt.time.fromisoformat(s["checkin_time"]):
        return []
    today, done = now.date(), []
    text = WA.checkin_text(pack, store, s, today)
    if text and _send(store, notifier, s, now, "checkin", text):
        done.append("checkin")
    if s.get("weekly_report", True) and today.weekday() == 6:
        start = s.get("pack_lessons_from")
        start = str(pack.config.get("lessons_from") or "") if start is None else start
        if _send(store, notifier, s, now, "weekly", WA.weekly_text(pack, store, data_dir, s, today, start or None)):
            done.append("weekly")
    return done


def tick(pack: Pack, store: Store, settings: Settings, notifier: Notifier, data_dir, now: dt.datetime,
         write=write_lesson, backup_dir=None) -> list[str]:
    s = settings.get()
    done = maybe_backup(data_dir, backup_dir, store, now)
    if not s.get("lesson_generator", True):
        return done  # generator off: no lessons are written, and nothing to remind about
    done += ensure_lessons(pack, store, s, data_dir, now, write)
    done += send_reminders(pack, store, s, notifier, now)
    done += send_accountability(pack, store, s, notifier, data_dir, now)
    return done
