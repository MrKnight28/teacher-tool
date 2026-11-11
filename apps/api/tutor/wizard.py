"""Setup wizard: the browser form for first-run setup. The work is done by setup_core.py.

Run directly with `docker compose --profile setup-browser run --rm -p 127.0.0.1:8090:8090 wizard`. The terminal setup
(setup.ps1 / setup.sh) is the normal way; this form is optional.

The form can rewrite .env, so it only answers a request that (1) carries the one-time key printed in the setup window
(in the address, and as a hidden field in the form) and (2) is addressed to a local name. Without that, any web page
open in your browser could post to 127.0.0.1:8090 and change your WhatsApp number or reminder address.
"""
from __future__ import annotations
import hmac
import html
import os
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from .settings import Settings
from .setup_core import _env_value, apply, check_keys, fetch_models, read_env, recommend

# ---------- web form ----------

def _pack_dates(repo: Path) -> tuple[str, str, str]:
    """Exam date and trip pause in effect (saved setting, else the pack's), as form values."""
    from .pack import load_pack
    try:
        c = load_pack(Path(os.environ.get("TUTOR_PACKS_DIR", repo / "packs")), "security-plus-sy0-701", repo / "data").config
    except (OSError, KeyError, ValueError):  # no pack here: leave the fields blank
        return "", "", ""
    rng = c.get("pause_ranges") or []
    return str(c.get("exam_date") or ""), (str(rng[0]["start"]) if rng else ""), (str(rng[0]["end"]) if rng else "")


def _form_page(repo: Path, msg: str = "", prev: dict | None = None, key: str = "") -> str:
    env, s = read_env(repo / ".env"), Settings(repo / "data").get()
    exam, p_start, p_end = _pack_dates(repo)
    if prev:  # after an error, show what was typed (never secrets)
        s = dict(s, lesson_time=prev.get("lesson_time", s["lesson_time"]), timezone=prev.get("timezone", s["timezone"]),
                 tone=prev.get("tone", s["tone"]), voice_provider=prev.get("voice_provider", s["voice_provider"]),
                 rest_days=[d for d in prev.get("rest_days", ",".join(s["rest_days"])).split(",")],
                 max_messages_per_day=prev.get("max_messages", s["max_messages_per_day"]),
                 monthly_cap_gbp=prev.get("cap_gbp", s["monthly_cap_gbp"]))
        env = dict(env, WHATSAPP_TO=prev.get("whatsapp_to", ""), NTFY_URL=prev.get("ntfy_url", ""),
                   TS_HOSTNAME=prev.get("ts_hostname", "teacher-tool"), OBSIDIAN_TUTOR_DIR=prev.get("obsidian_dir", ""),
                   BACKUP_DIR=prev.get("backup_dir", ""))
        env["_use_wa"], env["_use_ts"] = bool(prev.get("use_whatsapp")), bool(prev.get("use_tailscale"))
    saved = lambda k: "(saved, leave blank to keep)" if env.get(k) else ""  # noqa: E731
    v = lambda x: html.escape(str(x), quote=True)  # noqa: E731
    chk = lambda c: "checked" if c else ""  # noqa: E731
    sel = lambda cur, opt: "selected" if cur == opt else ""  # noqa: E731
    return f"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Tutor Setup</title><style>
