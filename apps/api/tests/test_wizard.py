import datetime as dt
import json
import pytest
from tutor.settings import Settings
from tutor.setup_core import apply, check_keys, read_env, recommend, serve_json

MODELS = [
    {"id": "anthropic/claude-sonnet-4", "created": 100, "pricing": {"prompt": "0.000003", "completion": "0.000015"}},
    {"id": "anthropic/claude-sonnet-5", "created": 200, "pricing": {"prompt": "0.000003", "completion": "0.000015"}},
    {"id": "some/model:free", "created": 50, "context_length": 128000, "pricing": {"prompt": "0", "completion": "0"}},
    {"id": "tiny/model:free", "created": 60, "context_length": 8000},
]
FULL = {"name": "Kyle", "openrouter_key": "sk-or-v1-abc", "lesson_time": "08:30", "tone": "strict",
        "max_messages": "8", "rest_days": "sat,sun", "use_whatsapp": "on", "whatsapp_to": "+447700900000",
        "use_tailscale": "on", "ts_authkey": "tskey-auth-abc123", "ts_hostname": "teacher-tool",
        "obsidian_dir": r"C:\Users\you\Documents\TutorNotes", "backup_dir": r"D:\Backups\teacher-tool",
        "gemini_key": "AIzaTest", "voice_provider": "gemini", "timezone": "Europe/London"}


def test_recommend_strong_and_free():
    r = recommend(MODELS)
    assert r["MODEL_TEACH"] == "anthropic/claude-sonnet-5" == r["MODEL_MARK"]
    assert r["MODEL_CHEAP"] == "some/model:free"
    assert recommend([])["MODEL_TEACH"] == ""


def test_full_setup_writes_everything(tmp_path):
    res = apply(tmp_path, FULL, recommend(MODELS))
    env = read_env(tmp_path / ".env")
    assert env["TUTOR_TOKEN"] == res["token"] and len(res["token"]) >= 40
    assert env["MODEL_TEACH"] == "anthropic/claude-sonnet-5"
    assert env["OBSIDIAN_TUTOR_DIR"] == r"C:\Users\you\Documents\TutorNotes"   # quoted path round-trips
    assert "OBSIDIAN_TUTOR_DIR='C:\\Users\\you\\Documents\\TutorNotes'" in (tmp_path / ".env").read_text()
    assert env["WHATSAPP_TO"] == "+447700900000" and env["OPENCLAW_HOOK_URL"] == "http://openclaw-gateway:18789"
    assert res["profiles"] == ["whatsapp", "tailscale"]
    assert (tmp_path / "setup" / "profiles.txt").read_text().split() == ["whatsapp", "tailscale"]
    oc = json.loads((tmp_path / "openclaw" / "config" / "openclaw.json").read_text())
    assert oc["hooks"]["token"] == env["OPENCLAW_HOOK_TOKEN"] != env["TUTOR_TOKEN"]
    assert oc["channels"]["whatsapp"] == {"dmPolicy": "allowlist", "allowFrom": ["+447700900000"], "selfChatMode": True,
                                          "groupPolicy": "disabled"}
    assert oc["tools"]["profile"] == "messaging"
    assert oc["agents"]["defaults"]["model"]["primary"] == "openrouter/some/model:free"
    ocenv = read_env(tmp_path / "openclaw" / "openclaw.env")
    assert ocenv["OPENCLAW_GATEWAY_TOKEN"] not in (env["TUTOR_TOKEN"], env["OPENCLAW_HOOK_TOKEN"])
    assert "TUTOR_TOKEN" not in ocenv                     # OpenClaw never sees tutor secrets
    assert "sk-or" not in (tmp_path / "openclaw" / "config" / "openclaw.json").read_text()
    assert (tmp_path / "openclaw" / "workspace" / "SOUL.md").exists()
    assert json.loads((tmp_path / "tailscale" / "serve.json").read_text())["Web"]["${TS_CERT_DOMAIN}:443"]
    assert Settings(tmp_path / "data").get()["tone"] == "strict"


def test_rerun_keeps_secrets_and_tokens(tmp_path):
    first = apply(tmp_path, FULL, recommend(MODELS))
    env1 = read_env(tmp_path / ".env")
    again = dict(FULL, openrouter_key="", ts_authkey="", gemini_key="", name="")
    second = apply(tmp_path, again)
    env2 = read_env(tmp_path / ".env")
    assert second["token"] == first["token"]
    for k in ("OPENROUTER_API_KEY", "TS_AUTHKEY", "GEMINI_API_KEY", "OPENCLAW_HOOK_TOKEN", "MODEL_TEACH"):
        assert env1[k] == env2[k]
    assert "Kyle" in (tmp_path / "data" / "context.md").read_text()   # blank name keeps profile


def test_rerun_keeps_tutor_port(tmp_path):
    apply(tmp_path, {"openrouter_key": "k"})
    with open(tmp_path / ".env", "a") as f:
        f.write("TUTOR_PORT=8081\n")
    apply(tmp_path, {})
    assert read_env(tmp_path / ".env")["TUTOR_PORT"] == "8081"


def test_minimal_setup_no_optional_services(tmp_path):
    res = apply(tmp_path, {"openrouter_key": "sk-or-v1-x"})
    assert res["profiles"] == [] and not (tmp_path / "openclaw").exists()
    assert "WHATSAPP_TO" not in read_env(tmp_path / ".env")


