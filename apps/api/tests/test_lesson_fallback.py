"""The Markdown fallback has no plan to check, so its text is checked for labels and promised behaviour and any hit is logged."""
from tutor import lesson_plan as P


def test_fallback_label_and_promise_are_reported():
    md = "# Lesson\n\nPlain meaning: a template.\n\nHomework will be used for retrieval next lesson.\n"
    hits = P.text_problems(md)
    assert any(h.startswith("label:") for h in hits)
    assert any(h.startswith("promise:") for h in hits)


def test_clean_fallback_reports_nothing():
    md = "# Lesson\n\nA fuse is a safety part.\n\n```quiz\n[]\n```\n"
    assert P.text_problems(md) == []


def test_a_label_inside_a_say_block_is_reported_because_it_would_be_spoken():
    md = "```say\nPlain meaning: inside a say block\n```\n"
    assert any(h.startswith("label:") for h in P.text_problems(md))
