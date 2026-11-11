"""The WhatsApp messenger model: a free OpenRouter model that has to repeat each reminder word for word."""
import json

from test_setup_cli import KEY, PHONE_NO, Script, app_answers, env_of, make_deps, repo  # noqa: F401  (repo is a fixture)
from tutor import setup_cli as SC
from tutor import setup_core as W
from tutor.llm import LLM
from tutor.notify import RELAY_INSTRUCTION, OpenClawHook
from tutor.store import Store

SAMPLE = W.RELAY_SAMPLE


def listing():
    def m(mid, ctx=131072, created=1, **extra):
        return {"id": mid, "context_length": ctx, "created": created, **extra}
    return [
        m("deepseek/deepseek-r1:free", created=9),                      # thinks out loud: wrong for "repeat exactly"
        m("qwen/qwen3-coder:free", created=9),                          # code model
        m("qwen/qwen2.5-vl-72b-instruct:free"),                         # vision
        m("tiny/model-3b:free", created=9),
        m("google/gemma-3-27b-it:free", ctx=96000, created=5),
        m("meta-llama/llama-3.3-70b-instruct:free", created=3),
        m("openai/gpt-oss-120b:free", created=8),
        m("mistralai/mistral-small-3.2-24b-instruct:free", created=6),
        m("short/ctx-70b:free", ctx=8000),                              # too little context
        m("paid/big-405b", pricing={"prompt": "0.001", "completion": "0.002"}),
    ]


def test_ranking_is_free_text_only_instruct_models_biggest_first():
    assert W.rank_free_models(listing()) == [
        "openai/gpt-oss-120b:free", "meta-llama/llama-3.3-70b-instruct:free", "google/gemma-3-27b-it:free",
        "mistralai/mistral-small-3.2-24b-instruct:free", "tiny/model-3b:free"]


def test_size_is_read_from_the_id():
    assert W._size_b("qwen/qwen3-235b-a22b:free") == 235 and W._size_b("meta/llama-3.3-70b-instruct") == 70
    assert W._size_b("google/gemma-3-4b-it") == 4 and W._size_b("x/mystery:free") == 30


def test_relay_ok_forgives_quotes_and_whitespace_but_nothing_else():
    assert W.relay_ok(SAMPLE, SAMPLE) and W.relay_ok(f'  "{SAMPLE}"\n', SAMPLE) and W.relay_ok(f"`{SAMPLE}`", SAMPLE)
    assert not W.relay_ok(f"Sure! {SAMPLE}", SAMPLE)                       # extra words
    assert not W.relay_ok(f"<think>hm</think>{SAMPLE}", SAMPLE)            # leaked reasoning
    assert not W.relay_ok(SAMPLE.replace("19:00", "20:00"), SAMPLE) and not W.relay_ok("", SAMPLE)


def test_pick_takes_the_first_that_passes_plus_two_backups_and_skips_failures():
    replies = {"a": "I'd be happy to! " + SAMPLE, "b": SAMPLE, "c": "ERR", "d": f'"{SAMPLE}"', "e": SAMPLE, "f": SAMPLE}
    tried = []

    def probe(model):
        tried.append(model)
        if replies[model] == "ERR":
            raise RuntimeError("429 rate limited")
        return replies[model]
    passed, failed = W.pick_relay_models(list("abcdef"), probe)
    assert passed == ["b", "d", "e"] and failed == ["a", "c"] and tried == list("abcde")   # stops once it has three


def test_pick_gives_up_after_max_probes():
    seen = []
    passed, failed = W.pick_relay_models([f"m{i}" for i in range(20)], lambda m: seen.append(m) or "no", max_probes=5)
    assert passed == [] and len(failed) == 5 == len(seen)


def test_probe_goes_through_the_gateway_to_openrouter_even_on_a_claude_subscription(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "claude-cli")                      # lessons use the subscription
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    sent = {}

    def post(body, key):
        sent.update(body=body, key=key)
        return {"choices": [{"message": {"content": SAMPLE}}], "usage": {"cost": 0}}
    store = Store(tmp_path / "progress.db")
    out = LLM(store, tmp_path, post=post, cli=lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not use the CLI")))
    monkeypatch.setenv("OPENROUTER_API_KEY", KEY)
    assert out.complete([{"role": "user", "content": RELAY_INSTRUCTION + SAMPLE}], "x/free:free", "probe") == SAMPLE
    assert sent["body"]["model"] == "x/free:free" and sent["body"]["max_tokens"] <= 200 and sent["key"] == KEY


def test_probe_relay_model_restores_the_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    post = lambda body, key: {"choices": [{"message": {"content": SAMPLE}}], "usage": {"cost": 0}}  # noqa: E731
    assert W.probe_relay_model("x:free", KEY, tmp_path, post=post) == SAMPLE
    import os
    assert "OPENROUTER_API_KEY" not in os.environ                          # the key was only set for the call


def test_the_notifier_uses_the_instruction_the_models_were_tested_with(monkeypatch):
    seen = {}

    class R:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"ok": true}'
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=0: seen.update(body=json.loads(req.data)) or R())
    OpenClawHook("http://gw", "tok", "+447700900123").send(SAMPLE)
    assert seen["body"]["message"] == RELAY_INSTRUCTION + SAMPLE


