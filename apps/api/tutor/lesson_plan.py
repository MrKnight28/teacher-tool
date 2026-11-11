"""Structured lesson plan: the model writes a plan as JSON, this module checks it, and render() turns it into the
lesson Markdown that the classroom, quiz and speech already read. Nothing here calls a model or sends text anywhere.

Each teaching section has two kinds of text, and they stay apart:
  content, examples, misconceptions  -> what the student SEES on the slide
  say, analogy                        -> what the teacher SAYS (an explanation in the teacher's own words, not a readout)
Other parts:
  checks                  -> teaching checks: '? ' lines in the say block, answered with the expect line
  application             -> a 'Scenario' slide (the scenario is on screen) and a spoken check about it
  retrieval               -> a 'Retrieval' slide at the start (earlier material, asked aloud)
  exam_questions          -> the quiz block, marked "source": "exam" (Security+ A-D items). Never spoken, never on a slide
  homework                -> kept in data/lessons/<day>.plan.json for the homework build; not shown yet
"""
from __future__ import annotations
import json
import re

from . import outcomes as O
from .mastery import status

FENCE = re.compile(r"```json\s*\n(.*?)```", re.S | re.I)
OPTIONS = 4  # exam questions have exactly four options, A to D
# Display names for the stages a lesson can have (pack.yaml). A key not listed here is shown with its words capitalised.
STAGE_NAMES = {"retrieval": "Retrieval", "intro": "Intro", "teaching": "Teaching", "guided_practice": "Guided practice",
               "independent_practice": "Independent practice", "qa": "Q&A", "review": "Review"}
# Presentation labels must not be spoken or written as text inside teaching content.
LABEL = re.compile(r"^\s*(plain meaning|analogy|common mix-up|example|scenario|note|summary|misconception)\s*:", re.I)
# Things the application does not do yet. Homework is stored, not used for retrieval.
UNSUPPORTED = re.compile(r"homework|next lesson|next session|retrieval (next|later)|will be (used|asked|tested) (next|later)", re.I)
ACRONYM = re.compile(r"\b(?:[A-Z]{2,}[A-Z0-9]*(?:/[A-Z0-9]+)*|\d+\.\d+[A-Z])\b")
MAX_ACRONYMS = 3          # per spoken line: more than this is cramming
# A misconception is spoken as a mistake, flagged before and after, so the wrong belief never sounds like teaching.
MIXUP_OPEN, MIXUP_TURN = "Here is a common mistake.", "That is not right."
MAX_SAY_WORDS = 60        # one spoken line should sound natural in one breath
STOP = {"which", "what", "that", "with", "from", "this", "their", "there", "about", "would", "should", "first", "after",
        "before", "when", "while", "where", "does", "have", "been", "will", "your", "they", "them", "into", "than", "only",
        "most", "each", "every", "some", "these", "those", "other", "best", "primary", "during", "company", "security"}


def parse_plan(reply: str) -> dict | None:
    """The plan object from a model reply: the first ```json block that holds one, else the whole reply."""
    chunks = [m.group(1) for m in FENCE.finditer(reply or "")] or [reply or ""]
    for raw in chunks:
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end <= start:
            continue
        try:
            plan = json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            continue
        if isinstance(plan, dict):
            return plan
    return None


def evidence_context(pack, store, day) -> str:
    """Graded progress for the model: weak objectives first, then the other statuses. Saying 'I understand' is not evidence."""
    rows, weak = [], []
    for o in pack.objectives:
        st = status(store.evidence(o["id"]), day, pack.config["review_intervals_days"])
        if st == "not_started":
            continue
        rows.append(f"{o['id']} {st}")
        if st == "needs_reinforcement":
            weak.append(o["id"])
    text = ("Graded progress: " + ("; ".join(rows) if rows else "none yet") + "\n"
            "Weak objectives to revisit (use retrieval and checks on these): " + (", ".join(weak) or "none"))
    # The last lesson's structured outcome: its focus and the misconceptions it found.
    notes = O.next_lesson_notes(store.last_outcome(day))
    return text + ("\n" + notes if notes else "")


