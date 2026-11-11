"""Course lessons from a lesson pack: read a source pack, check hand-written plans, render them, and queue them by day.

Two halves:
1. Import (run once, by a person): `python3 -m tutor import-pack --plans DIR [--source PACK]`.
   A source pack (format teacher-tool-source-lesson-pack-v1: manifest.json + lessons/NN-*.md, a folder or a .zip) is
   parsed into structured lessons: notes, check-ins and A-D exam questions with keys. The notes come from PDF extraction
   and are not fit to teach from as they are, so each lesson is rewritten by a person (or a model, outside this module)
   as a lesson plan (the JSON shape in lesson_plan.py). This module checks every plan with lesson_plan.problem(), spreads
   the exam answers evenly over A to D, and writes `NN-slug.md` (what the classroom reads) and `NN-slug.plan.json` into
   the course pack's lessons/ folder.
2. Queue (every night): from settings.pack_lessons_from, on each study day the scheduler installs the lowest-numbered
   pack lesson not used yet. A lesson used on a day marked missed counts as unused, so it comes back. When every pack
   lesson is used, the nightly writer takes over.

Nothing here calls a model. Answer keys stay in the lesson file's quiz block, which is never sent to the browser.
A zip is read in memory, only the files the manifest names, with a size limit; nothing is extracted to disk.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import zipfile
from pathlib import Path

from . import lesson_plan

FORMAT = "teacher-tool-source-lesson-pack-v1"
MAX_FILE = 512 * 1024            # a lesson file in a pack; the 17-lesson pack's largest is about 9 KB
LETTERS = "ABCD"
MARK = "<!-- pack-lesson: {n} -->"
MARK_RE = re.compile(r"<!-- pack-lesson: (\d+) -->")
FILE_RE = re.compile(r"(\d{2})-[a-z0-9-]+\.md")


class ImportProblem(ValueError):
    pass


# ---------- reading a source pack ----------

def _reader(path: Path):
    """A function name -> text for a pack folder or zip. Only names inside the pack; size-limited."""
    path = Path(path)
    if path.is_dir():
        root = path.resolve()

        def read(name: str) -> str:
            p = (root / name).resolve()
            if root not in p.parents or not p.is_file():
                raise ImportProblem(f"{name}: not a file in the pack")
            if p.stat().st_size > MAX_FILE:
                raise ImportProblem(f"{name}: too large")
            return p.read_text(encoding="utf-8")
        return read
    if zipfile.is_zipfile(path):
        z = zipfile.ZipFile(path)
        names = {i.filename: i for i in z.infolist()}

        def read(name: str) -> str:
            info = names.get(name)
            if info is None or info.is_dir():
                raise ImportProblem(f"{name}: not in the zip")
            if info.file_size > MAX_FILE:
                raise ImportProblem(f"{name}: too large")
            return z.read(info).decode("utf-8")
        return read
    raise ImportProblem(f"{path}: not a pack folder or zip")


def objectives_from_mapping(mapping: str) -> list[str]:
    """'Domain 1.1' -> ['1.1']; 'Domains 3.1 / 3.2' -> ['3.1', '3.2']."""
    return re.findall(r"\b\d\.\d\b", mapping or "")


def read_pack(path: Path) -> list[dict]:
    """Every lesson in the pack: number, title, objectives, notes, checkins, exam (with keys), source file."""
    read = _reader(path)
    manifest = json.loads(read("manifest.json"))
    if manifest.get("format") != FORMAT:
        raise ImportProblem(f"unknown pack format {manifest.get('format')!r}")
    out = []
    for item in manifest.get("lessons") or []:
        name = str(item.get("file", ""))
        if not re.fullmatch(r"lessons/" + FILE_RE.pattern, name):
            raise ImportProblem(f"{name!r}: unexpected lesson file name")
        lesson = parse_lesson(read(name))
        lesson.update(number=int(item["lesson_number"]), title=str(item["title"]),
                      objectives=objectives_from_mapping(item.get("mapping", "")), file=name)
        if not lesson["objectives"]:
            raise ImportProblem(f"lesson {lesson['number']}: no objective in {item.get('mapping')!r}")
        out.append(lesson)
    return sorted(out, key=lambda x: x["number"])


def _section(text: str, heading: str, until: str | None) -> str:
    start = text.find(heading)
    if start == -1:
        return ""
    start += len(heading)
    end = text.find(until, start) if until else -1
    return text[start:end if end != -1 else len(text)].strip()


def parse_lesson(text: str) -> dict:
    """One source lesson file -> {notes, checkins: [{q, answer, reason}], exam: [{q, options, key, why}]}."""
    notes = _section(text, "## Lesson content", "## Check-in questions")
    checkins = []
    for block in re.split(r"^### Check-in \d+\s*$", _section(text, "## Check-in questions", "## Exam questions"), flags=re.M)[1:]:
        q = block.split("Discuss before revealing the answer.")[0].strip()
        ans = re.search(r"\*\*Answer:\*\*\s*(.+)", block)
        why = re.search(r"\*\*Reason:\*\*\s*(.+)", block)
        checkins.append({"q": " ".join(q.split()), "answer": ans.group(1).strip() if ans else "",
                         "reason": why.group(1).strip() if why else ""})
    exam = []
    for block in re.split(r"^### Question \d+\s*$", _section(text, "## Exam questions", "## Source boundary"), flags=re.M)[1:]:
        lines = [ln.strip() for ln in block.strip().splitlines()]
        opts = {m.group(1): m.group(2).strip() for ln in lines if (m := re.fullmatch(r"([A-D])\.\s+(.+)", ln))}
        stem = " ".join(ln for ln in lines if ln and not re.match(r"[A-D]\.\s|\*\*", ln))
        key = re.search(r"\*\*Answer key:\*\*\s*([A-D])", block)
        why = re.search(r"\*\*Explanation:\*\*\s*(.+)", block)
        if len(opts) != 4 or not key:
            raise ImportProblem(f"exam question {len(exam) + 1}: needs options A to D and an answer key")
        exam.append({"q": stem, "options": [opts[k] for k in LETTERS], "key": key.group(1),
                     "answer": opts[key.group(1)], "why": why.group(1).strip() if why else ""})
    return {"notes": notes, "checkins": checkins, "exam": exam}


# ---------- plans -> lesson files ----------

def balance(plans: list[dict]) -> list[dict]:
    """Reorder each exam question's options so the right answers cycle A, B, C, D across the whole course.
    Only the order changes: the stem, options and answer text are kept, so marking (by answer text) is unaffected."""
    i = 0
    for plan in plans:
        for q in plan["exam_questions"]:
            wrong = [o for o in q["options"] if o != q["answer"]]
            pos = i % len(LETTERS)
            q["options"] = wrong[:pos] + [q["answer"]] + wrong[pos:]
            i += 1
    return plans


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48]


def lesson_markdown(number: int, plan: dict, ids: list[str], stages: dict[str, int]) -> str:
    bad = lesson_plan.problem(plan, ids, list(stages))
    if bad:
        raise ImportProblem(f"lesson {number}: {bad}")
    return f"<!-- objectives: {','.join(ids)} -->\n{MARK.format(n=number)}\n" + lesson_plan.render(plan, stages)


def build(plans_dir: Path, out_dir: Path, stages: dict[str, int], known_ids: set[str]) -> list[Path]:
    """Every NN-*.plan.json in plans_dir: check, balance answers, write NN-*.md and the plan next to it in out_dir.
    All plans are checked before anything is written, so a bad plan leaves the lessons folder as it was."""
    files = sorted(Path(plans_dir).glob("[0-9][0-9]-*.plan.json"))
    if not files:
        raise ImportProblem(f"no NN-name.plan.json files in {plans_dir}")
    loaded = []
    for f in files:
        plan = json.loads(f.read_text(encoding="utf-8"))
        ids = plan.get("objectives")
        if not isinstance(ids, list) or not ids or any(i not in known_ids for i in ids):
            raise ImportProblem(f"{f.name}: 'objectives' must list this course's objective ids")
        loaded.append((int(f.name[:2]), f.name[:-len(".plan.json")], plan, ids))
    balance([p for _, _, p, _ in loaded])
    rendered = [(n, stem, plan, lesson_markdown(n, plan, ids, stages)) for n, stem, plan, ids in loaded]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for n, stem, plan, md in rendered:
        (out_dir / f"{stem}.plan.json").write_text(json.dumps(plan, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        (out_dir / f"{stem}.md").write_text(md, encoding="utf-8")
        written.append(out_dir / f"{stem}.md")
    return written


# ---------- the queue ----------

def course_lessons(pack_root: Path) -> dict[int, Path]:
    """The pack's ready lessons: number -> lesson file."""
    d = Path(pack_root) / "lessons"
    return {int(p.name[:2]): p for p in sorted(d.glob("[0-9][0-9]-*.md")) if FILE_RE.fullmatch(p.name)} if d.is_dir() else {}


