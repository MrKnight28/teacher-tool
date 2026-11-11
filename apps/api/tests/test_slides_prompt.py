from tutor import lesson_writer


def test_prompt_asks_for_slide_structure_and_diagrams():
    p = lesson_writer.PROMPT
    assert '"## "' in p and '"### "' in p
    assert "```svg" in p
    assert "no script" in p
    assert "analogy" in p


def test_prompt_formats_without_stray_braces():
    # The quiz example uses doubled braces; the new text must not add single ones.
    out = lesson_writer.PROMPT.format(minutes=60, day="2026-10-05", objectives="- 4.1: x",
                                      last="none", stages="Retrieval 5 min")
    assert "{" in out and "analogy" in out
