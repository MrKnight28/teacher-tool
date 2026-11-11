import io
import wave
from pathlib import Path

import pytest

from tutor import setup_cli as SC
from tutor import setup_core as W
from tutor.settings import Settings

ROOT = Path(__file__).resolve().parents[3]
PACKS = ROOT / "packs"
MODELS = {"MODEL_PLAN": "x/plan", "MODEL_TEACH": "x/teach", "MODEL_MARK": "x/mark", "MODEL_CHEAP": "x/cheap"}
SECRET = "SECRET-TOKEN-123456"
KEY = "test-openrouter-key"


def wav(seconds=1.0):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x01\x00" * int(seconds * 16000))
    return buf.getvalue()


class Script(SC.Console):
    """Scripted answers. Every prompt pops the next answer; everything printed is kept for the checks."""

    def __init__(self, choose=(), yes=(), ask=(), secret=()):
        self.answers = {"choose": list(choose), "yes": list(yes), "ask": list(ask), "secret": list(secret)}
        self.lines = []

    def say(self, msg=""):
        self.lines.append(str(msg))

    def ask(self, question, default=""):
        return self.answers["ask"].pop(0) if self.answers["ask"] else default

    def secret(self, question):
        return self.answers["secret"].pop(0)

    def yes(self, question, default=True):
        self.asked = getattr(self, "asked", []) + [question]
        # questions a test doesn't script (the WhatsApp one, last) take the default, as pressing Enter would
        return self.answers["yes"].pop(0) if self.answers["yes"] else default

    def choose(self, question, options, default):
        return self.answers["choose"].pop(0)

    @property
    def output(self):
        return "\n".join(self.lines)


def app_answers(name="Kyle", goal="Pass Security+", exam="2027-06-30", lesson_time="09:00", tz="Europe/London", cap="20"):
    return [name, goal, exam, lesson_time, tz, cap]


def make_deps(**over):
    calls = {"whisper": []}

    def load_whisper(name):
        calls["whisper"].append(name)

    base = dict(
        claude_setup_token=lambda: None,
        check_keys=lambda env: ([{"name": "Claude subscription", "ok": True, "detail": "works"}]
                                if env.get("CLAUDE_CODE_OAUTH_TOKEN") else
                                [{"name": "Claude subscription", "ok": False, "detail": "no token"}]),
        fetch_models=lambda key: [],
        install_voices=lambda out: None,
        install_parakeet=lambda out: None,
        whisper_present=lambda name: True,
        load_whisper=load_whisper,
        check_parakeet=lambda: "firewall",
        synthesize=lambda text, primary, fallback: (wav(), primary, {}),
    )
    base.update(over)
    deps = SC.Deps(**base)
    deps.calls = calls
    return deps


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    (tmp_path / "data").mkdir()
    monkeypatch.setenv("TUTOR_PACKS_DIR", str(PACKS))
    monkeypatch.setenv("TMPDIR", str(tmp_path / "tmp"))
    return tmp_path


def env_of(repo):
    return W.read_env(repo / ".env")


# ---------- first run ----------

def test_first_run_with_claude_pro_writes_config_and_passes(repo):
    con = Script(choose=["pro", "kokoro+piper"], yes=[False], ask=app_answers(), secret=[SECRET])
    ok, checks = SC.run(repo, con, make_deps())
    assert ok is True
    env = env_of(repo)
    assert env["LLM_PROVIDER"] == "claude-cli" and env["CLAUDE_CODE_OAUTH_TOKEN"] == SECRET
    assert len(env["TUTOR_TOKEN"]) >= 40
    s = Settings(repo / "data").get()
    assert (s["lesson_voice"], s["tts_fallback"]) == ("kokoro", "piper")
    assert s["exam_date"] == "2027-06-30"


def test_secrets_are_never_printed(repo):
    con = Script(choose=["pro", "kokoro+piper"], yes=[False], ask=app_answers(), secret=[SECRET])
    SC.run(repo, con, make_deps())
    token = env_of(repo)["TUTOR_TOKEN"]
    assert SECRET not in con.output and token not in con.output
    assert "TUTOR_TOKEN" in con.output    # the name is shown, the value is not


def test_api_key_path_stores_key_and_recommended_models(repo, monkeypatch):
    monkeypatch.setattr(W, "recommend", lambda models: {"MODEL_PLAN": "p", "MODEL_TEACH": "t", "MODEL_MARK": "m", "MODEL_CHEAP": "c"})
    con = Script(choose=["api", "kokoro+piper"], yes=[False], ask=app_answers(), secret=[KEY])
    deps = make_deps(fetch_models=lambda key: [{"id": "x"}], check_keys=lambda env: (
        [{"name": "OpenRouter key", "ok": True, "detail": "valid"}] if env.get("OPENROUTER_API_KEY") else []))
    ok, _ = SC.run(repo, con, deps)
    assert ok is True
    env = env_of(repo)
    assert env["LLM_PROVIDER"] == "openrouter" and env["OPENROUTER_API_KEY"] == KEY and env["MODEL_TEACH"] == "t"
    assert KEY not in con.output