def sentence(s) -> str:
    """Text that ends with exactly one terminal mark. Joining two sentences with this never doubles a full stop."""
    t = _clean(s)
    return t if t[-1:] in (".", "!", "?") else t + "."


def problem(plan, ids: list[str], stages: list[str]) -> str | None:
    """Why a plan can't be rendered, or None if it is usable. ids: this lesson's objectives. stages: the pack's stage keys."""
    if not isinstance(plan, dict):
        return "the reply has no JSON object"
    lesson_ids = set(ids)
    if not _text(plan.get("title")):
        return "missing title"
    sections = plan.get("sections")
    if not isinstance(sections, list) or not sections:
        return "missing sections"
    taught: set[str] = set()
    visible: list[str] = []      # everything a student or teacher reads as teaching (not the exam)
    for n, s in enumerate(sections, 1):
        where = f"section {n}"
        if not isinstance(s, dict):
            return f"{where} is not an object"
        if s.get("stage") not in stages:
            return f"{where}: unknown stage {s.get('stage')!r}"
        if not _text(s.get("title")):
            return f"{where}: missing title"
        if not _strings(s.get("content")):
            return f"{where}: needs content points"
        if not _strings(s.get("examples")):
            return f"{where}: needs at least one example"
        if not _strings(s.get("say")) or not 1 <= len(s["say"]) <= 4:
            return f"{where}: needs 1 to 4 spoken explanation lines in say"
        shown = list(s["content"]) + list(s["examples"])
        for line in s["say"]:
            if len(line.split()) > MAX_SAY_WORDS:
                return f"{where}: a spoken line is longer than {MAX_SAY_WORDS} words"
            if len(ACRONYM.findall(line)) > MAX_ACRONYMS:
                return f"{where}: a spoken line has more than {MAX_ACRONYMS} acronyms; spread them out and explain one"
            if any(len(_norm(x)) >= 20 and _norm(x) in _norm(line) for x in shown):
                return f"{where}: spoken text repeats a slide bullet; explain it in the teacher's own words"
        checks = s.get("checks")
        if not isinstance(checks, list) or not 1 <= len(checks) <= 2:
            return f"{where}: needs 1 or 2 checks"
        for c in checks:
            bad = _ref(c, ("question", "expect", "objective"), lesson_ids, where + " check")
            if bad:
                return bad
        objs = s.get("objectives")
        if not _strings(objs) or any(o not in lesson_ids for o in objs):
            return f"{where}: objectives must be a non-empty list from this lesson"
        taught.update(objs)
        for m in s.get("misconceptions") or []:
            if not isinstance(m, dict) or not _text(m.get("belief")) or not _text(m.get("correction")):
                return f"{where}: misconceptions need belief and correction"
            visible += [m["belief"], m["correction"]]
        app = s.get("application")
        if app is not None:
            bad = _ref(app, ("scenario", "question", "expect", "objective"), lesson_ids, where + " application")
            if bad:
                return bad
            visible += [app["scenario"], app["question"]]
        visible += shown + list(s["say"]) + [c["question"] for c in checks]
        if s.get("analogy") is not None and not _text(s.get("analogy")):
            return f"{where}: analogy is empty; leave it out instead"
        visible += [s["analogy"]] if s.get("analogy") else []
    # Every spoken field of a section (say, checks, analogy, misconceptions) must not read a slide bullet back.
    for n, s in enumerate(sections, 1):
        shown = [_norm(x) for x in list(s["content"]) + list(s["examples"]) if len(_norm(x)) >= 20]
        spoken = list(s["say"]) + [c["question"] for c in s["checks"]]
        spoken += [s["analogy"]] if s.get("analogy") else []
        for m in s.get("misconceptions") or []:
            spoken += [m["belief"], m["correction"]]
        if any(x in _norm(line) for line in spoken for x in shown):
            return f"section {n}: a spoken line repeats a slide bullet; explain it in the teacher's own words"
    retrieval = plan.get("retrieval")
    if not isinstance(retrieval, list) or not 1 <= len(retrieval) <= 3:
        return "retrieval needs 1 to 3 questions"
    for r in retrieval:
        bad = _ref(r, ("question", "expect", "objective"), lesson_ids, "retrieval")
        if bad:
            return bad
        visible.append(r["question"])
    exams = plan.get("exam_questions")
    if not isinstance(exams, list) or len(exams) < 3:
        return "exam_questions needs at least 3 items"
    for n, q in enumerate(exams, 1):
        bad = _ref(q, ("q", "answer", "why", "objective"), lesson_ids, f"exam question {n}")
        if bad:
            return bad
        opts = q.get("options")
        if not _strings(opts) or len(opts) != OPTIONS or len(set(opts)) != OPTIONS:
            return f"exam question {n}: needs exactly {OPTIONS} different options"
        if q["answer"] not in opts:
            return f"exam question {n}: answer must be exactly one of the options"
        bad = _exam_leak(n, q, visible)
        if bad:
            return bad
    missing_exam = lesson_ids - {q["objective"] for q in exams}
    if missing_exam:
        return "no exam question for objective " + ", ".join(sorted(missing_exam))
    missing = lesson_ids - taught
    if missing:
        return "no teaching section for objective " + ", ".join(sorted(missing))
    for h in plan.get("homework") or []:
        bad = _ref(h, ("task", "objective"), lesson_ids, "homework")
        if bad:
            return bad
    for where, text in _all_text(plan):
        if LABEL.search(text):
            return f"{where}: a presentation label ('{text.split(':')[0]}:') is in the text; leave labels out"
        if UNSUPPORTED.search(text):
            return f"{where}: promises behaviour the lesson does not have ({UNSUPPORTED.search(text).group(0)})"
    return None


