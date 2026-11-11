"""The spoken-versus-slide contract for structured lesson plans: what the teacher says is not what the slide shows,
punctuation joins never double, stage names are explicit, labels and unsupported promises are refused, and exam
questions are not repeated or given away by the teaching."""
import copy
import re

import pytest
from tutor import lesson as L
from tutor import lesson_plan as P
from tests.test_lesson_plan import good_plan

STAGES = {"retrieval": 5, "intro": 5, "teaching": 15, "guided_practice": 10, "independent_practice": 15, "qa": 5, "review": 5}
IDS = ["4.1", "4.2"]


def plan():
    return copy.deepcopy(good_plan(IDS))


def check(p):
    return P.problem(p, IDS, list(STAGES))


def spoken_lines(md: str) -> list[str]:
    out = []
    for block in re.findall(r"```say\n(.*?)```", md, re.S):
        out += [ln for ln in block.splitlines() if ln.strip()]
    return out


# 1. slide content and spoken content are separate

def test_slide_bullets_are_not_the_spoken_script():
    md = P.render(plan(), STAGES)
    slide = [ln for ln in md.splitlines() if ln.startswith("- ")]
    say = spoken_lines(md)
    assert slide, "the slide should still carry its bullets"
    for bullet in slide:
        text = bullet[2:]
        assert text not in say, f"bullet read back verbatim: {text!r}"


def test_spoken_explanation_is_what_is_said_and_it_is_in_the_say_block():
    p = plan()
    md = P.render(p, STAGES)
    for line in p["sections"][0]["say"]:
        assert P.sentence(line) in spoken_lines(md)


def test_a_spoken_line_that_repeats_a_bullet_is_refused():
    p = plan()
    p["sections"][0]["say"] = [p["sections"][0]["content"][0] + " That is all."]
    assert "repeats a slide bullet" in check(p)


def test_a_check_question_that_reads_a_slide_bullet_back_is_refused():
    p = plan()
    p["sections"][0]["checks"][0]["question"] = p["sections"][0]["content"][0]
    assert "repeats a slide bullet" in check(p)


def test_a_misconception_that_reads_a_slide_bullet_back_is_refused():
    p = plan()
    p["sections"][0]["misconceptions"][0]["belief"] = p["sections"][0]["examples"][0]
    assert "repeats a slide bullet" in check(p)


def test_say_is_required_for_every_section():
    p = plan()
    del p["sections"][0]["say"]
    assert "needs 1 to 4 spoken explanation lines" in check(p)


def test_analogy_is_optional_and_empty_is_refused():
    p = plan()
    assert check(p) is None
    p["sections"][0]["analogy"] = "  "
    assert "analogy is empty" in check(p)
    p["sections"][0]["analogy"] = "A relay wired into a panel still carries current."
    md = P.render(p, STAGES)
    assert "A relay wired into a panel still carries current." in spoken_lines(md)


# 2. punctuation joining

@pytest.mark.parametrize("belief, correction", [
    ("Once a baseline is deployed, the system stays secure.", "Systems drift."),
    ("Is a firewall enough?", "No, it is one layer."),
    ("Anything connected is safe!", "Not true."),
    ("Defaults are safe", "They are not."),
])
def test_misconception_joins_never_double_or_mix_punctuation(belief, correction):
    p = plan()
    p["sections"][0]["misconceptions"] = [{"belief": belief, "correction": correction}]
    md = P.render(p, STAGES)
    for text in [ln for ln in md.splitlines() if "believe this" in ln or "Common mix-up" in ln]:
        assert ".." not in text and "?." not in text and "!." not in text
    spoken = [ln for ln in spoken_lines(md) if ln.startswith(P.MIXUP_OPEN) and P.MIXUP_TURN in ln and belief.rstrip(".?!") in ln]
    assert len(spoken) == 1 and "  " not in spoken[0]


def test_sentence_helper_ends_with_exactly_one_mark():
    assert P.sentence("Done.") == "Done."
    assert P.sentence("Really?") == "Really?"
    assert P.sentence("Wow!") == "Wow!"
    assert P.sentence("No mark") == "No mark."
    assert P.sentence("  spaced   out  ") == "spaced out."


def test_no_double_full_stop_anywhere_in_a_rendered_lesson():
    p = plan()
    p["sections"][0]["misconceptions"] = [{"belief": "Defaults are safe.", "correction": "They are not."}]
    md = P.render(p, STAGES)
    assert ".." not in md


# 3. examples are not lowercased and do not read "For example, A"

def test_examples_are_spoken_without_a_broken_lead_in():
    p = plan()
    p["sections"][0]["examples"] = ["A company finds an unknown server on the network."]
    md = P.render(p, STAGES)
    assert "For example, A company" not in md
    assert "Example: A company finds an unknown server" in md  # the slide keeps the example as written