def test_later_choice_is_a_warning_not_a_failure(repo):
    con = Script(choose=["later", "piper"], yes=[False], ask=app_answers())
    deps = make_deps(check_keys=lambda env: [{"name": "Claude subscription", "ok": False, "detail": "no token"}])
    ok, checks = SC.run(repo, con, deps)
    assert ok is True
    assert any(c.name == "Claude subscription" and c.status == "warn" for c in checks)


def test_voice_choices_are_stored(repo):
    con = Script(choose=["pro", "piper"], yes=[False], ask=app_answers(), secret=[SECRET])
    SC.run(repo, con, make_deps())
    s = Settings(repo / "data").get()
    assert (s["lesson_voice"], s["tts_fallback"]) == ("piper", "none")


# ---------- rerun ----------

def test_rerun_keeps_saved_secrets_and_unrelated_settings(repo):
    SC.run(repo, Script(choose=["pro", "kokoro+piper"], yes=[False], ask=app_answers(), secret=[SECRET]), make_deps())
    with open(repo / ".env", "a") as f:
        f.write("TRANSCRIBE=local\nMODEL_VISION=some/vision\n")          # keys setup doesn't own
    Settings(repo / "data").update({"tone": "gentle"})
    token_before = env_of(repo)["TUTOR_TOKEN"]
    con = Script(choose=["pro", "kokoro+piper"], yes=[True, False], ask=app_answers(name="", goal="Pass Security+"))
    ok, checks = SC.run(repo, con, make_deps())
    assert ok is True
    env = env_of(repo)
    assert env["CLAUDE_CODE_OAUTH_TOKEN"] == SECRET and env["TUTOR_TOKEN"] == token_before
    assert env["TRANSCRIBE"] == "local" and env["MODEL_VISION"] == "some/vision"
    assert Settings(repo / "data").get()["tone"] == "gentle"
    assert any(c.name == "Claude token" and "kept" in c.detail for c in checks)


def test_apply_keeps_keys_it_does_not_own_and_untouched_settings(repo):
    (repo / ".env").write_text("TRANSCRIBE=local\nKOKORO_VOICE=af_sky\n")
    Settings(repo / "data").update({"lesson_time": "10:30", "tone": "gentle"})
    W.apply(repo, {"openrouter_key": KEY})
    env = env_of(repo)
    assert env["TRANSCRIBE"] == "local" and env["KOKORO_VOICE"] == "af_sky"
    s = Settings(repo / "data").get()
    assert s["lesson_time"] == "10:30" and s["tone"] == "gentle"


def test_rerun_does_not_reinstall_whisper_when_present(repo):
    deps = make_deps(whisper_present=lambda name: True)
    SC.run(repo, Script(choose=["pro", "kokoro+piper"], yes=[False], ask=app_answers(), secret=[SECRET]), deps)
    assert deps.calls["whisper"] == ["base.en"]   # only the validation load, no download


def test_missing_whisper_is_downloaded_once_then_checked(repo):
    deps = make_deps(whisper_present=lambda name: False)
    SC.run(repo, Script(choose=["pro", "kokoro+piper"], yes=[False], ask=app_answers(), secret=[SECRET]), deps)
    assert deps.calls["whisper"] == ["base.en", "base.en"]   # install, then validation


# ---------- failures are named ----------

def test_failed_voice_install_is_named_and_setup_carries_on(repo):
    def broken(out):
        raise RuntimeError("checksum mismatch for kokoro-v1.0.onnx: not saved")
    con = Script(choose=["pro", "kokoro+piper"], yes=[False], ask=app_answers(), secret=[SECRET])
    ok, checks = SC.run(repo, con, make_deps(install_voices=broken))
    assert ok is False
    failed = [c for c in checks if c.status == "fail"]
    assert any("Kokoro + Piper" in c.name and "checksum mismatch" in c.detail for c in failed)
    assert any(c.group == "Database" and c.status == "ok" for c in checks)   # later stages still ran


def test_failed_parakeet_install_is_reported_with_its_name(repo):
    def broken(out):
        raise RuntimeError("download failed")
    con = Script(choose=["pro", "kokoro+piper"], yes=[True], ask=app_answers(), secret=[SECRET])
    ok, checks = SC.run(repo, con, make_deps(install_parakeet=broken))
    assert ok is False
    assert any(c.name == "Parakeet TDT 0.6B v3" and c.status == "fail" for c in checks)