def text_problems(markdown: str) -> list[str]:
    """Label and unsupported-promise hits in a Markdown lesson. Used for the fallback lesson, which has no structure to check."""
    out = []
    for ln in markdown.splitlines():
        if ln.startswith("```") or ln.startswith("<!--"):
            continue
        if LABEL.search(ln):
            out.append(f"label: {ln[:80]}")
        if UNSUPPORTED.search(ln):
            out.append(f"promise: {ln[:80]}")
    return out


def render(plan: dict, stages: dict[str, int]) -> str:
    """The lesson Markdown (without the objectives line). Stages are the pack's {key: minutes}, in order."""
    lines = [f"# {_clean(plan['title'])}", ""]
    by_stage: dict[str, list[str]] = {k: [] for k in stages}
    for s in plan["sections"]:
        by_stage[s["stage"]].append(_section(s))
    if plan.get("retrieval") and "retrieval" in by_stage:
        by_stage["retrieval"].insert(0, _retrieval(plan["retrieval"]))
    for key, minutes in stages.items():
        if not by_stage[key]:
            continue
        lines += [f"## {STAGE_NAMES.get(key, key.replace('_', ' ').capitalize())} ({minutes} min)", ""]
        for slide in by_stage[key]:
            lines += [slide, ""]
    items = [{"objective": q["objective"], "type": "multiple_choice", "q": _clean(q["q"]),
              "options": [_clean(o) for o in q["options"]], "answer": _clean(q["answer"]),
              "why": _clean(q["why"]), "source": "exam"} for q in plan["exam_questions"]]
    lines += ["```quiz", json.dumps(items, indent=1, ensure_ascii=False), "```", ""]
    return "\n".join(lines)


