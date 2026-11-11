"""HTTP routes: one table per method. A route is a function taking the request handler (see server.py), which carries
`app`, `qs` (query string), `day`, `data` (parsed JSON body) and `n` (Content-Length), and answers with `req.send(...)`.

GET_ROUTES and POST_ROUTES are checked after the token. PUBLIC_GET is served without it (the two pages).
RAW_POST routes read their own body (audio, sample files), so the JSON parse is skipped for them.
Errors: ValueError from a route becomes 400 with its message (see server.py).
"""
from __future__ import annotations
import os
from pathlib import Path
from .llm import CapReached
from .bench import blindtest as BT
from . import pronounce as P
from .bench import sttbench as SB
from . import voice as V

UI = Path(__file__).with_name("ui.html")
ADMIN = Path(__file__).with_name("admin.html")
HTML = "text/html; charset=utf-8"
WAV = "audio/wav"

PUBLIC_GET: dict = {}
GET_ROUTES: dict = {}
GET_PREFIXES: list = []     # (prefix, route) for paths with an id at the end
POST_ROUTES: dict = {}
RAW_POST: dict = {}
RAW_PREFIXES: list = []


def _get(path):
    def deco(fn):
        GET_ROUTES[path] = fn
        return fn
    return deco


def _post(path):
    def deco(fn):
        POST_ROUTES[path] = fn
        return fn
    return deco


def match(table: dict, prefixes: list, path: str):
    if path in table:
        return table[path]
    for prefix, fn in prefixes:
        if path.startswith(prefix):
            return fn
    return None


def find_get(path):
    return match(GET_ROUTES, GET_PREFIXES, path)


def find_post(path):
    return match(POST_ROUTES, [], path)


def find_raw(path):
    return match(RAW_POST, RAW_PREFIXES, path)


# ---------- pages (no token) ----------

PUBLIC_GET["/"] = lambda req: req.send(200, UI.read_bytes(), HTML)
PUBLIC_GET["/admin"] = lambda req: req.send(200, ADMIN.read_bytes(), HTML)


# ---------- GET (token) ----------

@_get("/api/admin/blindtest")
def _blindtest(req):
    req.send(200, {"items": BT.playlist(req.app.data), "results": BT.results(req.app.data)})


def _blindtest_audio(req):
    f = BT.clip_path(req.app.data, req.path.rsplit("/", 1)[-1])
    return req.send(200, f.read_bytes(), WAV) if f else req.send(404, {"error": "no such clip"})


GET_PREFIXES.append(("/api/admin/blindtest/audio/", _blindtest_audio))


@_get("/api/admin")
def _admin(req):
    req.send(200, req.app.admin_state())


@_get("/api/admin/stt-samples")
def _stt_samples(req):
    req.send(200, {"samples": SB.samples_status(req.app.data)})


@_get("/api/admin/sttbench")
def _sttbench_status(req):
    req.send(200, SB.job_status(req.app.data))


@_get("/api/admin/selftest")
def _selftest(req):
    from .selftest import run_checks
    req.send(200, {"checks": run_checks(req.app.data), "setup": req.app.setup_info(),
                   "events": req.app.store.events(8)})


@_get("/api/notes")
def _notes(req):
    req.send(200, {"notes": req.app.notes()})


@_get("/api/voice/status")
def _voice_status(req):
    req.send(200, req.app.voice_status())


@_get("/api/chat/history")
def _chat_history(req):
    req.send(200, {"messages": req.app.store.chat_history(req.day, 50)})


@_get("/api/lesson")
def _lesson(req):
    app = req.app
    l = app.lesson(req.day)
    rec = app.store.lesson(req.day)
    if l and rec and rec["status"] in ("planned", "missed") and req.day == app.today():
        app.store.save_lesson(req.day, rec["objectives"], "started", rec["summary"])
    req.send(200 if l else 404, l or {"error": "no lesson for that date"})


@_get("/api/progress")
def _progress(req):
    req.send(200, req.app.progress(req.day))


# ---------- raw bodies (no JSON; the route reads them) ----------