@pytest.mark.parametrize("bad", [
    {"openrouter_key": "abc\nTUTOR_TOKEN=x"},
    {"lesson_time": "9am"},
    {"use_whatsapp": "on", "whatsapp_to": "07700900000"},
    {"use_tailscale": "on"},
    {"obsidian_dir": "relative/path"},
    {"backup_dir": "C:\\it's"},
    {"ts_hostname": "Bad Name!"},
    {"voice_provider": "skype"},
])
def test_rejects_bad_input_and_writes_nothing(tmp_path, bad):
    with pytest.raises(ValueError):
        apply(tmp_path, bad)
    assert not (tmp_path / ".env").exists()


def test_check_keys_reports_without_raising():
    def fake_get(url, headers=None, timeout=20):
        if "openrouter" in url:
            return {"data": {"limit": 20}}
        raise OSError("network down")
    res = {c["name"]: c for c in check_keys({"OPENROUTER_API_KEY": "k", "GEMINI_API_KEY": "g", "TS_AUTHKEY": "bad"}, get=fake_get)}
    assert res["OpenRouter key"]["ok"] and "20" in res["OpenRouter key"]["detail"]
    assert not res["Gemini key (voice)"]["ok"] and not res["Tailscale auth key"]["ok"]
    assert not check_keys({})[0]["ok"]


def test_form_keeps_typed_values_on_error_but_not_secrets(tmp_path):
    from tutor.wizard import _form_page
    page = _form_page(tmp_path, "err", {"lesson_time": "07:15", "whatsapp_to": "0770", "use_whatsapp": "on",
                                        "openrouter_key": "sk-or-secret", "obsidian_dir": "rel"})
    assert 'value="07:15"' in page and 'value="0770"' in page and "sk-or-secret" not in page


# ---------- the browser form only answers its owner ----------

def _serve_form(tmp_path, key="the-one-time-key"):
    import os
    import socket
    import threading
    import time
    from tutor import wizard
    (tmp_path / "data").mkdir()
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    (tmp_path / ".env").write_text("TUTOR_TOKEN=existing-secret-token\nWHATSAPP_TO=+447700900123\nNTFY_URL=https://ntfy.sh/private-topic\n")
    os.environ["TUTOR_PACKS_DIR"] = str(__import__("pathlib").Path(__file__).resolve().parents[3] / "packs")
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    threading.Thread(target=wizard.run, args=(tmp_path, "127.0.0.1", port, key), daemon=True).start()
    time.sleep(0.5)
    return f"http://127.0.0.1:{port}/"


def _fetch(url, data=None, headers=None):
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, data, headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_form_needs_the_key_and_a_local_host(tmp_path):
    base = _serve_form(tmp_path)
    assert _fetch(base)[0] == 403                                          # no key
    assert _fetch(base + "?k=wrong")[0] == 403
    code, page = _fetch(base + "?k=the-one-time-key")
    assert code == 200 and 'name=k value="the-one-time-key"' in page
    assert "private-topic" not in _fetch(base)[1]                          # nothing about the saved setup without the key
    assert _fetch(base + "?k=the-one-time-key", headers={"Host": "evil.example"})[0] == 403   # DNS rebinding


def test_a_post_from_another_site_changes_nothing(tmp_path):
    import urllib.parse
    base = _serve_form(tmp_path)
    before = (tmp_path / ".env").read_text()
    body = urllib.parse.urlencode({"use_whatsapp": "on", "whatsapp_to": "+447700900666", "ntfy_url": "https://attacker.example/x"}).encode()
    for headers in ({"Origin": "https://evil.example"}, {"Origin": "null"}, {"Host": "evil.example"}, {}):   # {}: no key
        assert _fetch(base, body, headers)[0] == 403
    with_key = urllib.parse.urlencode({"k": "wrong", "whatsapp_to": "+447700900666"}).encode()
    assert _fetch(base, with_key, {"Origin": "http://127.0.0.1:8090"})[0] == 403
    assert (tmp_path / ".env").read_text() == before


def test_the_real_form_still_saves_and_only_then_stops(tmp_path):
    import urllib.parse
    base = _serve_form(tmp_path)
    body = urllib.parse.urlencode({"k": "the-one-time-key", "name": "Kyle", "lesson_time": "08:30", "tone": "firm",
                                   "max_messages": "8", "rest_days": "sat,sun", "timezone": "Europe/London", "cap_gbp": "40"}).encode()
    code, page = _fetch(base, body, {"Origin": "http://localhost:8090", "Host": "localhost:8090"})
    assert code == 200 and "Saved" in page and "existing-secret-token" in page


def test_local_names_and_the_key_check():
    from tutor.wizard import _local, allowed
    assert all(_local(x) for x in ("127.0.0.1:8090", "localhost", "http://localhost:8090", "[::1]:8090", "http://[::1]:8090/"))
    assert not any(_local(x) for x in ("", "null", "evil.example", "127.0.0.1.evil.example", "http://evil.example:8090", "localhost.evil.com"))
    assert allowed({"Host": "127.0.0.1:1"}, "k", "k") and not allowed({"Host": "127.0.0.1:1"}, "k", "")
    assert not allowed({"Host": "127.0.0.1:1", "Origin": "http://a.b"}, "k", "k")