:root{{--bg:#fff;--fg:#1a1a1a;--mut:#666;--card:#f4f4f6;--acc:#2b59c3}}
@media(prefers-color-scheme:dark){{:root{{--bg:#15161a;--fg:#e8e8ea;--mut:#9a9aa3;--card:#202229;--acc:#8ab4ff}}}}
body{{font:16px/1.5 system-ui;max-width:680px;margin:0 auto;padding:16px;background:var(--bg);color:var(--fg)}}
fieldset{{margin-top:14px;border:0;border-radius:10px;background:var(--card);padding:12px 14px}}legend{{font-weight:600;padding:0}}
label{{display:block;margin-top:10px}}input,select{{width:100%;padding:8px;font:inherit;box-sizing:border-box;border-radius:8px;border:1px solid var(--mut);background:var(--bg);color:var(--fg)}}
input[type=checkbox]{{width:auto}}small{{color:var(--mut);display:block}}button{{margin-top:16px;padding:10px 18px;font:inherit;border:0;border-radius:8px;background:var(--acc);color:#fff}}
</style></head><body><h1>Security+ Tutor setup</h1>{msg}<form method=post><input type=hidden name=k value="{html.escape(key, quote=True)}">
<fieldset><legend>1. You</legend><label>Name<input name=name></label><label>Goal<input name=goal value="Pass CompTIA Security+ SY0-701"></label>
<label>Exam date<input name=exam_date type=date value="{v(exam)}"></label><label>Known weak areas<input name=weak></label>
<label>Trip pause from (blank = no pause)<input name=pause_start type=date value="{v(p_start)}"></label><label>Trip pause to<input name=pause_end type=date value="{v(p_end)}"></label>
<small>Leave name blank to keep your saved profile.</small></fieldset>

<fieldset><legend>2. Models (lessons, marking, chat)</legend>
<label>Provider<select name=llm_provider>
<option value=claude-cli {sel(env.get('LLM_PROVIDER','openrouter'),'claude-cli')}>My Claude Pro/Max subscription (via Claude Code)</option>
<option value=openrouter {sel(env.get('LLM_PROVIDER','openrouter'),'openrouter')}>OpenRouter API credit</option></select></label>
<label>Claude token<input name=claude_token type=password placeholder="{v(saved('CLAUDE_CODE_OAUTH_TOKEN') or 'sk-ant-oat01-...')}"></label>
<small>Get it once: in PowerShell run <code>docker run --rm -it teacher-tool-api claude setup-token</code> (or <code>claude setup-token</code> if Claude Code is installed), sign in, copy the token. Uses your subscription's normal limits.</small>
<label>OpenRouter API key (optional with a subscription; used for book photos)<input name=openrouter_key type=password placeholder="{v(saved('OPENROUTER_API_KEY'))}"></label>
<small>Get one at openrouter.ai/keys and set a credit limit on it.</small>
<label><input type=checkbox name=recommend checked> Pick the best model for each task automatically</label>
<label>Monthly spend cap (£)<input name=cap_gbp type=number value="{v(s['monthly_cap_gbp'])}"></label></fieldset>

<fieldset><legend>3. Voice</legend>
<label>Provider<select name=voice_provider><option value=gemini {sel(s['voice_provider'],'gemini')}>Google Gemini Live (recommended)</option>
<option value=openai {sel(s['voice_provider'],'openai')}>OpenAI Realtime mini</option><option value=none {sel(s['voice_provider'],'none')}>No voice yet</option></select></label>
<label>Gemini API key<input name=gemini_key type=password placeholder="{v(saved('GEMINI_API_KEY'))}"></label>
<label>OpenAI API key (backup)<input name=openai_key type=password placeholder="{v(saved('OPENAI_API_KEY'))}"></label></fieldset>

<fieldset><legend>4. Schedule</legend>
<label>Lesson time<input name=lesson_time value="{v(s['lesson_time'])}"></label>
<label>Rest days<input name=rest_days value="{v(','.join(s['rest_days']))}"></label>
<label>Time zone<input name=timezone value="{v(s['timezone'])}"></label>
<label>Reminder tone<select name=tone>{''.join(f'<option {sel(s["tone"],t)}>{t}</option>' for t in ('gentle','firm','strict'))}</select></label>
<label>Max messages per day (0-8)<input name=max_messages type=number min=0 max=8 value="{v(s['max_messages_per_day'])}"></label></fieldset>

<fieldset><legend>5. WhatsApp (via OpenClaw)</legend>
<label><input type=checkbox name=use_whatsapp {chk(env.get('_use_wa', env.get('WHATSAPP_TO')))}> Send reminders on WhatsApp</label>
<label>Your WhatsApp number<input name=whatsapp_to placeholder="+447700900000" value="{v(env.get('WHATSAPP_TO',''))}"></label>
<small>Setup starts a hardened OpenClaw and then shows a QR code in the setup window: scan it with WhatsApp &gt; Linked devices.</small>
<label>Backup channel: ntfy topic URL (optional)<input name=ntfy_url placeholder="https://ntfy.sh/long-random-topic" value="{v(env.get('NTFY_URL',''))}"></label></fieldset>

<fieldset><legend>6. Phone access and HTTPS (Tailscale)</legend>
<label><input type=checkbox name=use_tailscale {chk(env.get('_use_ts', env.get('TS_AUTHKEY')))}> Reach the tutor privately from my phone (needed for voice)</label>
<label>Tailscale auth key<input name=ts_authkey type=password placeholder="{v(saved('TS_AUTHKEY') or 'tskey-auth-...')}"></label>
<small>Create at login.tailscale.com/admin/settings/keys. In the admin console, turn on MagicDNS and HTTPS certificates.</small>
<label>Device name<input name=ts_hostname value="{v(env.get('TS_HOSTNAME','teacher-tool'))}"></label></fieldset>

<fieldset><legend>7. Folders on this PC</legend>
<label>Obsidian Tutor folder (lesson summaries are written here)<input name=obsidian_dir placeholder="C:\\Users\\you\\Documents\\TutorNotes" value="{v(env.get('OBSIDIAN_TUTOR_DIR',''))}"></label>
<label>Backup folder (nightly zip of progress and notes)<input name=backup_dir placeholder="D:\\Backups\\teacher-tool" value="{v(env.get('BACKUP_DIR',''))}"></label></fieldset>
<button>Test and save</button></form></body></html>"""


def _done_page(result: dict, checks: list[dict], models: dict | None) -> str:
    rows = "".join(f"<li>{'✅' if c['ok'] else '❌'} <b>{html.escape(c['name'])}</b>: {html.escape(str(c['detail']))}</li>"
                   for c in checks)
    chosen = "".join(f"<li>{html.escape(k)}: {html.escape(v)}</li>" for k, v in (models or {}).items())
    ts = (f"<p>Phone/HTTPS link (after setup finishes): <b>https://{html.escape(result['tailscale_host'])}.&lt;your-tailnet&gt;.ts.net</b></p>"
          if result["tailscale_host"] else "")
    return f"""<!doctype html><meta charset=utf-8><body style="font:16px/1.5 system-ui;max-width:680px;margin:auto;padding:16px">
<h1>Saved</h1><h3>Checks</h3><ul>{rows or '<li>No keys to test</li>'}</ul>
<h3>Models</h3><ul>{chosen or '<li>Kept your saved models</li>'}</ul>
<p>Your access token (also in <code>.env</code>; save it in your password manager):</p><pre style="user-select:all">{html.escape(result['token'])}</pre>
<p>Services to start: {html.escape(', '.join(['tutor'] + result['profiles']))}</p>{ts}
<p><b>Go back to the setup window</b>; it carries on automatically (starting services{', WhatsApp QR code' if 'whatsapp' in result['profiles'] else ''}, then a full self-test).</p>"""


LOCAL_NAMES = {"127.0.0.1", "localhost", "::1"}


def _local(value: str) -> bool:
    """True if a Host header or an Origin URL names this machine (the port may be anything: Docker publishes its own)."""
    value = (value or "").strip().lower()
    if not value or value == "null":
        return False
    try:
        host = urlsplit(value if "//" in value else "//" + value).hostname
    except ValueError:
        return False
    return host in LOCAL_NAMES


def allowed(headers, supplied_key: str, key: str) -> bool:
    """The request is for a local name, comes from a local page (if the browser says where from), and has the key."""
    if not _local(headers.get("Host", "")):
        return False
    origin = headers.get("Origin")
    if origin is not None and not _local(origin):
        return False
    return bool(key) and hmac.compare_digest((supplied_key or "").encode(), key.encode())


def make_handler(repo: Path, key: str):
    class H(BaseHTTPRequestHandler):
        timeout = 30   # a stalled client can't hold the form open

        def log_message(self, *a): pass

        def _page(self, body, code=200):
            b = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(b)

        def _refuse(self):
            self._page("<!doctype html><meta charset=utf-8><body style='font:16px system-ui;padding:16px'>"
                       "<h1>Not allowed</h1><p>Open the address printed in the setup window (it ends with <code>?k=…</code>).</p>", 403)

        def do_GET(self):
            supplied = (parse_qs(urlsplit(self.path).query).get("k") or [""])[0]
            if not allowed(self.headers, supplied, key):
                return self._refuse()
            self._page(_form_page(repo, key=key))

        def do_POST(self):
            try:
                n = int(self.headers.get("Content-Length", 0))
            except ValueError:
                n = -1
            if n < 0 or n > 40_000:
                return self._page("<!doctype html><meta charset=utf-8><p>Bad request.</p>", 400)
            form = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode(errors="replace")).items()}
            if not allowed(self.headers, form.pop("k", ""), key):
                return self._refuse()
            try:
                old = read_env(repo / ".env")
                api_key = _env_value(form.get("openrouter_key", "")) or old.get("OPENROUTER_API_KEY", "")
                models = None
                if form.get("recommend") and api_key:
                    try:
                        models = recommend(fetch_models(api_key))
                    except OSError:
                        models = None
                result = apply(repo, form, models)
                checks = check_keys(read_env(repo / ".env"))
            except ValueError as e:
                return self._page(_form_page(repo, f"<p style='color:#b3261e'><b>Not saved:</b> {html.escape(str(e))}</p>", form, key), 400)
            self._page(_done_page(result, checks, models))
            self.server.done = True
    return H


def run(repo: Path, host="0.0.0.0", port=8090, key: str | None = None):
    repo = Path(repo)
    key = key or secrets.token_urlsafe(16)
    srv = HTTPServer((host, port), make_handler(repo, key))
    srv.done = False
    print(f"Setup wizard: open http://127.0.0.1:{port}/?k={key} in your browser "
          "(use the port you published with -p; the key after ?k= is needed)", flush=True)
    while not srv.done:
        srv.handle_request()