def _drain(req, n, limit):
    """Read and drop an oversized body in chunks, so the client gets its answer, not a connection reset."""
    left = n
    while left > 0:
        left -= len(req.rfile.read(min(left, limit)))


def _transcribe(req):
    n = req.n
    if n > V.MAX_AUDIO_BYTES:
        _drain(req, n, 65536)
        return req.send(413, {"error": "recording too long (max about two minutes)"})
    audio = req.rfile.read(n)
    qs = req.qs
    ms = (qs.get("ms") or [""])[0]
    try:
        out = req.app.voice_transcribe(req.day, audio, req.headers.get("X-Audio-Mime", "")[:60],
                                       int(ms) if ms.isdigit() else None, chain=(qs.get("chain") or [""])[0])
        return req.send(200, out)
    except CapReached as e:
        return req.send(402, {"error": str(e)})
    except ValueError as e:
        return req.send(400, {"error": str(e)})
    except (RuntimeError, OSError) as e:
        return req.send(502, {"error": str(e)[:200] or "voice service unavailable, try again"})


RAW_POST["/api/voice/transcribe"] = _transcribe


def _stt_sample(req, name):
    if req.n > SB.MAX_SAMPLE_BYTES:
        _drain(req, req.n, 65536)
        return req.send(413, {"error": "the recording is too large (max about one minute)"})
    body = req.rfile.read(req.n) if req.n else b""
    try:
        SB.save_sample(req.app.data, name, body)
    except ValueError as e:
        return req.send(400, {"error": str(e)})
    return req.send(200, {"ok": True, "name": name})


RAW_PREFIXES.append(("/api/admin/stt-sample/", lambda req: _stt_sample(req, req.path.rsplit("/", 1)[-1])))


# ---------- POST (token, JSON body) ----------

@_post("/api/answer")
def _answer(req):
    if not isinstance(req.data.get("id"), int):
        return req.send(404, {"error": "not found"})
    r = req.app.answer(req.day, req.data["id"], str(req.data.get("answer", "")))
    req.send(200 if r else 404, r or {"error": "no such question"})


@_post("/api/finish")
def _finish(req):
    ok = req.app.finish(req.day, str(req.data.get("summary", "")))
    req.send(200 if ok else 404, {"ok": ok})


@_post("/api/notes")
def _save_notes(req):
    req.send(200, {"notes": req.app.save_notes(req.data.get("notes"))})


@_post("/api/voice/timings")
def _timings(req):
    req.send(200, req.app.browser_timing(req.data))


def _speech(req, method):
    try:
        wav = method(req.day, str(req.data.get("text", "")), str(req.data.get("kind", "read")), chain=str(req.data.get("chain", "")))
        return req.send(200, wav, WAV)
    except CapReached as e:
        return req.send(402, {"error": str(e)})
    except (RuntimeError, OSError) as e:
        return req.send(502, {"error": str(e)[:200] or "voice service unavailable, try again"})


POST_ROUTES["/api/voice/speak"] = lambda req: _speech(req, req.app.voice_speak)
POST_ROUTES["/api/voice/tts"] = lambda req: _speech(req, req.app.voice_tts)


@_post("/api/chat")
def _chat(req):
    r = req.app.chat(req.day, str(req.data.get("message", "")))
    req.send(200 if r else 400, r or {"error": "empty message"})


@_post("/api/checkin")
def _checkin(req):
    try:
        slide, qi = int(req.data.get("slide")), int(req.data.get("question_index"))
    except (TypeError, ValueError):
        return req.send(400, {"error": "bad check-in"})
    ans = str(req.data.get("answer", "")).strip()[:1000]
    if not ans:
        return req.send(400, {"error": "say something first"})
    req.stream(req.app.checkin(req.day, slide, qi, ans, chain=str(req.data.get("chain", ""))[:64]))


@_post("/api/chat/stream")
def _chat_stream(req):
    if not str(req.data.get("message", "")).strip():
        return req.send(400, {"error": "empty message"})
    req.stream(req.app.chat_stream(req.day, str(req.data.get("message", "")), req.n, chain=str(req.data.get("chain", ""))))


