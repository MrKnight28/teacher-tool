"""Terminal setup for a fresh install: `python3 -m tutor setup`, run by setup.ps1 / setup.sh.

It replaces the browser form for first-run provisioning. The browser admin page stays for everything after setup.

Stages: 1 system checks, 2 Claude, 3 speech-to-text, 4 text-to-speech, 5 application, 6 WhatsApp reminders,
7 models, 8 database, 9 validation, 10 summary. Each check prints one line: ok, a warning (optional, or not set up yet) or a failure.

- Writes go through wizard.apply(), so validation and the .env format stay in one place. Keys setup doesn't own are kept.
- Integrations set up earlier (Tailscale, the Obsidian and backup folders) are carried over, so a rerun never turns them off.
- WhatsApp is asked here. setup.ps1 / setup.sh then install OpenClaw's WhatsApp plugin and show the QR code.
- Re-running keeps what you don't change: prompts offer the saved value as the default, and saved secrets are kept
  unless you choose to replace them.
- Secrets are typed with hidden input and are never printed or logged.
- Models are installed by the existing installers (tts.fetch, parakeet.fetch, the Whisper loader). Files that are already
  there are checked, not downloaded again.
- Every model is tested by using it (a load, or a short synthesis), not only by checking that a file exists.

Every external step is a parameter (Deps), so tests run without Docker, a Claude account, an API key or a download.
"""
from __future__ import annotations

import datetime as dt
import io
import os
import re
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

from . import setup_core as core
from .pack import load_pack
from .selftest import _writable
from .settings import Settings
from .store import Store

WHISPER = "base.en"
PARAKEET_GB = 3.0
CHECK_TEXT = "Setup check. The tutor is ready."
VOICES = {  # choice: (lesson voice, fallback)
    "kokoro+piper": ("kokoro", "piper"),
    "kokoro": ("kokoro", "none"),
    "piper": ("piper", "none"),
}


# ---------- console (a real terminal, or scripted answers in tests) ----------

