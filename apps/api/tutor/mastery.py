"""Evidence-based mastery: saying 'I understand' never counts; only graded evidence does."""
from __future__ import annotations
import datetime as dt

# higher = stronger evidence
WEIGHT = {"recognise": 1, "recall": 2, "apply_familiar": 3, "apply_new": 4, "delayed_recall": 4}


def status(evidence: list[tuple], today: dt.date, intervals=(1, 3, 7, 14, 30)) -> str:
    """evidence rows: (day_iso, kind, correct). Returns one of the handoff's statuses."""
    if not evidence:
        return "not_started"
    recent = evidence[-4:]
    wrong = sum(1 for _, _, c in recent if not c)
    strong = [e for e in evidence if e[2] and WEIGHT[e[1]] >= 3]
    delayed = [e for e in evidence if e[2] and e[1] == "delayed_recall"]
    if wrong >= 2:
        return "needs_reinforcement"
    if strong and delayed:
        last = dt.date.fromisoformat(evidence[-1][0])
        n = min(len(delayed), len(intervals) - 1)
        return "due_for_review" if (today - last).days >= intervals[n] else "demonstrated"
    if len(evidence) >= 2:
        return "practising"
    return "introduced"
