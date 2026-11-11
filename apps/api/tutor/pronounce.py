"""Spoken forms for terms, applied before text-to-speech. The screen keeps the written form.

The rules live in the course pack (packs/<pack>/pronounce.yaml). The browser copy in ui.html (applyPronounce) must
match this exactly; a test checks both on the same text.
"""
from __future__ import annotations
import re
from pathlib import Path

import yaml


def load(path) -> list[tuple[str, str]]:
    """The rules, longest written form first. A missing or broken file gives no rules (speech still works)."""
    try:
        data = yaml.safe_load(Path(path).read_text()) or {}
        rules = [(str(r["written"]), str(r["say"])) for r in data.get("rules", [])]
    except (OSError, yaml.YAMLError, KeyError, TypeError):
        return []
    return sorted(rules, key=lambda r: -len(r[0]))


def apply(text: str, rules) -> str:
    for written, say in rules:
        text = re.sub(r"(?<!\w)" + re.escape(written) + r"(?!\w)", lambda m, s=say: s, text)
    return text
