import datetime as dt
import json
import subprocess
from pathlib import Path
import pytest
from tutor.lesson_writer import write_lesson
from tutor.llm import LLM
from tutor.providers.claude_cli import _flatten, run_claude_cli
from tutor.pack import load_pack
from tutor.store import Store
from tutor.setup_core import apply, check_keys, read_env

PACKS = Path(__file__).resolve().parents[3] / "packs"


class P:
    def __init__(self, out, code=0, err=""):
        self.stdout, self.returncode, self.stderr = json.dumps(out), code, err


def test_flatten_system_and_history():
    s, p = _flatten([{"role": "system", "content": "SOUL"}, {"role": "user", "content": "hi"},
                     {"role": "assistant", "content": "hello"}, {"role": "user", "content": "what is CIA?"}])
    assert s == "SOUL" and "Student: hi" in p and "Tutor: hello" in p and p.endswith("what is CIA?")
    with pytest.raises(ValueError):
        _flatten([{"role": "user", "content": [{"type": "image_url"}]}])


def test_cli_call_is_isolated_and_toolless(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-oat01-x")
    monkeypatch.setenv("OPENROUTER_API_KEY", "should-not-leak")
    seen = {}

    def runner(cmd, **kw):
        seen.update(cmd=cmd, **kw)
        return P({"result": "lesson text", "is_error": False})
    out = run_claude_cli([{"role": "system", "content": "SOUL"}, {"role": "user", "content": "write"}], "sonnet", runner=runner)
    c = seen["cmd"]
    assert out["result"] == "lesson text"
    assert c[c.index("--tools") + 1] == "" and c[c.index("--model") + 1] == "sonnet"
    assert c[c.index("--system-prompt") + 1] == "SOUL" and seen["input"] == "write"
    assert "--setting-sources" in c and "--no-session-persistence" in c
    assert set(seen["env"]) == {"PATH", "HOME", "CLAUDE_CODE_OAUTH_TOKEN", "DISABLE_AUTOUPDATER", "DISABLE_TELEMETRY"}
    assert seen["cwd"] == seen["env"]["HOME"]          # empty temp dir: no CLAUDE.md or project settings


def test_cli_errors_are_clear(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "t")
    with pytest.raises(RuntimeError, match="limit reached"):
        run_claude_cli([{"role": "user", "content": "x"}], "sonnet",
                       runner=lambda *a, **k: P({"result": "Usage limit reached", "is_error": True}, 1))
    def slow(*a, **k):
        raise subprocess.TimeoutExpired("claude", 1)
    with pytest.raises(RuntimeError, match="timed out"):
        run_claude_cli([{"role": "user", "content": "x"}], "sonnet", runner=slow)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN")
    with pytest.raises(RuntimeError, match="setup-token"):
        run_claude_cli([{"role": "user", "content": "x"}], "sonnet", runner=slow)


def test_subscription_writes_lesson_without_openrouter_or_cap(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "claude-cli")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    calls = []
    def cli(messages, model, timeout=300):
        calls.append(model)
        return {"result": "# Lesson\\n```quiz\\n[]\\n```"}
    store = Store(tmp_path / "t.db")
    out = write_lesson(load_pack(PACKS, "security-plus-sy0-701"), store, tmp_path, dt.date(2026, 10, 6),
                       llm=LLM(store, tmp_path, cli=cli))
    # Two rejected plans, then the Markdown lesson: an empty quiz is retried once, then replaced by a backup quiz.
    assert calls == ["sonnet"] * 5 and "# Lesson" in out.read_text() and "```quiz" in out.read_text()
    assert store.month_cost_usd(dt.date.today().strftime("%Y-%m")) == 0.0


def test_wizard_subscription_provider(tmp_path):
    apply(tmp_path, {"llm_provider": "claude-cli", "claude_token": "sk-ant-oat01-abc"})
    env = read_env(tmp_path / ".env")
    assert env["LLM_PROVIDER"] == "claude-cli" and env["CLAUDE_CODE_OAUTH_TOKEN"] == "sk-ant-oat01-abc"
    apply(tmp_path, {"llm_provider": "claude-cli"})              # re-run keeps the token
    assert read_env(tmp_path / ".env")["CLAUDE_CODE_OAUTH_TOKEN"] == "sk-ant-oat01-abc"
    with pytest.raises(ValueError):
        apply(tmp_path / "b", {"llm_provider": "claude-cli"})   # no token at all
    res = {c["name"]: c for c in check_keys(env, cli=lambda m, model, t: {"result": "OK"})}
    assert res["Claude subscription"]["ok"] and "OpenRouter key" not in res
