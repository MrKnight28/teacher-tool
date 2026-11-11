import argparse, datetime as dt, os, sys
from pathlib import Path
from .lesson_writer import write_lesson
from .pack import load_pack
from .store import Store


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tutor")
    sub = ap.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("setup", help="terminal setup for a fresh install (Claude, speech, models, checks)")
    st.add_argument("--repo", default="/repo")
    w = sub.add_parser("write-lesson", help="write a lesson for a date (default tomorrow)")
    w.add_argument("--date")
    sl = sub.add_parser("sample-lesson", help="install the practice lesson for a date (default today); nothing is recorded")
    sl.add_argument("--date")
    sl.add_argument("--force", action="store_true", help="replace a real lesson on that date")
    lo = sub.add_parser("lessons-off", help="turn the lesson generator off and archive real lessons; the practice lesson is used instead")
    lo.add_argument("--reset-progress", action="store_true", help="also clear quiz/check-in progress and chat history")
    sub.add_parser("lessons-on", help="turn the lesson generator back on")
    ip = sub.add_parser("import-pack", help="check course lesson plans (NN-name.plan.json) and write them as course lessons")
    ip.add_argument("--plans", required=True, help="folder of NN-name.plan.json files")
    ip.add_argument("--out", help="where to write the lessons (default: the course pack's lessons folder)")
    sub.add_parser("course-lessons", help="show which course lesson each study day gets")
    sub.add_parser("serve", help="run the web app")
    vb = sub.add_parser("voicebench", help="time speech-to-text (Whisper, bundled 5 s clip) and Gemini speech on this PC")
    vb.add_argument("--all", action="store_true", help="time tiny.en, base.en and small.en (downloads the models first)")
    fv = sub.add_parser("fetch-voices", help="download the Kokoro and Piper voice files once (needs internet)")
    fv.add_argument("--stt", choices=["parakeet"], help="also download a speech model: parakeet (int8 and float, about 3.2 GB)")
    sb = sub.add_parser("sttbench", help="compare speech-to-text engines on recordings in data/stt-samples")
    sb.add_argument("--samples", help="folder of .wav/.txt pairs (default data/stt-samples)")
    sb.add_argument("--threads", default="4,8,16", help="thread counts to compare")
    sw = sub.add_parser("stt-worker")   # used by sttbench: one engine in one process
    sw.add_argument("spec")
    tb = sub.add_parser("ttsbench", help="time how fast Kokoro and Piper start speaking on this PC")
    tb.add_argument("--threads", default="4,8,16", help="Kokoro ONNX thread counts to compare")
    tb.add_argument("--extras", action="store_true", help="also CPU use, inter-op threads and Kokoro-with-Whisper contention")
    wz = sub.add_parser("wizard", help="first-run setup wizard")
    wz.add_argument("--repo", default="/repo")
    stp = sub.add_parser("selftest", help="check keys, folders and channels")
    stp.add_argument("--send", action="store_true", help="also send a test reminder")
    sub.add_parser("scheduler", help="run reminders + nightly lesson writer (loops every 60s)")
    a = ap.parse_args(argv)
    if a.cmd == "wizard":
        from .wizard import run
        return run(Path(a.repo))
    if a.cmd == "setup":
        from .setup_cli import main as setup_main
        return setup_main(Path(a.repo))
    data = Path(os.environ.get("TUTOR_DATA_DIR", "./data"))
    if a.cmd == "sttbench":
        from . import stt as STT
        from .pronounce import load as load_rules
        from .bench.sttbench import run as stt_run
        pack = load_pack(Path(os.environ.get("TUTOR_PACKS_DIR", "./packs")), os.environ.get("TUTOR_PACK", "security-plus-sy0-701"), data)
        lessons = sorted((data / "lessons").glob("*.md"))
        rules = load_rules(pack.root / "pronounce.yaml")
        prompt = STT.build_prompt(pack, lessons[-1].read_text() if lessons else "", rules)
        threads = [int(x) for x in a.threads.split(",") if x.strip()]
        stt_run(data, prompt_text=prompt, samples=a.samples, threads=threads)
        return 0
    if a.cmd == "stt-worker":
        import json
        from .bench.sttbench import worker
        try:
            result = worker(json.loads(a.spec))
        except Exception as e:  # reported to the parent as this engine's error; other engines still run
            result = {"error": str(e)[:200]}
        print("RESULT " + json.dumps(result), flush=True)
        return 0
    if a.cmd == "fetch-voices":
        from .tts import fetch
        fetch()
        if a.stt == "parakeet":
            from .parakeet import fetch as fetch_parakeet, download_mb
            print(f"parakeet: about {download_mb('int8')} MB (int8) + {download_mb('float')} MB (float)")
            fetch_parakeet()
        return 0
    if a.cmd == "ttsbench":
        from .bench.ttsbench import run as tts_bench
        tts_bench(data, [int(x) for x in a.threads.split(",") if x.strip()], with_extras=a.extras)
        return 0
    if a.cmd == "voicebench":
        from .voice import WHISPER_MODELS
        from .bench.voicebench import run as bench
        bench(data, list(WHISPER_MODELS) if a.all else None)
        return 0
    packs = Path(os.environ.get("TUTOR_PACKS_DIR", "./packs"))
    pack = load_pack(packs, os.environ.get("TUTOR_PACK", "security-plus-sy0-701"), data)
    if a.cmd == "selftest":
        from .selftest import main as st_main
        return st_main(data, a.send)
    store = Store(data / "progress.db")
    if a.cmd == "write-lesson":
        from .settings import local_now
        day = dt.date.fromisoformat(a.date) if a.date else local_now(data).date() + dt.timedelta(days=1)
        from .settings import Settings
        if not Settings(data).get()["lesson_generator"]:
            print("The lesson generator is off (python3 -m tutor lessons-on to turn it back on).")
            return 1
        out = write_lesson(pack, store, data, day)
        print(out or f"{day}: not a study day (rest or pause), nothing written")
    elif a.cmd == "sample-lesson":
        from .sample import install
        from .settings import local_now
        day = dt.date.fromisoformat(a.date) if a.date else local_now(data).date()
        try:
            print(install(pack, store, data, day, force=a.force))
        except FileExistsError as e:
            print(e)
            return 1
    elif a.cmd == "lessons-off":
        from .sample import lessons_off
        from .settings import local_now
        r = lessons_off(store, data, local_now(data), a.reset_progress)
        print(f"Lesson generator is off. Archived {len(r['archived'])} lesson(s)"
              + (f" to {r['to']}" if r["archived"] else "") + (". Progress and chat cleared." if r["progress_reset"] else "."))
        print("Every date now opens the practice lesson. Turn back on with: python3 -m tutor lessons-on")
    elif a.cmd == "import-pack":
        from .importer import ImportProblem, build
        try:
            written = build(Path(a.plans), Path(a.out) if a.out else pack.root / "lessons", pack.config["stages"],
                            {o["id"] for o in pack.objectives})
        except ImportProblem as e:
            print(f"Not imported: {e}")
            return 1
        print(f"{len(written)} course lesson(s) checked and written:")
        for w in written:
            print(f"  {w}")
    elif a.cmd == "course-lessons":
        from .importer import preview
        from .settings import Settings, local_now
        start = Settings(data).get().get("pack_lessons_from")
        start = str(pack.config.get("lessons_from") or "") if start is None else start
        rows = preview(pack, data, store, local_now(data).date(), start or None)
        if not rows:
            print("Course lessons are off: the nightly writer writes every lesson.")
        for day, n, title in rows:
            print(f"{day} {day.strftime('%a')}  " + (f"lesson {n:2d}  {title}" if n else f"          {title}"))
        left = [n for _, n, _ in rows if n]
        print(f"{len(left)} course lesson(s) fit before the exam.")
    elif a.cmd == "lessons-on":
        from .settings import Settings
        Settings(data).update({"lesson_generator": True})
        print("Lesson generator is on. The next lesson is written by the scheduler.")
    elif a.cmd == "scheduler":
        import time
        from .notify import from_env
        from .scheduler import tick
        from .settings import Settings, local_now
        notifier = from_env()
        while True:
            try:
                p = load_pack(packs, os.environ.get("TUTOR_PACK", "security-plus-sy0-701"), data)
                now = local_now(data)
                for ev in tick(p, store, Settings(data), notifier, data, now, backup_dir=os.environ.get("TUTOR_BACKUP_DIR") or None):
                    print(f"{now:%F %T} {ev}", flush=True)
            except Exception as e:  # keep the loop alive; log and retry next minute
                print(f"scheduler error: {e}", flush=True)
            time.sleep(60)
    else:
        import logging
        from .server import App, serve
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")  # voice timing lines go to docker logs
        host = os.environ.get("TUTOR_HOST", "127.0.0.1")
        serve(App(pack, store, data, os.environ.get("TUTOR_TOKEN")), host, int(os.environ.get("TUTOR_PORT", "8080")))


if __name__ == "__main__":
    sys.exit(main())