@_post("/api/admin/sttbench/run")
def _sttbench_run(req):
    started = SB.start(req.app.data, prompt_text=req.app.bench_prompt())
    req.send(202 if started else 409, {"started": started, "error": None if started else "sttbench is already running"})


@_post("/api/admin/selftest/send")
def _selftest_send(req):
    from .selftest import run_checks
    req.send(200, {"checks": run_checks(req.app.data, send_test=True), "setup": req.app.setup_info()})


@_post("/api/admin/write-lesson")
def _write_lesson(req):
    from .scheduler import try_write
    from .settings import local_now
    app = req.app
    if not app.settings.get()["lesson_generator"]:
        return req.send(409, {"error": "the lesson generator is off (admin > Schedule)"})
    app.store.reset_attempts(req.day, "write")  # a manual request always gets a fresh try
    r = try_write(app.pack, app.store, app.data, req.day, local_now(app.data))
    ok = r == "wrote_lesson"
    req.send(200 if ok else 502, {"ok": ok, "detail": r or "not written"})


@_post("/api/admin/blindtest/build")
def _blindtest_build(req):
    try:
        req.send(200, {"clips": len(BT.build(req.app.data, out=lambda s: None))})
    except RuntimeError as e:
        req.send(502, {"error": str(e)[:200]})


@_post("/api/admin/blindtest/vote")
def _blindtest_vote(req):
    ok = BT.vote(req.app.data, str(req.data.get("id", "")), req.data.get("score", 0))
    req.send(200 if ok else 400, {"ok": ok})


@_post("/api/admin/write-scripts")
def _write_scripts(req):
    from .lesson_writer import add_scripts
    if not req.app.settings.get()["lesson_generator"]:
        return req.send(409, {"error": "the lesson generator is off (admin > Schedule)"})
    try:
        ok = add_scripts(req.app.pack, req.app.data, req.day, req.app.llm)
    except CapReached as e:
        return req.send(402, {"error": str(e)})
    req.send(200 if ok else 502, {"ok": ok, "detail": "scripts added" if ok else "the model did not return usable scripts"})


@_post("/api/admin/pronounce")
def _pronounce(req):
    req.send(200, {"spoken": P.apply(str(req.data.get("text", ""))[:1000], req.app.pronounce)})


@_post("/api/admin/soul")
def _soul(req):
    req.app._write("soul.md", str(req.data.get("text", "")))
    req.send(200, {"ok": True})


@_post("/api/admin/context")
def _context(req):
    req.app._write("context.md", str(req.data.get("text", "")))
    req.send(200, {"ok": True})


@_post("/api/admin/settings")
def _settings(req):
    import threading
    changes = req.data.get("changes")
    if not isinstance(changes, dict):
        return req.send(404, {"error": "not found"})
    before = req.app.settings.get()["whisper_model"]
    out = req.app.settings.update(changes)
    if out["whisper_model"] != before:  # load the new speech model now, not on the next question
        threading.Thread(target=V.preload, args=(out["whisper_model"],), daemon=True).start()
    req.send(200, out)


@_post("/api/admin/materials")
def _materials(req):
    req.send(200, {"saved": req.app.materials.save(str(req.data.get("name", "")), str(req.data.get("content", "")))})


@_post("/api/admin/materials/photo")
def _photo(req):
    from .materials import transcribe_image
    model = os.environ.get("MODEL_VISION") or os.environ.get("MODEL_TEACH", "")
    try:
        f = transcribe_image(req.app.materials, str(req.data.get("name", "book")), str(req.data.get("image", "")),
                             req.app.llm, model)
    except CapReached as e:
        return req.send(402, {"error": str(e)})
    except OSError:
        return req.send(502, {"error": "model service unavailable, try again"})
    req.send(200, {"saved": f})


@_post("/api/admin/materials/delete")
def _materials_delete(req):
    req.send(200, {"deleted": req.app.materials.delete(str(req.data.get("name", "")))})
