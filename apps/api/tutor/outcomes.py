"""End-of-lesson outcome: what this lesson showed, built from its evidence rows and its plan. Pure: no store, no model.
The raw transcript is never read here; it is for review, not for progress.

An objective is:
  demonstrated  every check and exam item on it was right
  weak          every one was wrong
  developing    a mix (or partial answers)
  not assessed  nothing on it was checked this lesson
"""
from __future__ import annotations
from .untrusted import data as fenced


def build(day, objectives: list[str], rows: list[dict], plan: dict | None) -> dict:
    """rows: Store.evidence_on(day). plan: the lesson's plan dict, or None for a lesson written before plans."""
    assessed = [r for r in rows if r["source"] in ("checkin", "exam") and r["objective"] in objectives]
    by: dict[str, list[dict]] = {o: [] for o in objectives}
    for r in assessed:
        by[r["objective"]].append(r)
    demonstrated, developing, weak, not_assessed = [], [], [], []
    for o in objectives:
        rs = by[o]
        if not rs:
            not_assessed.append(o)
        elif all(r["verdict"] == "correct" for r in rs):
            demonstrated.append(o)
        elif all(r["verdict"] == "wrong" for r in rs):
            weak.append(o)
        else:
            developing.append(o)
    misconceptions, seen = [], set()
    for r in assessed:
        key = (r["objective"], r["misconception"])
        if r["misconception"] and key not in seen:
            seen.add(key)
            misconceptions.append({"objective": r["objective"], "belief": r["misconception"]})
    exams = [r for r in rows if r["source"] == "exam"]
    homework = [{"objective": h.get("objective", ""), "task": h.get("task", "")}
                for h in (plan or {}).get("homework", []) if isinstance(h, dict) and h.get("task")]
    return {
        "lesson": str(day),
        "objectives": objectives,
        "demonstrated": demonstrated,
        "developing": developing,
        "weak": weak,
        "not_assessed": not_assessed,
        "misconceptions": misconceptions,
        "assessment": {"correct": sum(r["correct"] for r in exams), "total": len(exams)},
        "homework": homework,
        # the next lesson starts here: weak first, then developing
        "focus": weak + [o for o in developing if o not in weak],
    }


def next_lesson_notes(outcome: dict | None) -> str:
    """The lines the next lesson's plan is given. Empty when there is no earlier outcome."""
    if not outcome:
        return ""
    focus = ", ".join(outcome.get("focus") or []) or "none"
    miscs = "; ".join(f"{m['objective']}: {m['belief']}" for m in outcome.get("misconceptions") or []) or "none recorded"
    # The beliefs came from a model's plan, so they are fenced as data.
    return f"Last lesson focus (weak first): {focus}\n" + fenced("misconceptions seen last lesson", miscs)