def used(data_dir: Path, store, before: dt.date) -> set[int]:
    """Pack lessons already given on a day before `before`, except on days marked missed."""
    out = set()
    for f in (Path(data_dir) / "lessons").glob("????-??-??.md"):
        try:
            day = dt.date.fromisoformat(f.stem)
        except ValueError:
            continue
        if day >= before:
            continue
        m = MARK_RE.search(f.read_text(encoding="utf-8")[:300])
        if not m:
            continue
        row = store.lesson(day)
        if row is None or row["status"] != "missed":
            out.add(int(m.group(1)))
    return out


def next_lesson(pack_root: Path, data_dir: Path, store, day: dt.date, start: str | None) -> tuple[int, str] | None:
    """(number, file text) of the pack lesson for `day`, or None: no start date, before it, or every lesson used."""
    if not start or day < dt.date.fromisoformat(start):
        return None
    ready = course_lessons(pack_root)
    left = sorted(set(ready) - used(data_dir, store, day))
    if not left:
        return None
    n = left[0]
    return n, ready[n].read_text(encoding="utf-8")


def preview(pack, data_dir: Path, store, today: dt.date, start: str | None, until: dt.date | None = None) -> list[tuple]:
    """(day, lesson number or None, title) for each study day from max(start, today) up to the exam: what the queue will
    give if no lesson is missed. None means every course lesson is used by then and the nightly writer takes over."""
    if not start:
        return []
    ready = course_lessons(pack.root)
    titles = {n: (re.search(r"^# (.+)$", p.read_text(encoding="utf-8"), re.M) or [None, p.stem])[1] for n, p in ready.items()}
    left = sorted(set(ready) - used(data_dir, store, today))
    day = max(dt.date.fromisoformat(start), today)
    end = until or pack.config.get("exam_date") or day + dt.timedelta(days=60)
    out = []
    while day < end:
        if pack.is_study_day(day):
            n = left.pop(0) if left else None
            out.append((day, n, titles.get(n, "written by the nightly writer")))
        day += dt.timedelta(days=1)
    return out