class Console:
    """Prompts on the terminal. Secrets use hidden input (getpass)."""

    def say(self, msg: str = "") -> None:
        print(msg, flush=True)

    def ask(self, question: str, default: str = "") -> str:
        shown = f" [{default}]" if default else ""
        return input(f"{question}{shown}: ").strip() or default

    def secret(self, question: str) -> str:
        import getpass
        return getpass.getpass(f"{question} (typed characters are hidden): ").strip()

    def yes(self, question: str, default: bool = True) -> bool:
        answer = input(f"{question} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
        return default if not answer else answer.startswith("y")

    def choose(self, question: str, options: list[tuple[str, str]], default: str) -> str:
        self.say(question)
        for i, (_, label) in enumerate(options, 1):
            self.say(f"  {i}. {label}")
        answer = input(f"Choose 1-{len(options)} [{[k for k, _ in options].index(default) + 1}]: ").strip()
        if not answer:
            return default
        if not answer.isdigit() or not 1 <= int(answer) <= len(options):
            self.say("Not a choice; keeping the default.")
            return default
        return options[int(answer) - 1][0]


# ---------- results ----------

@dataclass
class Check:
    group: str
    name: str
    status: str   # "ok", "warn" (optional, or not set up) or "fail"
    detail: str = ""


def _run_claude_setup_token() -> None:
    """Claude's own login. It prints a link and a token in this terminal; nothing here reads the login itself."""
    try:
        subprocess.run(["claude", "setup-token"], check=False)
    except FileNotFoundError:
        raise RuntimeError("Claude Code is not in this image (rebuild the setup image)")


def _whisper_present(name: str) -> bool:
    from .tts import MODELS_DIR
    return (MODELS_DIR / f"models--Systran--faster-whisper-{name}").exists()


def _check_parakeet() -> str:
    from faster_whisper.audio import decode_audio
    from .parakeet import load, recognize
    from .voice import BENCH_CLIP
    return recognize(load("int8", threads=4), decode_audio(str(BENCH_CLIP), sampling_rate=16000))


@dataclass
class Deps:
    """Every external step. The defaults are the app's own code; tests pass fakes."""
    claude_setup_token: object = _run_claude_setup_token   # runs `claude setup-token` in this terminal
    check_keys: object = core.check_keys                      # the key checks the admin page runs
    fetch_models: object = core.fetch_models                  # OpenRouter's model list
    install_voices: object = None                          # Kokoro + Piper files (tts.fetch)
    install_parakeet: object = None                        # Parakeet files (parakeet.fetch)
    whisper_present: object = _whisper_present
    load_whisper: object = None                            # loads, and downloads if missing, a Whisper model
    check_parakeet: object = _check_parakeet               # loads Parakeet and transcribes the bundled clip
    synthesize: object = None                              # tts.synthesize(text, primary, fallback)
    probe_relay: object = None                             # (model, key, data_dir) -> the model's reply to a reminder to relay

    def __post_init__(self):
        from . import parakeet, tts, voice
        self.install_voices = self.install_voices or (lambda out: tts.fetch(out=out))
        self.install_parakeet = self.install_parakeet or (lambda out: parakeet.fetch(out=out))
        self.load_whisper = self.load_whisper or (lambda name: voice._load_model(name))
        self.synthesize = self.synthesize or tts.synthesize
        self.probe_relay = self.probe_relay or core.probe_relay_model


def _wav_ok(wav: bytes, min_seconds: float = 0.2) -> bool:
    try:
        with wave.open(io.BytesIO(wav), "rb") as w:
            return w.getnframes() / w.getframerate() >= min_seconds
    except (wave.Error, EOFError, ZeroDivisionError):
        return False


def _valid_date(v: str) -> bool:
    try:
        dt.date.fromisoformat(v)
        return True
    except ValueError:
        return False


def _ask_until(con: Console, question: str, default: str, valid, message: str) -> str:
    while True:
        answer = con.ask(question, default)
        if not answer or valid(answer):
            return answer
        con.say(message)


# ---------- stages ----------

def stage_system(repo: Path, data: Path, out: list[Check]) -> bool:
    has_compose = (repo / "docker-compose.yml").exists()
    out.append(Check("System", "Project folder", "ok" if has_compose else "fail",
                     str(repo) if has_compose else "docker-compose.yml not found: is the repo mounted at /repo?"))
    writable, detail = _writable(str(data))
    out.append(Check("System", "Data folder", "ok" if writable else "fail", detail))
    # espeak-ng and Kokoro write temporary files here (the container's /tmp is noexec), so it must exist.
    tmp = Path(os.environ.get("TMPDIR", "/data/tmp"))
    try:
        tmp.mkdir(parents=True, exist_ok=True)
        tmp_ok, tmp_detail = True, f"{tmp} ready"
    except OSError as e:
        tmp_ok, tmp_detail = False, f"{tmp} cannot be created: {e.strerror}"
    out.append(Check("System", "Temporary folder for speech", "ok" if tmp_ok else "fail", tmp_detail))
    try:
        load_pack(Path(os.environ.get("TUTOR_PACKS_DIR", "./packs")), "security-plus-sy0-701", data)
        pack_ok, pack_detail = True, "Security+ SY0-701 loaded"
    except Exception as e:  # noqa: BLE001 - reported, not raised
        pack_ok, pack_detail = False, type(e).__name__
    out.append(Check("System", "Course pack", "ok" if pack_ok else "fail", pack_detail))
    return has_compose and writable and tmp_ok and pack_ok


def stage_claude(con: Console, deps: Deps, env: dict, form: dict, out: list[Check]) -> tuple[str, dict | None]:
    """Returns (choice, models). choice is 'pro', 'api' or 'later'; models are the recommended ones, if listed."""
    current = {"claude-cli": "pro", "openrouter": "api"}.get(env.get("LLM_PROVIDER", ""), "pro")
    choice = con.choose("How should the tutor use Claude?", [
        ("pro", "Claude Code / Claude Pro subscription (you log in once, in this terminal)"),
        ("api", "API key (OpenRouter: pay per use, includes Claude models)"),
        ("later", "Skip for now (lessons and chat will not run until you add one)"),
    ], default=current)
    models = None
    if choice == "pro":
        form["llm_provider"] = "claude-cli"
        if env.get("CLAUDE_CODE_OAUTH_TOKEN") and con.yes("A Claude token is already saved. Keep it?", True):
            out.append(Check("Claude", "Claude token", "ok", "kept from the last setup"))
        else:
            con.say("Claude Code will ask you to log in. Follow the link it shows, then copy the token it prints.")
            try:
                deps.claude_setup_token()
            except RuntimeError as e:
                out.append(Check("Claude", "Claude login", "fail", str(e)))
                return choice, None
            form["claude_token"] = con.secret("Paste the token here")
            out.append(Check("Claude", "Claude token", "ok", "entered"))
    elif choice == "api":
        form["llm_provider"] = "openrouter"
        if env.get("OPENROUTER_API_KEY") and con.yes("An API key is already saved. Keep it?", True):
            out.append(Check("Claude", "API key", "ok", "kept from the last setup"))
        else:
            form["openrouter_key"] = con.secret("Paste the OpenRouter API key here")
            out.append(Check("Claude", "API key", "ok", "entered"))
        key = form.get("openrouter_key") or env.get("OPENROUTER_API_KEY", "")
        try:
            models = core.recommend(deps.fetch_models(key)) if key else None
            out.append(Check("Claude", "Model per task", "ok" if models else "warn",
                             "recommended models chosen" if models else "no key to list models; kept the saved ones"))
        except Exception as e:  # noqa: BLE001 - the key check below reports a bad key
            out.append(Check("Claude", "Model per task", "warn", f"could not list models ({type(e).__name__}); kept the saved ones"))
    else:
        out.append(Check("Claude", "Claude", "warn", "not set up: lessons and chat will not run"))
    return choice, models


def stage_stt(con: Console, out: list[Check]) -> bool:
    """Whisper is always installed (the Japanese course needs it). Returns True if Parakeet should be installed too."""
    out.append(Check("Speech", f"Whisper {WHISPER}", "ok", "installed in step 6; used now and needed for Japanese"))
    want = con.yes(f"Also install Parakeet (about {PARAKEET_GB:.0f} GB) to compare speech engines? "
                   "It is not used for lessons yet", False)
    if want:
        out.append(Check("Speech", "Parakeet TDT 0.6B v3", "ok", "installed in step 6; compared with sttbench, not used for lessons yet"))
    return want


def stage_tts(con: Console, data: Path) -> dict:
    """The lesson voice and its fallback, as settings. All local voice files are installed whichever is picked."""
    current = Settings(data).get()
    default = next((k for k, v in VOICES.items() if v == (current["lesson_voice"], current["tts_fallback"])), "kokoro+piper")
    choice = con.choose("Lesson voice (all local voice files are installed, whichever you pick):", [
        ("kokoro+piper", "Kokoro, with Piper as the fallback (recommended)"),
        ("kokoro", "Kokoro only"),
        ("piper", "Piper only"),
    ], default=default)
    lesson, fallback = VOICES[choice]
    return {"lesson_voice": lesson, "tts_fallback": fallback}


def stage_app(con: Console, data: Path, form: dict) -> None:
    current = Settings(data).get()
    form["name"] = con.ask("Your first name (used in lessons; blank keeps the saved one)", "")
    form["goal"] = con.ask("What is your goal", "Pass CompTIA Security+ SY0-701")
    form["exam_date"] = _ask_until(con, "Exam date (YYYY-MM-DD; blank keeps the saved one)",
                                   current.get("exam_date") or "", _valid_date, "Use the form YYYY-MM-DD.")
    form["lesson_time"] = _ask_until(con, "Lesson time (HH:MM)", current["lesson_time"],
                                     lambda v: re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v), "Use the form HH:MM.")
    form["timezone"] = con.ask("Time zone", current["timezone"])
    form["cap_gbp"] = _ask_until(con, "Monthly spend cap in pounds", str(current["monthly_cap_gbp"]),
                                 lambda v: v.isdigit() and int(v) > 0, "Enter a whole number of pounds.")