# 4. stage names

def test_known_stages_have_explicit_display_names():
    for key in STAGES:
        p = plan()
        p["sections"][0]["stage"] = key
        md = P.render(p, STAGES)
        assert f"## {P.STAGE_NAMES[key]} ({STAGES[key]} min)" in md, key
    assert P.STAGE_NAMES["qa"] == "Q&A"
    assert "Qa " not in P.render(plan(), STAGES)


def test_unknown_stage_key_falls_back_to_capitalised_words():
    p = plan()
    p["sections"][0]["stage"] = "wrap_up"
    md = P.render(p, {**STAGES, "wrap_up": 5})
    assert "## Wrap up (5 min)" in md


def test_stage_names_cover_every_stage_the_pack_uses():
    pack_stages = ["retrieval", "intro", "teaching", "guided_practice", "independent_practice", "qa", "review"]
    assert set(pack_stages) <= set(P.STAGE_NAMES)


# 5. labels are not spoken

def test_a_label_inside_teaching_text_is_refused():
    p = plan()
    p["sections"][0]["content"][0] = "Plain meaning: a template that every system starts from."
    assert "presentation label" in check(p)
    p = plan()
    p["sections"][0]["say"][0] = "Analogy: a board design that every unit is built to."
    assert "presentation label" in check(p)


def test_rendered_speech_contains_no_labels():
    md = P.render(plan(), STAGES)
    for line in spoken_lines(md):
        assert not P.LABEL.search(line)


# 6. no promised behaviour the application lacks

@pytest.mark.parametrize("text", [
    "Homework will be used for retrieval next lesson.",
    "Your homework is marked automatically.",
    "We will ask you about this next lesson.",
    "This will be tested later in the course.",
])
def test_promises_the_lesson_cannot_keep_are_refused(text):
    p = plan()
    p["sections"][0]["content"][0] = text
    assert "promises behaviour the lesson does not have" in check(p)


def test_homework_is_stored_in_the_plan_not_promised_in_the_lesson():
    p = plan()
    assert check(p) is None
    md = P.render(p, STAGES)
    assert "homework" not in md.lower()


# 7. exam questions do not repeat or leak through teaching

def test_exam_question_repeating_a_teaching_check_is_refused():
    p = plan()
    p["sections"][0]["checks"][0]["question"] = "A company allows personal phones and wants to erase only company data after a loss?"
    p["exam_questions"][0]["q"] = "A company allows personal phones and wants to erase only company data after a loss?"
    assert "repeats the wording of a teaching item" in check(p)


def test_exam_answer_given_away_in_teaching_is_refused():
    p = plan()
    p["exam_questions"][0]["options"] = ["Deploy from a hardened baseline image", "Alpha", "Beta", "Gamma"]
    p["exam_questions"][0]["answer"] = "Deploy from a hardened baseline image"
    p["sections"][0]["say"][0] = "Remember, you deploy from a hardened baseline image for consistency."
    assert "answer is given away" in check(p)


def test_same_objective_in_teaching_and_exam_is_allowed():
    p = plan()
    p["exam_questions"][0]["q"] = "Which control is best for a fleet of unmanaged laptops in a scenario nobody owns?"
    assert check(p) is None


# 8. acronyms are not crammed into one spoken sentence

def test_more_than_three_acronyms_in_one_spoken_line_is_refused():
    p = plan()
    p["sections"][0]["say"] = ["ICS, SCADA, RTOS and IoT all need hardening, and WPA3 and MDM help with that."]
    assert "more than 3 acronyms" in check(p)


def test_a_few_acronyms_with_an_explanation_are_fine():
    p = plan()
    p["sections"][0]["say"] = ["Mobile device management (MDM) lets an organisation enforce policy on phones."]
    assert check(p) is None


# 9. the existing contract still holds

def test_exam_questions_still_have_exactly_four_protected_options():
    p = plan()
    p["exam_questions"][0]["options"] = ["A", "B", "C"]
    assert "exactly 4 different options" in check(p)
    p = plan()
    p["exam_questions"][0]["answer"] = "B"
    assert "answer must be exactly one of the options" in check(p)


def test_exam_answers_never_reach_the_spoken_script_or_the_slides():
    md = P.render(plan(), STAGES)
    lesson = L.Lesson.parse(md, STAGES)
    assert lesson.quiz and all(q["source"] == "exam" for q in lesson.quiz)
    text = "\n".join(spoken_lines(md)) + L.student_text(md)
    for q in lesson.quiz:
        assert q["q"] not in text
