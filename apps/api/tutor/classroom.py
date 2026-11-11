"""Classroom helpers: validated notebook data. Lesson parsing (outline, stages) is in lesson.py."""
from __future__ import annotations
import re
import secrets

NOTE_ID = re.compile(r"^n-[A-Za-z0-9]{4,24}$")
MAX_NOTES, MAX_TITLE, MAX_BODY = 200, 120, 50_000


def validate_notes(items) -> list[dict]:
    """Check a whole notebook before it is saved. Raises ValueError with a plain message."""
    if not isinstance(items, list):
        raise ValueError("notes must be a list")
    if len(items) > MAX_NOTES:
        raise ValueError(f"too many notes (max {MAX_NOTES})")
    out, seen = [], set()
    for n in items:
        if not isinstance(n, dict):
            raise ValueError("each note must be an object")
        title, body = n.get("title", ""), n.get("body", "")
        if not isinstance(title, str) or not isinstance(body, str):
            raise ValueError("title and body must be text")
        if len(title) > MAX_TITLE:
            raise ValueError(f"title too long (max {MAX_TITLE} characters)")
        if len(body.encode("utf-8")) > MAX_BODY:
            raise ValueError("note too large (max 50 KB)")
        nid = n.get("id") if isinstance(n.get("id"), str) else ""
        if not NOTE_ID.match(nid) or nid in seen:
            nid = "n-" + secrets.token_hex(6)  # ids we did not issue are replaced
        seen.add(nid)
        out.append({"id": nid, "title": title, "body": body})
    return out