def _profiles(repo: Path) -> list[str]:
    """Optional services switched on last time (setup/profiles.txt)."""
    try:
        return [p.strip() for p in (repo / "setup" / "profiles.txt").read_text().splitlines() if p.strip()]
    except OSError:
        return []


def carry_over(repo: Path, env: dict, form: dict) -> None:
    """Keep integrations this terminal setup doesn't ask about, so saving doesn't turn them off."""
    if "tailscale" in _profiles(repo):
        form["use_tailscale"] = "1"
        form["ts_hostname"] = env.get("TS_HOSTNAME") or "teacher-tool"
    form["obsidian_dir"] = env.get("OBSIDIAN_TUTOR_DIR", "")
    form["backup_dir"] = env.get("BACKUP_DIR", "")


def _masked(number: str) -> str:
    return number[:3] + "…" + number[-3:]


def _pick_messenger_model(con: Console, deps: Deps, data: Path, key: str, listing: list[dict], current: str,
                          saved: dict, out: list[Check]) -> tuple[str, list[str]]:
    """The messenger model only passes each reminder on word for word, but it has to obey that exactly. Rank OpenRouter's free
    models (biggest first), have each of the best few repeat a sample reminder, and keep the first that does plus two
    backups (a free model can be rate-limited or withdrawn). Returns (primary, fallbacks)."""
    ranked = core.rank_free_models(listing)
    if not ranked:
        return current, [m for m in saved.get("OPENCLAW_FALLBACK_MODELS", "").split(",") if m]
    con.say("Testing OpenRouter's free models for the WhatsApp messenger (each must repeat a reminder word for word)...")

    def probe(model):
        reply = deps.probe_relay(model, key, data)
        con.say(f"  {model}: {'ok' if core.relay_ok(reply, core.RELAY_SAMPLE) else 'did not repeat it exactly'}")
        return reply

    passed, _ = core.pick_relay_models(ranked, probe)
    if not passed:
        out.append(Check("WhatsApp", "Messenger model", "warn",
                         f"none of the top free models repeated a reminder exactly (rate limits?); kept {current or 'the default'}"))
        return current, [m for m in saved.get("OPENCLAW_FALLBACK_MODELS", "").split(",") if m]
    out.append(Check("WhatsApp", "Messenger model", "ok",
                     f"{passed[0]} (free)" + (f"; backups: {', '.join(passed[1:])}" if passed[1:] else "")))
    return passed[0], passed[1:]