def test_a_voice_that_fails_its_test_is_reported(repo):
    def synth(text, primary, fallback):
        if primary == "kokoro":
            raise RuntimeError("model would not load")
        return wav(), primary, {}
    con = Script(choose=["pro", "kokoro+piper"], yes=[False], ask=app_answers(), secret=[SECRET])
    ok, checks = SC.run(repo, con, make_deps(synthesize=synth))
    assert ok is False
    assert any(c.name == "Text-to-speech: kokoro" and c.status == "fail" for c in checks)
    assert any(c.name == "Text-to-speech: piper (fallback)" and c.status == "ok" for c in checks)


def test_a_silent_voice_output_is_a_failure(repo):
    def silent(text, primary, fallback):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
        return buf.getvalue(), primary, {}
    con = Script(choose=["pro", "piper"], yes=[False], ask=app_answers(), secret=[SECRET])
    ok, checks = SC.run(repo, con, make_deps(synthesize=silent))
    assert ok is False and any(c.name == "Text-to-speech: piper" and c.status == "fail" for c in checks)


def test_a_rejected_claude_token_is_reported(repo):
    con = Script(choose=["pro", "kokoro+piper"], yes=[False], ask=app_answers(), secret=["WRONG-TOKEN-XYZ"])
    deps = make_deps(check_keys=lambda env: [{"name": "Claude subscription", "ok": False,
                                              "detail": "RuntimeError: login failed"}])
    ok, checks = SC.run(repo, con, deps)
    assert ok is False
    assert any(c.name == "Claude subscription" and c.status == "fail" for c in checks)
    assert "WRONG-TOKEN-XYZ" not in con.output


def test_claude_login_step_failing_stops_before_writing_the_token(repo):
    def no_claude():
        raise RuntimeError("Claude Code is not in this image")
    con = Script(choose=["pro"], yes=[], ask=[], secret=[])
    ok, checks = SC.run(repo, con, make_deps(claude_setup_token=no_claude))
    assert ok is False
    assert any(c.name == "Claude login" and c.status == "fail" for c in checks)
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in env_of(repo)


def test_unusable_temporary_folder_stops_setup(repo, tmp_path, monkeypatch):
    blocker = tmp_path / "a-file"
    blocker.write_text("not a folder")
    monkeypatch.setenv("TMPDIR", str(blocker / "tmp"))   # cannot be created under a file
    ok, checks = SC.run(repo, Script(), make_deps())
    assert ok is False and any(c.name == "Temporary folder for speech" and c.status == "fail" for c in checks)


def test_missing_project_folder_stops_setup(tmp_path, monkeypatch):
    monkeypatch.setenv("TUTOR_PACKS_DIR", str(PACKS))
    ok, checks = SC.run(tmp_path, Script(), make_deps())
    assert ok is False and any(c.name == "Project folder" and c.status == "fail" for c in checks)


# ---------- the browser form is no longer needed for first-run setup ----------

def test_setup_scripts_no_longer_open_the_browser_form():
    for script in (ROOT / "setup.ps1", ROOT / "setup.sh"):
        text = script.read_text()
        assert "run --rm setup" in text
        assert "--profile setup run --rm -p" not in text and "Start-Job" not in text and "xdg-open" not in text


def test_compose_has_terminal_setup_with_the_same_limits_as_the_tutor():
    text = (ROOT / "docker-compose.yml").read_text()
    setup_block = text[text.index("  setup:"):text.index("  # Optional: the browser form")]
    assert "read_only: true" in setup_block and "cap_drop: [ALL]" in setup_block
    assert "no-new-privileges" in setup_block and "\n    ports:" not in setup_block
    assert '["python3", "-m", "tutor", "setup"' in setup_block


def test_access_token_is_not_printed_by_the_scripts():
    for script in (ROOT / "setup.ps1", ROOT / "setup.sh"):
        text = script.read_text()
        assert "Access token: $token" not in text and '"Access token: ${TOKEN}"' not in text


# ---------- WhatsApp ----------

PHONE_NO = "+447700900123"


def test_fresh_setup_leaves_whatsapp_off_by_default(repo):
    con = Script(choose=["pro", "kokoro+piper"], yes=[False], ask=app_answers(), secret=[SECRET])
    ok, checks = SC.run(repo, con, make_deps())
    assert ok is True
    assert "Send reminders on WhatsApp?" in con.asked
    assert "WHATSAPP_TO" not in env_of(repo)
    assert "whatsapp" not in (repo / "setup" / "profiles.txt").read_text()
    assert any(c.group == "WhatsApp" and c.status == "warn" for c in checks)