def _section(s: dict) -> str:
    # The slide: visual support. Bullets, examples and mix-ups as written.
    slide = [f"- {_clean(c)}" for c in s["content"]]
    slide += [f"Example: {_clean(e)}" for e in s["examples"]]
    slide += [f"Common mix-up: {sentence(m['belief'])} {sentence(m['correction'])}" for m in s.get("misconceptions") or []]
    # The teacher's voice: explanation in the teacher's words, then the analogy if there is a good one, then the mix-ups.
    say = [sentence(x) for x in s["say"]]
    if s.get("analogy"):
        say.append(sentence(s["analogy"]))
    say += [f"{MIXUP_OPEN} {sentence(m['belief'])} {MIXUP_TURN} {sentence(m['correction'])}"
            for m in s.get("misconceptions") or []]
    say += _checks(s["checks"])
    out = [f"### {_clean(s['title'])}", *slide, "", "```say", *say, "```"]
    if s.get("application"):
        app = s["application"]
        out += ["", f"### Scenario: {_clean(s['title'])}", _clean(app["scenario"]), "",
                "```say", "Look at the scenario on the screen.", *_checks([app]), "```"]
    return "\n".join(out)


def _retrieval(items: list[dict]) -> str:
    return "\n".join(["### Retrieval", "Quick check on earlier material.", "", "```say", *_checks(items), "```"])


def _checks(items: list[dict]) -> list[str]:
    out = []
    for c in items:
        out += [f"? {_clean(c['question'])}", f"expect: {_clean(c['expect'])}"]
    return out


def _clean(s) -> str:
    """One line, no code fences: the strings sit inside Markdown and JSON in the lesson file."""
    return " ".join(str(s).replace("```", "'''").split())


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9 ]", "", _clean(s).lower())


def _words(s) -> set[str]:
    return {w for w in _norm(s).split() if len(w) > 3 and w not in STOP}


def _exam_leak(n: int, q: dict, visible: list[str]) -> str | None:
    """An exam question must not be the teaching again: no near-copy of its wording, and its answer must not be given away."""
    qw, aw = _words(q["q"]), _words(q["answer"])
    answer = _norm(q["answer"])
    for t in visible:
        tw = _words(t)
        if qw and len(qw & tw) / len(qw) >= 0.5:
            return f"exam question {n} repeats the wording of a teaching item; write an independent scenario"
        if len(aw) >= 3 and len(aw & tw) / len(aw) >= 0.8:
            return f"exam question {n}: its answer is given away in teaching text"
        if len(answer) >= 12 and answer in _norm(t):
            return f"exam question {n}: its answer is given away in teaching text"
    return None


def _all_text(plan: dict):
    """(where, text) for every string a student or teacher reads, for the label and promise checks."""
    for n, s in enumerate(plan.get("sections") or [], 1):
        if not isinstance(s, dict):
            continue
        where = f"section {n}"
        for key in ("content", "examples", "say"):
            for t in s.get(key) or []:
                if isinstance(t, str):
                    yield where, t
        if isinstance(s.get("analogy"), str):
            yield where, s["analogy"]
        for m in s.get("misconceptions") or []:
            if isinstance(m, dict):
                yield where, f"{m.get('belief', '')} {m.get('correction', '')}"
        for c in s.get("checks") or []:
            if isinstance(c, dict):
                yield where, c.get("question", "")
    for r in plan.get("retrieval") or []:
        if isinstance(r, dict):
            yield "retrieval", r.get("question", "")


def _text(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _strings(v) -> bool:
    return isinstance(v, list) and bool(v) and all(_text(x) for x in v)


def _ref(item, keys: tuple, lesson_ids: set[str], where: str) -> str | None:
    if not isinstance(item, dict):
        return f"{where} is not an object"
    for k in keys:
        if not _text(item.get(k)):
            return f"{where}: missing {k}"
    if item["objective"] not in lesson_ids:
        return f"{where}: objective {item['objective']!r} is not in this lesson"
    return None
