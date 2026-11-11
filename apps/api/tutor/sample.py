"""The practice lesson: a complete, hand-written lesson in the real format, for testing the classroom and voice.

It lives in the course pack (sample-lesson.md) and is copied to data/lessons/<date>.md. Its second line marks it as a
sample, so quiz answers, check-ins and the finish summary are never recorded as progress or sent to Obsidian.
"""
from __future__ import annotations
import datetime as dt
from pathlib import Path
from .lesson import Lesson, is_sample

SAMPLE_FILE = "sample-lesson.md"


def install(pack, store, data_dir: Path, day: dt.date, force: bool = False, build_audio: bool = True) -> Path:
    src = Path(pack.root) / SAMPLE_FILE
    text = src.read_text()
    out = Path(data_dir) / "lessons" / f"{day}.md"
    if out.exists() and not force:
        if not is_sample(out.read_text()):
            raise FileExistsError(f"{day} already has a real lesson; use --force to replace it")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    store.save_lesson(day, Lesson.parse(text).objectives, status="sample")  # not "planned": no reminders, late nudges or 'missed'
    if build_audio:
        build_slide_audio(pack, data_dir, text)
    return out


def build_slide_audio(pack, data_dir: Path, text: str):
    try:  # best effort: build the slide audio so Read starts at once
        from .tts import prebuild_lesson
        from . import pronounce as P
        prebuild_lesson(data_dir, text, rules=P.load(Path(pack.root) / "pronounce.yaml"))
    except Exception as e:  # noqa: BLE001 - voice files may not be fetched yet
        print(f"slide audio not built: {str(e)[:160]}", flush=True)


def lessons_off(store, data_dir: Path, now: dt.datetime, reset_progress: bool = False) -> dict:
    """Turn the lesson generator off and move every real (non-sample) lesson to data/lessons-archive/<time>/.
    Nothing is deleted: the archived files can be moved back by hand."""
    from .settings import Settings
    Settings(data_dir).update({"lesson_generator": False})
    src = Path(data_dir) / "lessons"
    dest = Path(data_dir) / "lessons-archive" / now.strftime("%Y%m%d-%H%M%S")
    moved = []
    for f in sorted(src.glob("*.md")) if src.exists() else []:
        if not is_sample(f.read_text()):
            dest.mkdir(parents=True, exist_ok=True)
            f.replace(dest / f.name)
            moved.append(f.stem)
    store.forget_lessons(moved, reset_progress)
    store.log_event(now, "lessons", f"generator off; archived {len(moved)} lesson(s)"
                    + ("; progress and chat reset" if reset_progress else ""))
    return {"archived": moved, "to": str(dest) if moved else "", "progress_reset": reset_progress}
