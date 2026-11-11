"""The one parser for lesson markdown. Everything that reads a lesson file goes through Lesson.parse().

A lesson file has an optional `<!-- objectives: 1.1,2.3 -->` line, a `# ` title, `## ` stages, `### ` concept slides,
a ```say block after each slide (the teacher script), and a quiz block (```quiz or a ```json list) with answer keys.
The answer keys and the expect lines are server-side only. Nothing in this module sends text anywhere.
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass

QUIZ = re.compile(r"```(?:json)?\s*quiz?\s*\n(.*?)```|```json\s*\n(\s*\[.*?\])\s*```", re.S | re.I)
SAY = re.compile(r"```say[ \t]*\n(.*?)```", re.S | re.I)
OBJECTIVES = re.compile(r"objectives:\s*([\d.,\s]+)")
MIN_RE = re.compile(r"\(\s*(\d+)\s*min", re.I)
QUIZ_TYPES = ("multiple_choice", "pbq_scenario", "acronym_recall", "free_text")
DEFAULT_MINUTES = 5
SAMPLE_MARK = "<!-- sample"


@dataclass
class Lesson:
    text: str                       # the file as written (never sent to the browser)
    body: str                       # what the student may see: no quiz blocks, no say blocks
    title: str
    stages: list[dict]              # {"name", "minutes"} from the '## ' headings
    slides: list[dict]              # {"title", "body": [lines]} in the page's order
    scripts: dict[int, list[dict]]  # slide index -> script lines, expect lines included
    quiz: list[dict]                # questions with answer keys
    objectives: list[str]           # ids from the objectives line, in order
    sample: bool                    # a practice lesson: answers and summaries are not recorded

    @classmethod
    def parse(cls, text: str, stage_minutes: dict[str, int] | None = None) -> "Lesson":
        body = student_text(text)
        title, stages = outline(body, stage_minutes or {})
        m = OBJECTIVES.search(text)
        ids = [i.strip() for i in m.group(1).split(",") if i.strip()] if m else []
        return cls(text=text, body=body, title=title, stages=stages, slides=slides(text), scripts=scripts(text),
                   quiz=quiz_items(text), objectives=ids, sample=is_sample(text))


def is_sample(text: str) -> bool:
    """A practice lesson (from `python3 -m tutor sample-lesson`): answers and summaries aren't recorded."""
    return SAMPLE_MARK in text[:400]


def quiz_items(text: str) -> list[dict]:
    """The first quiz block that parses, with each item checked. Items with a missing field are dropped."""
    for m in QUIZ.finditer(text):
        raw = m.group(1) or m.group(2)
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            continue
        out = []
        for i, q in enumerate(items):
            if not all(k in q for k in ("objective", "q", "answer")):
                continue
            if q.get("type") not in QUIZ_TYPES:
                q["type"] = "multiple_choice" if q.get("options") else "free_text"
            q["options"] = [str(o) for o in q.get("options") or []]
            q["answer"] = str(q["answer"])
            q.setdefault("why", "")
            q["id"] = i
            out.append(q)
        if out:
            return out
    return []


def student_text(text: str) -> str:
    """The lesson without quiz blocks (answer keys) and say blocks (scripts): what the student reads."""
    return SAY.sub("", QUIZ.sub("", text))


def say_items(block: str) -> list[dict]:
    """One say block: a line per spoken line. A '? ' line is a check-in question; an 'expect:' line after it is the key idea."""
    items = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.lower().startswith("expect:"):
            if items and items[-1]["question"]:
                items[-1]["expect"] = line[len("expect:"):].strip()
            continue
        if line.startswith("? "):
            items.append({"text": line[2:].strip(), "question": True, "expect": ""})
        else:
            items.append({"text": line, "question": False, "expect": ""})
    return [i for i in items if i["text"]]


def slides(markdown: str) -> list[dict]:
    """Slides in the page's order: a '## ' stage heading is a slide, and so is each '### ' concept."""
    out = []
    for line in markdown.split("\n"):
        if line.startswith("<!--"):
            continue
        if line.startswith("## ") or line.startswith("### "):
            out.append({"title": line.split(" ", 1)[1].strip(), "body": []})
        elif out:
            out[-1]["body"].append(line)
    return out


def scripts(markdown: str) -> dict[int, list[dict]]:
    """Slide index -> script lines. Only slides with a say block that has lines appear."""
    found = {}
    for idx, s in enumerate(slides(markdown)):
        m = SAY.search("\n".join(s["body"]))
        if m:
            items = say_items(m.group(1))
            if items:
                found[idx] = items
    return found


def minutes_from_config(name: str, stage_minutes: dict[str, int]) -> int:
    """pack.yaml keys (e.g. guided_practice) matched against a heading such as 'Stage 4: Guided practice'."""
    low = name.lower()
    for key, mins in stage_minutes.items():
        if key.replace("_", " ") in low:
            return int(mins)
    return DEFAULT_MINUTES


def outline(markdown: str, stage_minutes: dict[str, int]) -> tuple[str, list[dict]]:
    """Lesson title (first '# ' heading) and stages ('## ' headings, quiz excluded).
    Minutes come from a '(N min)' tag in the heading, else from the pack config."""
    title, stages = "", []
    for line in markdown.splitlines():
        if not title and line.startswith("# "):
            title = line[2:].strip()
            continue
        m = re.match(r"## (.*)", line)
        if not m or m.group(1).strip().lower().startswith("quiz"):
            continue
        raw = m.group(1).strip()
        tag = MIN_RE.search(raw)
        name = MIN_RE.sub("", raw).strip(" ·-–:()")
        mins = int(tag.group(1)) if tag else minutes_from_config(raw, stage_minutes)
        stages.append({"name": name, "minutes": mins})
    return title, stages
