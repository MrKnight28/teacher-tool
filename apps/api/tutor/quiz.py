"""Marking for the lesson quiz. The quiz is parsed by lesson.py. Answer keys stay server-side."""
from __future__ import annotations
import json
import re
from .lesson import quiz_items

KIND = {"multiple_choice": "recognise", "acronym_recall": "recall",
        "pbq_scenario": "apply_familiar", "free_text": "recall"}


def public_view(q: dict) -> dict:
    return {k: q[k] for k in ("id", "objective", "type", "q", "options")}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def _terms(s: str) -> set[str]:
    return {w for w in _norm(s).split() if len(w) > 3}


def _covers(key: str, answer: str) -> bool:
    """At least 80% of the key's words (4+ letters) are in the answer, and at least two of them when the key has two."""
    kt = _terms(key)
    hit = len(kt & _terms(answer))
    return bool(kt) and hit / len(kt) >= 0.8 and hit >= min(2, len(kt))


def mark(q: dict, answer: str, judge=None) -> tuple[bool, str]:
    """judge(question, key, answer)->bool|None is an optional LLM marker for free text."""
    a, key = _norm(answer), _norm(str(q["answer"]))
    t = q["type"]
    if t in ("multiple_choice", "acronym_recall"):
        ok = a == key or (q["options"] and a[:1] == key[:1] and len(a) == 1 and key[:1] in "abcdef")
        if t == "acronym_recall":
            # The whole expansion, alone or inside a longer answer, or nearly all of its words. A fragment of the answer
            # (any 4 letters of "Mandatory Access Control") used to pass.
            ok = bool(ok) or bool(key and key in a) or _covers(key, a)
    else:
        verdict = judge(q["q"], q["answer"], answer) if judge else None
        if verdict is None:
            kt = _terms(q["answer"])
            ok = bool(kt) and len(kt & _terms(answer)) / len(kt) >= 0.6
        else:
            ok = verdict
    return bool(ok), ("Correct. " if ok else f"Not quite. Answer: {q['answer']}. ") + q["why"]


def problem(text: str, objective_ids: set[str]) -> str | None:
    """Why a lesson's quiz can't be used, or None if it is usable (3+ valid items on real objectives)."""
    items = quiz_items(text)
    if len(items) < 3:
        return f"found {len(items)} valid quiz items, need at least 3"
    bad = sorted({q["objective"] for q in items if q["objective"] not in objective_ids})
    return f"unknown objective ids {', '.join(bad)}" if bad else None


def backup_quiz(titles: dict[str, str], n: int = 3) -> str:
    """Recall questions on weak objectives, as a quiz block. Used only when the model's quiz stays invalid."""
    items = [{"id": i, "objective": oid, "type": "free_text", "q": f"In your own words, explain: {title}.",
              "options": [], "answer": title, "why": "Backup question on an objective you need to revisit."}
             for i, (oid, title) in enumerate(list(titles.items())[:n])]
    return "```quiz\n" + json.dumps(items, indent=1) + "\n```"