def stage_whatsapp(con: Console, deps: Deps, repo: Path, env: dict, form: dict, models: dict | None,
                   out: list[Check]) -> dict | None:
    """Reminders on the student's own WhatsApp, through OpenClaw. Returns the models to save (a messenger model is added
    when none is set). OpenClaw needs a model of its own, so it needs an OpenRouter key even on a Claude subscription."""
    was_on = "whatsapp" in _profiles(repo)
    con.say("The tutor can message your own WhatsApp: a reminder before each lesson, nudges if you're late, an evening")
    con.say("check-in with your streak and a Sunday report. You can reply: status, move 19:00, skip, quiz, help.")
    con.say("It links like WhatsApp Web, only your number can talk to it, and replies come from the tutor's own data.")
    if not con.yes("Send reminders on WhatsApp?", was_on):
        out.append(Check("WhatsApp", "WhatsApp reminders", "warn",
                         "turned off" if was_on else "not set up: reminders go to the log"))
        return models
    number = _ask_until(con, "Your WhatsApp number, international format (e.g. +447700900000)",
                        env.get("WHATSAPP_TO", ""), lambda v: core.PHONE.fullmatch(v.replace(" ", "")),
                        "Use + then the country code and number, e.g. +447700900000.").replace(" ", "")
    if not number:
        out.append(Check("WhatsApp", "WhatsApp reminders", "warn", "no number given: left off"))
        return models
    key = form.get("openrouter_key") or env.get("OPENROUTER_API_KEY", "")
    if not key:
        con.say("The WhatsApp messenger needs its own small model to send messages. An OpenRouter key works, and its free models are enough.")
        key = con.secret("Paste an OpenRouter API key (blank leaves WhatsApp off)")
        if not key:
            out.append(Check("WhatsApp", "WhatsApp reminders", "warn", "needs an OpenRouter key: left off"))
            return models
        form["openrouter_key"] = key
    saved = {k: env[k] for k in ("MODEL_PLAN", "MODEL_TEACH", "MODEL_MARK", "MODEL_CHEAP", "OPENCLAW_FALLBACK_MODELS") if env.get(k)}
    cheap = (models or {}).get("MODEL_CHEAP") or saved.get("MODEL_CHEAP", "")
    fallbacks = [m for m in saved.get("OPENCLAW_FALLBACK_MODELS", "").split(",") if m]
    try:
        listing = deps.fetch_models(key)
        if not cheap:
            cheap = core.recommend(listing).get("MODEL_CHEAP", "")
        cheap, fallbacks = _pick_messenger_model(con, deps, repo / "data", key, listing, cheap, saved, out)
    except Exception as e:  # noqa: BLE001 - reported below
        out.append(Check("WhatsApp", "Messenger model", "warn", f"could not list free models ({type(e).__name__}); kept the saved one"))
    if cheap:
        models = {**saved, **(models or {}), "MODEL_CHEAP": cheap, "OPENCLAW_FALLBACK_MODELS": ",".join(fallbacks)}
    else:
        out.append(Check("WhatsApp", "Messenger model", "warn", "could not pick one; the messenger uses OpenClaw's default"))
    form["use_whatsapp"] = "1"
    form["whatsapp_to"] = number
    out.append(Check("WhatsApp", "WhatsApp reminders", "ok",
                     f"on for {_masked(number)}; scan the QR code that appears after setup"))
    return models


