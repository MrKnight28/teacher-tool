"""Speech-to-text helpers: word error rate, and the Whisper initial prompt (key terms from today's lesson).

The benchmark that compares engines is in sttbench.py. The prompt is off by default. Turn it on in admin only if
sttbench shows it lowers the word error rate, and only for Whisper (Parakeet has no equivalent).
"""
from __future__ import annotations
import re
from .lesson import Lesson


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text.lower())


def wer(ref: str, hyp: str) -> float:
    """Word error rate: word-level edit distance divided by the number of words in the reference."""
    r, h = words(ref), words(hyp)
    if not r:
        return 0.0 if not h else 1.0
    d = list(range(len(h) + 1))
    for i, rw in enumerate(r, 1):
        prev, d[0] = d[0], i
        for j, hw in enumerate(h, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (rw != hw))
    return d[len(h)] / len(r)


def build_prompt(pack, lesson_md: str | None, rules) -> str:
    """Key terms (from the pronunciation list) and today's objective titles, within Whisper's prompt size."""
    ids = Lesson.parse(lesson_md or "").objectives
    titles = []
    for oid in ids:
        try:
            titles.append(pack.objective(oid)["title"])
        except (KeyError, TypeError):
            continue
    terms = [w for w, _ in rules]
    return ("Security+ SY0-701 exam study. Terms: " + ", ".join(terms) + ". Topics: " + "; ".join(titles))[:600]