def test_whatsapp_on_with_a_claude_subscription_asks_for_a_messenger_key(repo, monkeypatch):
    monkeypatch.setattr(W, "recommend", lambda models: {"MODEL_PLAN": "p", "MODEL_TEACH": "t", "MODEL_MARK": "m", "MODEL_CHEAP": "free/x"})
    con = Script(choose=["pro", "kokoro+piper"], yes=[False, True], ask=app_answers() + [PHONE_NO], secret=[SECRET, KEY])
    ok, checks = SC.run(repo, con, make_deps(fetch_models=lambda key: [{"id": "x"}]))
    assert ok is True
    env = env_of(repo)
    assert env["LLM_PROVIDER"] == "claude-cli"                  # the tutor still uses the subscription
    assert env["WHATSAPP_TO"] == PHONE_NO and env["OPENROUTER_API_KEY"] == KEY and env["MODEL_CHEAP"] == "free/x"
    assert env["OPENCLAW_HOOK_TOKEN"] and env["OPENCLAW_HOOK_URL"]
    assert (repo / "setup" / "profiles.txt").read_text().split() == ["whatsapp"]
    cfg = (repo / "openclaw" / "config" / "openclaw.json").read_text()
    assert PHONE_NO in cfg and '"messaging"' in cfg
    assert KEY not in con.output and PHONE_NO not in con.output   # the number is shown masked only
    assert any(c.group == "WhatsApp" and c.status == "ok" for c in checks)


def test_a_bad_number_is_asked_again(repo):
    con = Script(choose=["api", "kokoro+piper"], yes=[False, True], ask=app_answers() + ["07700 900123", PHONE_NO], secret=[KEY])
    ok, _ = SC.run(repo, con, make_deps(check_keys=lambda env: []))
    assert ok is True and env_of(repo)["WHATSAPP_TO"] == PHONE_NO
    assert "international" in con.output or "+447700900000" in con.output


def test_whatsapp_without_a_key_stays_off(repo):
    con = Script(choose=["pro", "kokoro+piper"], yes=[False, True], ask=app_answers() + [PHONE_NO], secret=[SECRET, ""])
    ok, checks = SC.run(repo, con, make_deps())
    assert ok is True and "WHATSAPP_TO" not in env_of(repo)
    assert any(c.group == "WhatsApp" and "OpenRouter key" in c.detail for c in checks)


def test_rerun_keeps_whatsapp_on_by_pressing_enter_and_can_turn_it_off(repo):
    SC.run(repo, Script(choose=["api", "kokoro+piper"], yes=[False, True], ask=app_answers() + [PHONE_NO], secret=[KEY]),
           make_deps(check_keys=lambda env: []))
    # rerun: keep the key, no Parakeet, then Enter on the WhatsApp question (default is on) and on the number
    ok, _ = SC.run(repo, Script(choose=["api", "kokoro+piper"], yes=[True, False], ask=app_answers()), make_deps(check_keys=lambda env: []))
    assert ok is True and env_of(repo)["WHATSAPP_TO"] == PHONE_NO
    assert "whatsapp" in (repo / "setup" / "profiles.txt").read_text()
    SC.run(repo, Script(choose=["api", "kokoro+piper"], yes=[True, False, False], ask=app_answers()), make_deps(check_keys=lambda env: []))
    assert "WHATSAPP_TO" not in env_of(repo)
    assert "whatsapp" not in (repo / "setup" / "profiles.txt").read_text()


def test_rerun_keeps_tailscale_and_folders_set_up_in_the_browser_form(repo):
    W.apply(repo, {"openrouter_key": KEY, "use_tailscale": "1", "ts_authkey": "tskey-auth-abc", "ts_hostname": "tutor-pc",
                   "obsidian_dir": "C:\\Users\\you\\Documents\\TutorNotes", "backup_dir": "D:\\Backups\\tutor"})
    ok, _ = SC.run(repo, Script(choose=["api", "kokoro+piper"], yes=[True, False], ask=app_answers()), make_deps(check_keys=lambda env: []))
    assert ok is True
    env = env_of(repo)
    assert env["TS_AUTHKEY"] == "tskey-auth-abc" and env["TS_HOSTNAME"] == "tutor-pc"
    assert env["OBSIDIAN_TUTOR_DIR"] == "C:\\Users\\you\\Documents\\TutorNotes" and env["BACKUP_DIR"] == "D:\\Backups\\tutor"
    assert "tailscale" in (repo / "setup" / "profiles.txt").read_text()