def stage_models(con: Console, deps: Deps, want_parakeet: bool, out: list[Check]) -> None:
    """Each model is named in its own check, so a failure says which one. A failure doesn't stop the others."""
    try:
        deps.install_voices(con.say)
        out.append(Check("Models", "Kokoro + Piper voice files", "ok", "installed, checksum matches"))
    except Exception as e:  # noqa: BLE001
        out.append(Check("Models", "Kokoro + Piper voice files", "fail", f"{str(e)[:160]} (run setup again to retry)"))
    if deps.whisper_present(WHISPER):
        out.append(Check("Models", f"Whisper {WHISPER}", "ok", "already installed, not downloaded again"))
    else:
        con.say(f"Downloading Whisper {WHISPER} ...")
        try:
            deps.load_whisper(WHISPER)
            out.append(Check("Models", f"Whisper {WHISPER}", "ok", "downloaded"))
        except Exception as e:  # noqa: BLE001
            out.append(Check("Models", f"Whisper {WHISPER}", "fail", f"{str(e)[:160]} (run setup again to retry)"))
    if want_parakeet:
        try:
            deps.install_parakeet(con.say)
            out.append(Check("Models", "Parakeet TDT 0.6B v3", "ok", "installed, checksum matches"))
        except Exception as e:  # noqa: BLE001
            out.append(Check("Models", "Parakeet TDT 0.6B v3", "fail", f"{str(e)[:160]} (run setup again to retry)"))


def stage_database(data: Path, speech: dict, out: list[Check]) -> None:
    try:
        Store(data / "progress.db")
        Settings(data).update(speech)
        out.append(Check("Database", "progress.db and settings", "ok", "ready"))
    except Exception as e:  # noqa: BLE001
        out.append(Check("Database", "progress.db and settings", "fail", f"{type(e).__name__}: {str(e)[:120]}"))


