"""The WhatsApp accountability bot: replies to the student's messages, the evening check-in, and the Sunday report.

Replies come from the tutor-replies OpenClaw plugin (openclaw-plugin/tutor-replies), which claims every WhatsApp DM
before the OpenClaw agent sees it and posts it to /api/wa/inbound with its own token (TUTOR_WA_TOKEN). The bot answers
from the tutor's own data with fixed commands. No model is called, so a message can't instruct anything and costs nothing.

Commands: status, move 19:00 (today only), skip (today), quiz then a letter, help.
Quiz answers are marked here; the right answer is only shown after an attempt, as on the lesson page.
The check-in and report are sent by the scheduler through the normal notifier, inside the daily cap and quiet hours.
"""
from __future__ import annotations

import datetime as dt
import json
import random
import re
from pathlib import Path

from . import quiz as Q
from .importer import preview
from .lesson import Lesson
from .mastery import status

LETTERS = "ABCD"
HELP = ("I'm your Security+ tutor. Send:\n"
        "status - today's lesson, streak, days to the exam\n"
        "move 19:00 - move today's lesson\n"
        "skip - skip today (the topics move to your next lesson)\n"
        "quiz - a question from a lesson you've done\n"
        "help - this list")
TIME_RE = re.compile(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?\b", re.I)


# ---------- shared facts ----------

def lesson_time(store, s: dict, day: dt.date) -> str:
    """Today's lesson time: a 'move' for this day if there is one, else the usual time."""
    return store.get_kv(f"time:{day}") or s["lesson_time"]


def lesson_title(data_dir: Path, day: dt.date) -> str:
    f = Path(data_dir) / "lessons" / f"{day}.md"
    if not f.exists():
        return ""
    m = re.search(r"^# (.+)$", f.read_text(encoding="utf-8"), re.M)
    return m.group(1).strip() if m else ""


def streak(pack, store, today: dt.date) -> int:
    """Study days in a row with the lesson finished, counting back from today (or yesterday, if today isn't done yet).
    Rest days and pauses don't count either way."""
    n, day = 0, today
    row = store.lesson(day)
    if not (row and row["status"] == "done"):
        day -= dt.timedelta(days=1)
    for _ in range(400):
        if pack.is_study_day(day):
            row = store.lesson(day)
            if not (row and row["status"] == "done"):
                break
            n += 1
        day -= dt.timedelta(days=1)
    return n


def days_to_exam(pack, today: dt.date):
    exam = pack.config.get("exam_date")
    return (exam - today).days if exam else None


def _parse_time(text: str) -> str | None:
    m = TIME_RE.search(text)
    if not m:
        return None
    h, mins, ampm = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
    if ampm == "pm" and h < 12:
        h += 12
    if ampm == "am" and h == 12:
        h = 0
    if not (0 <= h <= 23 and 0 <= mins <= 59) or (not ampm and not m.group(2)):
        return None   # "move 7" is ambiguous; "move 7pm" or "move 19:00" is not
    return f"{h:02d}:{mins:02d}"


# ---------- replies ----------

class Bot:
    def __init__(self, pack, store, data_dir: Path, settings, now: dt.datetime):
        self.pack, self.store, self.data, self.settings, self.now = pack, store, Path(data_dir), settings, now
        self.today = now.date()

    def handle(self, text: str) -> str:
        t = " ".join(str(text or "").split())[:300]
        low = t.lower()
        pending = self.store.get_kv("wa_quiz")
        if pending and re.fullmatch(r"\(?([abcd])\)?[.)]?", low):
            return self._answer(json.loads(pending), LETTERS.index(low.strip("().")[0].upper()))
        word = low.split(" ")[0] if low else ""
        if word in ("status", "today", "streak"):
            return self.status()
        if word in ("move", "at", "reschedule"):
            return self.move(t)
        if word == "skip":
            return self.skip()
        if word == "quiz":
            return self.quiz()
        if word in ("help", "menu", "hi", "hello", "?", "commands"):
            return HELP
        return "I didn't get that. " + HELP

    def status(self) -> str:
        s = self.settings.get()
        row = self.store.lesson(self.today)
        title = lesson_title(self.data, self.today)
        if s["paused"] or not self.pack.is_study_day(self.today):
            line = "No lesson today (rest day or pause)."
        elif row is None:
            line = "Today's lesson isn't ready yet."
        else:
            when = lesson_time(self.store, s, self.today)
            state = {"planned": f"at {when}, not started yet", "started": "started, not finished",
                     "done": "done", "missed": "missed or skipped"}.get(row["status"], row["status"])
            line = f"Today: {title or 'your lesson'}, {state}."
        days = days_to_exam(self.pack, self.today)
        out = [line, f"Streak: {streak(self.pack, self.store, self.today)} study day(s) in a row."]
        if days is not None:
            out.append(f"Exam in {days} days.")
        return "\n".join(out)

    def move(self, text: str) -> str:
        s = self.settings.get()
        row = self.store.lesson(self.today)
        if row is None or not self.pack.is_study_day(self.today):
            return "There's no lesson today to move."
        if row["status"] != "planned":
            return "Today's lesson has already started, finished or been skipped, so it can't be moved."
        hhmm = _parse_time(text.split(" ", 1)[1] if " " in text else "")
        if not hhmm:
            return "Send the new time like this: move 19:00 (or move 7pm)."
        if dt.datetime.combine(self.today, dt.time.fromisoformat(hhmm)) <= self.now:
            return f"{hhmm} has already passed. Pick a later time today."
        self.store.set_kv(f"time:{self.today}", hhmm)
        return f"Done. Today's lesson is now at {hhmm}. I'll remind you 15 minutes before."

    def skip(self) -> str:
        row = self.store.lesson(self.today)
        if row is None or not self.pack.is_study_day(self.today):
            return "There's no lesson today to skip."
        if row["status"] == "done":
            return "You've already finished today's lesson."
        if row["status"] == "missed":
            return "Today's lesson is already skipped."
        self.store.save_lesson(self.today, row["objectives"], "missed", row["summary"])
        self.store.mark_sent(self.today, "missed_logged")   # no 'missed' message on top of this reply
        self.store.log_event(self.now, "whatsapp", f"{self.today}: lesson skipped by reply")
        return "Skipped. Today's topics move to your next lesson, and your streak restarts. Back at it tomorrow."

    # --- quiz ---

    def _bank(self) -> list[tuple[str, dict]]:
        """(lesson day, question) for exam questions in lessons before today, practice lessons excluded."""
        out = []
        for f in sorted((self.data / "lessons").glob("????-??-??.md")):
            if f.stem >= str(self.today):
                continue
            les = Lesson.parse(f.read_text(encoding="utf-8"))
            if les.sample:
                continue
            out += [(f.stem, q) for q in les.quiz if q["type"] == "multiple_choice" and len(q["options"]) == 4]
        return out

    def quiz(self) -> str:
        bank = self._bank()
        if not bank:
            return "No questions yet: they come from lessons you've already had."
        last = json.loads(self.store.get_kv("wa_quiz_last") or "{}")
        choices = [b for b in bank if (b[0], b[1]["id"]) != (last.get("day"), last.get("id"))] or bank
        day, q = random.choice(choices)
        self.store.set_kv("wa_quiz", json.dumps({"day": day, "id": q["id"]}))
        self.store.set_kv("wa_quiz_last", json.dumps({"day": day, "id": q["id"]}))
        opts = "\n".join(f"{LETTERS[i]}) {o}" for i, o in enumerate(q["options"]))
        return f"{q['q']}\n{opts}\nReply A, B, C or D."

    def _answer(self, pending: dict, k: int) -> str:
        self.store.set_kv("wa_quiz", "")
        f = self.data / "lessons" / f"{pending['day']}.md"
        les = Lesson.parse(f.read_text(encoding="utf-8")) if f.exists() else None
        q = next((x for x in (les.quiz if les else []) if x["id"] == pending["id"]), None)
        if q is None:
            return "That question has gone. Send quiz for a new one."
        ok, _ = Q.mark(q, q["options"][k])
        self.store.add_evidence(q["objective"], self.today, Q.KIND[q["type"]], ok, note=q["options"][k][:200],
                                source="whatsapp", verdict="correct" if ok else "wrong",
                                event_key=f"wa:{self.today}:{pending['day']}:{pending['id']}")
        right = LETTERS[q["options"].index(q["answer"])] if q["answer"] in q["options"] else "?"
        head = "Right." if ok else f"Not quite. It's {right}) {q['answer']}."
        return f"{head} {q.get('why', '')}".strip() + "\nSend quiz for another."


# ---------- scheduled messages ----------

CHECKIN = {
    "gentle": {"done": "Lesson done today, nice work. {streak} Exam in {days} days.",
               "started": "You started today's lesson but didn't finish it. Finish it tomorrow if you can. {streak}",
               "none": "No lesson today. That's OK, tomorrow's a new one. Exam in {days} days."},
    "firm": {"done": "Lesson done. {streak} Exam in {days} days.",
             "started": "Today's lesson was started but not finished. Finish what you start. {streak}",
             "none": "No lesson today. Streak reset. Tomorrow, no excuses. Exam in {days} days."},
    "strict": {"done": "Done. {streak} {days} days to the exam.",
               "started": "Started, not finished. That doesn't count. {streak} {days} days to the exam.",
               "none": "Nothing done today. Streak is 0. {days} days to the exam."},
}


def checkin_text(pack, store, s: dict, today: dt.date) -> str | None:
    """The evening check-in for a study day, or None on rest days and pauses."""
    if s["paused"] or not pack.is_study_day(today):
        return None
    row = store.lesson(today)
    if row and row["status"] == "planned":
        return None   # the lesson (perhaps moved later) hasn't happened yet; the reminder ladder covers it
    key = "done" if row and row["status"] == "done" else ("started" if row and row["status"] == "started" else "none")
    n = streak(pack, store, today)
    words = CHECKIN.get(s["tone"], CHECKIN["firm"])[key]
    return words.format(streak=f"Streak: {n} study day(s) in a row.", days=days_to_exam(pack, today) or "?")


def weekly_text(pack, store, data_dir: Path, s: dict, today: dt.date, start: str | None) -> str:
    """The Sunday report: the week just gone, the weakest objectives, and next week's lessons."""
    monday = today - dt.timedelta(days=today.weekday())
    week = [monday + dt.timedelta(days=i) for i in range(7) if monday + dt.timedelta(days=i) <= today]
    study = [d for d in week if pack.is_study_day(d)]
    done = sum(1 for d in study if (store.lesson(d) or {}).get("status") == "done")
    answers = [e for d in week for e in store.evidence_on(d) if e.get("source") in ("exam", "whatsapp")]
    right = sum(1 for e in answers if e.get("correct"))
    iv = pack.config["review_intervals_days"]
    order = {"needs_reinforcement": 0, "introduced": 1, "practising": 2}
    weak = sorted((o for o in pack.objectives if status(store.evidence(o["id"]), today, iv) in order),
                  key=lambda o: order[status(store.evidence(o["id"]), today, iv)])[:3]
    lines = [f"Week to {today:%a %d %b}:",
             f"Lessons done: {done} of {len(study)} study day(s).",
             f"Exam questions: {right} of {len(answers)} right." if answers else "Exam questions: none answered this week.",
             f"Streak: {streak(pack, store, today)} study day(s) in a row."]
    if weak:
        lines.append("Weakest: " + "; ".join(f"{o['id']} {o['title']}" for o in weak) + ".")
    nxt = [r for r in preview(pack, data_dir, store, today + dt.timedelta(days=1), start,
                              until=today + dt.timedelta(days=8))]
    if nxt:
        lines.append("Next week: " + "; ".join(f"{d:%a} {title}" for d, _, title in nxt) + ".")
    days = days_to_exam(pack, today)
    if days is not None:
        lines.append(f"Exam in {days} days.")
    return "\n".join(lines)
