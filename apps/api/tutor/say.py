"""Teacher scripts: what the spoken lesson says and which lines the browser may see. Parsing is in lesson.py.

Expect lines are server-side only, like quiz answer keys: they are never sent to the browser or spoken.
"""
from __future__ import annotations
import re
from .lesson import SAY

NAME = re.compile(r"^\s*Name:\s*(.+?)\s*$", re.M | re.I)


def public(items: list[dict], answers: list[str]) -> list[dict]:
    """Lines safe to send to the browser: no expect lines, and no line that gives away a quiz answer."""
    keys = [a.strip().lower() for a in answers if a and len(a.strip()) >= 4]
    out = []
    for it in items:
        low = it["text"].lower()
        if any(k in low for k in keys):
            continue
        out.append({"text": it["text"], "question": it["question"]})
    return out


def student_name(context: str) -> str:
    """The first name from a "Name:" line in context.md, or "" if none is set. Letters only, at most 30."""
    m = NAME.search(context or "")
    if not m:
        return ""
    name = re.sub(r"[^A-Za-z' -]", "", m.group(1)).strip()[:30]
    return name


def limit_name(markdown: str, name: str) -> str:
    """Keep the student's name on the first spoken line of each script and on check-in questions; drop it elsewhere.
    The model tends to say the name in nearly every line, and the brief asks for about once per slide."""
    if not name:
        return markdown
    pat = re.escape(name)

    def fix(m):
        out, used = [], False
        for ln in m.group(1).split("\n"):
            if re.search(rf"\b{pat}\b", ln):
                if ln.lstrip().startswith("? ") or not used:
                    used = True
                    out.append(ln)
                    continue
                ln = re.sub(rf"^(\s*){pat},\s*", r"\1", ln)
                ln = re.sub(rf"\b{pat}\b", "you", ln)
            out.append(ln)
        return "```say\n" + "\n".join(out) + "```"

    return SAY.sub(fix, markdown)