def stage_validate(deps: Deps, repo: Path, choice: str, speech: dict, want_parakeet: bool, out: list[Check]) -> None:
    """Uses each component. Nothing here prints a key: the key checks return only status text."""
    env = core.read_env(repo / ".env")
    for c in deps.check_keys(env):
        status = "ok" if c["ok"] else ("warn" if choice == "later" else "fail")
        out.append(Check("Validation", c["name"], status, c["detail"]))
    try:
        deps.load_whisper(WHISPER)
        out.append(Check("Validation", f"Speech-to-text: Whisper {WHISPER}", "ok", "loads"))
    except Exception as e:  # noqa: BLE001
        out.append(Check("Validation", f"Speech-to-text: Whisper {WHISPER}", "fail", str(e)[:160]))
    if want_parakeet:
        try:
            text = deps.check_parakeet()
            out.append(Check("Validation", "Speech-to-text: Parakeet", "ok" if text.strip() else "fail",
                             "loads and transcribes the test clip" if text.strip() else "loaded but returned no text"))
        except Exception as e:  # noqa: BLE001
            out.append(Check("Validation", "Speech-to-text: Parakeet", "fail", str(e)[:160]))
    voices = [speech["lesson_voice"]] + ([speech["tts_fallback"]] if speech["tts_fallback"] != "none" else [])
    for voice in voices:
        try:
            wav, _, _ = deps.synthesize(CHECK_TEXT, voice, None)
            out.append(Check("Validation", f"Text-to-speech: {voice}" + (" (fallback)" if voice != speech["lesson_voice"] else ""),
                             "ok" if _wav_ok(wav) else "fail", "synthesises a sentence" if _wav_ok(wav) else "produced no audio"))
        except Exception as e:  # noqa: BLE001
            out.append(Check("Validation", f"Text-to-speech: {voice}", "fail", str(e)[:160]))


def summary(con: Console, checks: list[Check], env_path: Path) -> bool:
    con.say("\nTeacher Tool setup")
    group = None
    for c in checks:
        if c.group != group:
            group = c.group
            con.say(f"\n{group}")
        mark = {"ok": "ok  ", "warn": "!   ", "fail": "FAIL"}[c.status]
        con.say(f"  {mark} {c.name}" + (f": {c.detail}" if c.detail else ""))
    failed = [c for c in checks if c.status == "fail"]
    con.say("")
    if failed:
        con.say(f"Setup finished with {len(failed)} problem(s). Fix the items marked FAIL, then run setup again: it keeps your settings.")
    else:
        con.say("Setup complete.")
    con.say("Next: docker compose up -d, then open http://127.0.0.1:8080 (admin page: /admin).")
    con.say(f"Your access token is saved as TUTOR_TOKEN in {env_path}. It is not printed here.")
    return not failed


# ---------- run ----------

def run(repo: Path, con: Console | None = None, deps: Deps | None = None) -> tuple[bool, list[Check]]:
    repo = Path(repo)
    con = con or Console()
    deps = deps or Deps()
    data = repo / "data"
    env = core.read_env(repo / ".env")
    checks: list[Check] = []
    con.say("Teacher Tool setup. Press Enter to keep the value in brackets.")

    con.say("\n== 1 of 10: system checks")
    if not stage_system(repo, data, checks):
        summary(con, checks, repo / ".env")
        return False, checks
    con.say("\n== 2 of 10: Claude")
    form: dict = {}
    choice, models = stage_claude(con, deps, env, form, checks)
    if any(c.group == "Claude" and c.status == "fail" for c in checks):   # no login, nothing else can work: stop here
        summary(con, checks, repo / ".env")
        return False, checks
    con.say("\n== 3 of 10: speech-to-text")
    want_parakeet = stage_stt(con, checks)
    con.say("\n== 4 of 10: text-to-speech")
    speech = stage_tts(con, data)
    con.say("\n== 5 of 10: application")
    stage_app(con, data, form)
    con.say("\n== 6 of 10: WhatsApp reminders")
    models = stage_whatsapp(con, deps, repo, env, form, models, checks)
    carry_over(repo, env, form)
    try:
        core.apply(repo, form, models)
        checks.append(Check("Application", "Configuration saved", "ok", ".env and data/ updated; other settings kept"))
    except ValueError as e:
        checks.append(Check("Application", "Configuration saved", "fail", str(e)))
        summary(con, checks, repo / ".env")
        return False, checks
    con.say("\n== 7 of 10: models")
    stage_models(con, deps, want_parakeet, checks)
    con.say("\n== 8 of 10: database")
    stage_database(data, speech, checks)
    con.say("\n== 9 of 10: validation (each model is used, not only found)")
    stage_validate(deps, repo, choice, speech, want_parakeet, checks)
    con.say("\n== 10 of 10: summary")
    return summary(con, checks, repo / ".env"), checks


def main(repo: Path) -> int:
    ok, _ = run(repo)
    return 0 if ok else 1