def run_setup(repo, probe, **over):
    con = Script(choose=["pro", "kokoro+piper"], yes=[False, True], ask=app_answers() + [PHONE_NO], secret=["tok", KEY])
    ok, checks = SC.run(repo, con, make_deps(fetch_models=lambda key: listing(), probe_relay=probe, **over))
    return ok, checks, con


def test_setup_picks_the_best_free_model_that_passes_and_writes_backups(repo):
    good = {"meta-llama/llama-3.3-70b-instruct:free", "google/gemma-3-27b-it:free", "mistralai/mistral-small-3.2-24b-instruct:free"}
    ok, checks, con = run_setup(repo, lambda m, key, data: SAMPLE if m in good else "Sure, here you go! " + SAMPLE)
    assert ok is True
    env = env_of(repo)
    assert env["MODEL_CHEAP"] == "meta-llama/llama-3.3-70b-instruct:free"                       # gpt-oss was biggest but chatty
    assert env["OPENCLAW_FALLBACK_MODELS"] == "google/gemma-3-27b-it:free,mistralai/mistral-small-3.2-24b-instruct:free"
    cfg = json.loads((repo / "openclaw" / "config" / "openclaw.json").read_text())
    assert cfg["agents"]["defaults"]["model"] == {
        "primary": "openrouter/meta-llama/llama-3.3-70b-instruct:free",
        "fallbacks": ["openrouter/google/gemma-3-27b-it:free", "openrouter/mistralai/mistral-small-3.2-24b-instruct:free"]}
    assert any(c.group == "WhatsApp" and c.status == "ok" and "meta-llama/llama-3.3-70b-instruct:free (free)" in c.detail for c in checks)
    assert "gpt-oss-120b:free: did not repeat it exactly" in con.output and "llama-3.3-70b-instruct:free: ok" in con.output
    assert KEY not in con.output


def test_setup_keeps_going_when_no_free_model_passes(repo):
    ok, checks, con = run_setup(repo, lambda m, key, data: "I cannot do that")
    assert ok is True and env_of(repo)["WHATSAPP_TO"] == PHONE_NO
    assert any(c.group == "WhatsApp" and "none of the top free models" in c.detail for c in checks)


def test_a_failing_probe_never_stops_setup(repo):
    def boom(m, key, data):
        raise OSError("network down")
    ok, checks, _ = run_setup(repo, boom)
    assert ok is True and any("none of the top free models" in c.detail for c in checks)


def test_a_rerun_picks_again_and_replaces_old_backups(repo):
    run_setup(repo, lambda m, key, data: SAMPLE)
    first = env_of(repo)
    assert first["MODEL_CHEAP"] == "openai/gpt-oss-120b:free" and first["OPENCLAW_FALLBACK_MODELS"].count(",") == 1
    con = Script(choose=["pro", "kokoro+piper"], yes=[False, True], ask=app_answers() + [PHONE_NO], secret=["tok"])
    ok, _ = SC.run(repo, con, make_deps(fetch_models=lambda key: [m for m in listing() if "gpt-oss" not in m["id"]],
                                        probe_relay=lambda m, key, data: SAMPLE))
    assert ok is True and env_of(repo)["MODEL_CHEAP"] == "meta-llama/llama-3.3-70b-instruct:free"


def test_a_free_messenger_model_adds_nothing_to_the_spend(tmp_path, monkeypatch):
    from tutor.scheduler import _send
    import datetime as dt

    class N:
        name = "openclaw"
        def send(self, text): return True
    store = Store(tmp_path / "p.db")
    settings = {"max_messages_per_day": 8, "quiet_start": "22:00", "quiet_end": "07:00"}
    monkeypatch.setenv("MODEL_CHEAP", "meta-llama/llama-3.3-70b-instruct:free")
    now = dt.datetime(2026, 10, 8, 12, 0)
    assert _send(store, N(), settings, now, "reminder", "hi")
    assert store.month_cost_usd("2026-10") == 0
    monkeypatch.setenv("MODEL_CHEAP", "paid/model")
    assert _send(store, N(), settings, now, "late", "hi") and store.month_cost_usd("2026-10") > 0
