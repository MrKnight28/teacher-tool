"""Pick tomorrow's objectives: missed work first, then weak, then the misconceptions the last lesson found, then due review,
then new by exam weight."""
from __future__ import annotations
import datetime as dt
from .mastery import status
from .pack import Pack
from .store import Store


def plan_objectives(pack: Pack, store: Store, day: dt.date, count: int = 2) -> list[str]:
    st = {o["id"]: status(store.evidence(o["id"]), day, pack.config["review_intervals_days"]) for o in pack.objectives}
    last = store.last_outcome(day) or {}
    chosen: list[str] = []

    def take(ids):
        for i in ids:
            if i not in chosen and len(chosen) < count:
                chosen.append(i)

    take([i for i in store.missed_objectives(day)])
    take([i for i, s in st.items() if s == "needs_reinforcement"])
    # Objectives where the last lesson's check-ins or exam items showed a belief the marker identified.
    take([m["objective"] for m in last.get("misconceptions") or [] if m.get("objective") in st])
    take([i for i, s in st.items() if s == "due_for_review"])
    new = [i for i, s in st.items() if s in ("not_started", "introduced")]
    # highest exam weight first, keep curriculum order within a domain
    new.sort(key=lambda i: -pack.domain_weight(i))
    take(new)
    take([i for i, s in st.items() if s == "practising"])
    return chosen
