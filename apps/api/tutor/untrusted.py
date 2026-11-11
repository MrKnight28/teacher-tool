"""Untrusted text inside a prompt.

The student's answers, chat messages and summaries, the study materials, and lesson text written by a model are all data. Prompts
put them between <data name="..."> tags and tell the model never to follow instructions inside. That only holds if the text
cannot close the tag itself, so every piece of untrusted text goes through neutralise() before it is placed in a prompt.
"""
from __future__ import annotations
import re

_FENCE = re.compile(r"<(\s*/?\s*data\b)", re.I)


def neutralise(text) -> str:
    """Text that cannot open or close a <data> block: the '<' of '<data' and '</data' becomes a look-alike '‹'."""
    return _FENCE.sub(lambda m: "‹" + m.group(1), str(text if text is not None else ""))


def data(name: str, text) -> str:
    """One fenced data block."""
    return f'<data name="{neutralise(name)}">\n{neutralise(text)}\n</data>'
