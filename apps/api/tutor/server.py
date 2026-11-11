"""Web app (stdlib only): the App combines the services; routes.py holds the paths; this file is the HTTP plumbing.
Binds to localhost by default."""
from __future__ import annotations
import datetime as dt
import hmac
import json
import logging
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from . import routes
from . import tts as TT
from . import pronounce as P
from . import voice as V
from .pack import Pack
from .services.admin import AdminMixin
from .services.chat import ChatMixin
from .services.lessons import LessonMixin
from .services.voice import VoiceMixin
from .settings import Settings, local_now
from .store import Store
from .materials import Materials

MAX_BODY = 8_500_000  # allows one book photo (base64) per request
WA_PATH = "/api/wa/inbound"   # the tutor-replies OpenClaw plugin; its own token, nothing else accepts it
WA_MAX_BODY = 16_384
CSP = ("default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src 'self' data:; media-src 'self' blob:; "
       "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
MIN_TOKEN = 16      # setup makes 43 characters; a short hand-typed TUTOR_TOKEN is refused at start
REQUEST_TIMEOUT = 60   # seconds a client may stall on one read or write (not how long a model may take to answer)
log = logging.getLogger("tutor.server")


def same_secret(got: str, expected: str) -> bool:
    """Constant-time comparison that never raises. Headers arrive as latin-1 text, so compare bytes: hmac.compare_digest
    raises TypeError on a str with non-ASCII characters, which let an unauthenticated request crash its handler."""
    return hmac.compare_digest(got.encode("latin-1", "replace"), (expected or "").encode("utf-8"))


class App(ChatMixin, LessonMixin, VoiceMixin, AdminMixin):
    def __init__(self, pack: Pack, store: Store, data_dir: Path, token: str | None):
        from .llm import LLM
        self.pack, self.store, self.data, self.token = pack, store, Path(data_dir), token
        self.settings, self.materials = Settings(self.data), Materials(self.data)
        self.llm = LLM(store, self.data)
        self.pronounce = P.load(pack.root / "pronounce.yaml")  # spoken forms for terms; the screen keeps the written form
        self.speech_cache = TT.SpeechCache(self.data / "cache" / "tts")  # slide audio, built after each lesson

    @property
    def soul(self) -> str:
        f = self.data / "soul.md"
        return f.read_text() if f.exists() else self.pack.soul

    @property
    def context(self) -> str:
        f = self.data / "context.md"
        return f.read_text() if f.exists() else ""

    def _write(self, name: str, text: str, limit: int = 20_000):
        if len(text) > limit:
            raise ValueError("too long")
        self.data.mkdir(parents=True, exist_ok=True)
        (self.data / name).write_text(text)

    def today(self) -> dt.date:
        return local_now(self.data).date()


def make_handler(app: App):
    """The request handler. It is also the request object routes.py receives: app, qs, path, day, data, n, rfile."""

    class H(BaseHTTPRequestHandler):
        timeout = REQUEST_TIMEOUT    # a half-sent request can't hold a thread open for ever
        started = False              # response headers already sent (so an error can't be answered with a second response)

        def log_message(self, *a): pass

        def _headers(self):
            self.started = True
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", CSP)
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")     # lessons, progress and answers are not for caches

        def send(self, code, body, ctype="application/json"):
            b = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b)))
            self._headers()
            self.end_headers()
            self.wfile.write(b)

        def stream(self, events):
            """Server-sent events: one JSON object per `data:` line, sent as each piece is ready."""
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self._headers()
            self.end_headers()
            try:
                for ev in events:
                    self.wfile.write(b"data: " + json.dumps(ev, ensure_ascii=False).encode() + b"\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass  # the page moved on (a newer question or Read); stop reading from the model
            finally:
                events.close()

        def _authed(self):
            if not app.token:
                return True
            got = self.headers.get("Authorization", "").removeprefix("Bearer ")
            return same_secret(got, app.token)

        def _length(self) -> int:
            """The body length the client declared, or -1 if it isn't a plain non-negative number."""
            raw = self.headers.get("Content-Length", "0").strip()
            return int(raw) if raw.isascii() and raw.isdigit() else -1

        def _setup(self, qs, path):
            self.app, self.qs, self.path = app, qs, path
            self.n = self._length()

        def _run(self, route):
            """Call a route. A ValueError is the caller's mistake (400); anything else is ours, and the answer says nothing
            about it (the log has the error's type, never its text, which could hold what the student typed)."""
            try:
                route(self)
            except ValueError as e:
                if self.started:
                    self.close_connection = True
                else:
                    self.send(400, {"error": str(e)})
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                self.close_connection = True
            except Exception as e:  # noqa: BLE001
                log.error("%s failed: %s", urlparse(self.path).path, type(e).__name__)
                if self.started:
                    self.close_connection = True
                else:
                    self.send(500, {"error": "server error"})

        def do_GET(self):
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            self._setup(qs, u.path)
            page = routes.PUBLIC_GET.get(u.path)
            if page:
                return self._run(page)
            if not self._authed():
                return self.send(401, {"error": "unauthorised"})
            self.day = _day(qs, app)
            route = routes.find_get(u.path)
            if route is None:
                return self.send(404, {"error": "not found"})
            self._run(route)

        def _whatsapp(self):
            """A WhatsApp message from the tutor-replies plugin. Only TUTOR_WA_TOKEN opens this route, and that token
            opens nothing else. Only the student's own number (WHATSAPP_TO) gets an answer."""
            token = os.environ.get("TUTOR_WA_TOKEN", "")
            got = self.headers.get("Authorization", "").removeprefix("Bearer ")
            if not token or not same_secret(got, token):
                return self.send(401, {"error": "unauthorised"})
            n = self._length()
            if n < 0:
                return self.send(400, {"error": "bad request"})
            if n > WA_MAX_BODY:
                return self.send(413, {"error": "too large"})
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
                text, sender = str(body.get("text", "")), str(body.get("sender", ""))
            except (ValueError, AttributeError):
                return self.send(400, {"error": "bad request"})
            owner = re.sub(r"\D", "", os.environ.get("WHATSAPP_TO", ""))
            if not owner or re.sub(r"\D", "", sender.split("@")[0].split(":")[0]) != owner:
                return self.send(403, {"error": "not the student's number"})
            from .whatsapp import Bot
            reply = Bot(app.pack, app.store, app.data, app.settings, local_now(app.data)).handle(text)
            app.store.log_event(local_now(app.data), "whatsapp", f"reply to '{text.split(' ')[0][:20]}'")
            return self.send(200, {"reply": reply})

        def do_POST(self):
            if urlparse(self.path).path == WA_PATH:
                return self._run(lambda _: self._whatsapp())
            if not self._authed():
                return self.send(401, {"error": "unauthorised"})
            u = urlparse(self.path)
            self._setup(parse_qs(u.query), u.path)
            if self.n < 0:
                return self.send(400, {"error": "bad request"})
            raw = routes.find_raw(u.path)
            if raw is not None:  # reads its own body
                self.day = _day(self.qs, app)
                return self._run(raw)
            if self.n > MAX_BODY:
                return self.send(413, {"error": "too large"})
            try:
                self.data = json.loads(self.rfile.read(self.n) or b"{}")
                if not isinstance(self.data, dict):
                    raise ValueError("expected a JSON object")
                self.day = dt.date.fromisoformat(self.data.get("date") or str(app.today()))
            except (ValueError, TypeError, RecursionError):   # bad JSON, a non-text date, or JSON nested too deep
                return self.send(400, {"error": "bad request"})
            route = routes.find_post(u.path)
            if route is None:
                return self.send(404, {"error": "not found"})
            self._run(route)
    return H


def _day(qs, app) -> dt.date:
    try:
        return dt.date.fromisoformat(qs.get("date", [""])[0]) if qs.get("date") else app.today()
    except ValueError:
        return app.today()


def serve(app: App, host="127.0.0.1", port=8080):
    if host != "127.0.0.1" and not app.token:
        raise SystemExit("Refusing to bind beyond localhost without TUTOR_TOKEN set")
    if app.token and len(app.token) < MIN_TOKEN:
        raise SystemExit(f"TUTOR_TOKEN is too short ({MIN_TOKEN}+ characters needed). Re-run setup; it makes a strong one.")
    threading.Thread(target=V.preload, daemon=True).start()  # load the speech model while the server starts
    ThreadingHTTPServer((host, port), make_handler(app)).serve_forever()
