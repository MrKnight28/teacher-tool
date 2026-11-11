import base64, datetime as dt, io, json, logging, random, shutil, struct, subprocess, threading, urllib.request, urllib.error
from http.server import ThreadingHTTPServer
from pathlib import Path
import pytest
from tutor import llm as L
from tutor import timing as T
from tutor import tts as TT
from tutor import voice as V
from tutor.providers import gemini, http, openai
from tutor.bench import voicebench as VB
from tutor.pack import load_pack
from tutor.server import App, make_handler
from tutor.settings import Settings
from tutor.store import Store

PACKS = Path(__file__).resolve().parents[3] / "packs"
UI = Path(__file__).resolve().parents[1] / "tutor" / "ui.html"
SECRET_Q = "SECRETQUESTION about the fuse"
SECRET_A = "SECRETANSWER fuses protect circuits"
SECRET_LESSON = "SECRETLESSON text"


def test_wav_header_matches_pcm_length():
    pcm = b"\x00\x01" * 100
    wav = V.wav_from_pcm(pcm, rate=24000)
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"
    assert struct.unpack("<I", wav[40:44])[0] == len(pcm)
    assert struct.unpack("<I", wav[24:28])[0] == 24000  # sample rate
    assert wav[44:] == pcm


def test_multipart_carries_fields_and_file():
    body, ctype = http.multipart({"model": "whisper-1"}, "file", "q.webm", b"AUDIO", "audio/webm")
    boundary = ctype.split("boundary=")[1].encode()
    assert ctype.startswith("multipart/form-data")
    assert b'name="model"\r\n\r\nwhisper-1' in body
    assert b'filename="q.webm"' in body and b"Content-Type: audio/webm" in body and b"AUDIO" in body
    assert body.endswith(b"--" + boundary + b"--\r\n")


def test_bundled_benchmark_clip_is_five_seconds():
    wav = V.BENCH_CLIP.read_bytes()
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"
    rate = struct.unpack("<I", wav[24:28])[0]
    data_len = struct.unpack("<I", wav[40:44])[0]
    assert rate == 16000 and data_len / (rate * 2) == 5.0


# ---------- speech-to-text ----------

def test_local_transcription_is_the_default_and_free(monkeypatch):
    monkeypatch.delenv("TRANSCRIBE", raising=False)
    monkeypatch.delenv("WHISPER_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-never-be-used")
    seen = {}

    def fake_local(audio, name=None, duration_ms=None, timing=None, prompt=None):
        seen.update(audio=audio, name=name)
        return "  what is a fuse?  "

    monkeypatch.setattr(V, "_local_transcribe", fake_local)
    assert V.transcribe(b"x" * 2000, "audio/webm") == "what is a fuse?"
    assert seen["audio"] == b"x" * 2000
    assert V.transcribe_cost() == 0.0
    assert V.transcribe_label() == "local:whisper-base.en"


def test_local_transcription_errors_are_plain(monkeypatch):
    monkeypatch.delenv("TRANSCRIBE", raising=False)

    def no_model(*a, **k):
        raise RuntimeError("could not load the speech model; it downloads once")

    monkeypatch.setattr(V, "_local_transcribe", no_model)
    with pytest.raises(RuntimeError, match="downloads once"):
        V.transcribe(b"x" * 100, "audio/webm")


class FakeModel:
    def __init__(self):
        self.calls = []

    def transcribe(self, samples, **kw):
        self.calls.append(kw)
        return iter([]), None


def test_short_clips_skip_the_vad_filter(monkeypatch):
    model = FakeModel()
    monkeypatch.setattr(V, "_load_model", lambda name=None: (model, 0.0))
    wav = V.BENCH_CLIP.read_bytes()  # a real WAV, so the decode step runs for real
    t = {}
    V._local_transcribe(wav, "base.en", 2000, t)
    assert model.calls[-1]["vad_filter"] is False and t["vad"] == 0
    V._local_transcribe(wav, "base.en", 5000, t)
    assert model.calls[-1]["vad_filter"] is True
    assert t["audio_s"] == 5.0 and t["model"] == "local:whisper-base.en"
    assert {"decode_ms", "model_wait_ms", "transcribe_ms"} <= set(t)


def test_transcribe_openai_sends_raw_audio_and_is_labelled(monkeypatch):
    monkeypatch.setenv("TRANSCRIBE", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    seen = {}

    def fake_post(url, body, headers, timeout=90):
        seen.update(url=url, headers=headers, body=body)
        return {"text": "  what is a fuse?  "}

    assert V.transcribe(b"x" * 2000, "audio/webm;codecs=opus", post=fake_post) == "what is a fuse?"
    assert seen["url"] == openai.TRANSCRIBE_URL
    assert seen["headers"]["Authorization"] == "Bearer sk-test"
    assert b"whisper-1" in seen["body"]
    assert V.transcribe_label() == "openai:whisper-1" and V.transcribe_cost() > 0


def test_openai_mode_needs_key_and_valid_audio(monkeypatch):
    monkeypatch.setenv("TRANSCRIBE", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        V.transcribe(b"x" * 100, "audio/webm")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    with pytest.raises(ValueError, match="too long"):
        V.transcribe(b"x" * (V.MAX_AUDIO_BYTES + 1), "audio/webm")
    with pytest.raises(ValueError, match="could not be read"):
        V.transcribe(b"", "audio/webm")


# ---------- Gemini speech ----------

def test_speak_wraps_gemini_pcm_as_wav(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g-test")
    pcm = b"\x10\x00" * 50
    reply = {"candidates": [{"content": {"parts": [{"inlineData": {
        "mimeType": "audio/L16;codec=pcm;rate=24000", "data": base64.b64encode(pcm).decode()}}]}}]}
    timing = {}

    def fake_post(url, body, headers, timeout=90):
        assert "generateContent" in url and headers["x-goog-api-key"] == "g-test"
        assert b"responseModalities" in body and b"AUDIO" in body
        return reply

    wav = V.speak("A fuse breaks the circuit.", post=fake_post, timing=timing)
    assert wav[:4] == b"RIFF" and wav[44:] == pcm
    assert "gemini_ms" in timing and timing["gemini_req_bytes"] > 0


def test_speak_errors_are_plain(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="Gemini key"):
        V.speak("hi")
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    with pytest.raises(RuntimeError, match="no audio"):
        V.speak("hi", post=lambda *a, **k: {"candidates": []})
    with pytest.raises(ValueError, match="nothing"):
        V.speak("   ")


def test_gemini_free_tier_costs_nothing_and_paid_is_estimated():
    assert V.speak_cost("x" * 1000) == 0.0
    assert V.speak_cost("x" * 1000, "free") == 0.0
    assert V.speak_cost("x" * 1000, "paid") > V.speak_cost("x" * 10, "paid") > 0


def test_status_reports_the_voice_choice(monkeypatch):
    monkeypatch.delenv("TRANSCRIBE", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    s = V.status({"whisper_model": "small.en", "lesson_voice": "gemini", "gemini_billing": "free"})
    assert s["transcribe"] == "local" and s["speak"] is False and "model_ready" in s
    assert s["whisper_model"] == "small.en" and s["lesson_voice"] == "gemini" and s["gemini_billing"] == "free"
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    assert V.status()["speak"] is True


def test_preload_never_raises(monkeypatch):
    monkeypatch.setenv("TRANSCRIBE", "openai")
    V.preload()  # openai mode: nothing to load

    def broken(name=None):
        raise RuntimeError("no model")

    monkeypatch.delenv("TRANSCRIBE", raising=False)
    monkeypatch.setattr(V, "_load_model", broken)
    V.preload()


def test_voice_settings_validate(tmp_path):
    s = Settings(tmp_path)
    assert s.get()["lesson_voice"] == "kokoro" and s.get()["gemini_billing"] == "free"
    assert s.get()["whisper_model"] == "base.en"
    s.update({"whisper_model": "small.en", "lesson_voice": "gemini", "gemini_billing": "paid"})
    assert Settings(tmp_path).get()["gemini_billing"] == "paid"
    for bad in ({"whisper_model": "large-v3"}, {"lesson_voice": "robot"}, {"gemini_billing": "card"}):
        with pytest.raises(ValueError):
            s.update(bad)


# ---------- sentences for streaming ----------

def test_sentence_splitter_waits_for_a_finished_sentence():
    s = V.SentenceSplitter()
    got = []
    for piece in ["Hello the fi", "rewall stops traffic. It ", "is fast", "? Yes."]:
        got += s.feed(piece)
    assert got == ["Hello the firewall stops traffic.", "It is fast?"]
    assert s.flush() == ["Yes."]


SPLIT_SAMPLE = 'A firewall stops traffic. Is it 3.5 GHz? He said "stop." Then it stopped!  Done'
SPLIT_EXPECTED = ["A firewall stops traffic.", "Is it 3.5 GHz?", 'He said "stop."', "Then it stopped!", "Done"]


def test_sentence_split_matches_the_server_rule():
    assert V.split_sentences(SPLIT_SAMPLE) == SPLIT_EXPECTED


# ---------- timing: numbers and step names only ----------

def test_timing_refuses_anything_but_numbers_and_labels():
    with pytest.raises(ValueError):
        T.record("ask", text_chars="hello")
    with pytest.raises(ValueError):
        T.record("ask", question=1.0)
    with pytest.raises(ValueError):
        T.record("ask", model="fuses are good")
    with pytest.raises(ValueError):
        T.record("nonsense")


def test_timing_log_never_holds_question_answer_or_lesson(tmp_path, caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="tutor.timing")
    monkeypatch.setenv("LLM_PROVIDER", "claude-cli")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "t")
    day = dt.date(2026, 10, 6)
    (tmp_path / "lessons").mkdir()
    (tmp_path / "lessons" / f"{day}.md").write_text(f"## Fuses\n{SECRET_LESSON}\n")
    store = Store(tmp_path / "t.db")
    app = App(load_pack(PACKS, "security-plus-sy0-701"), store, tmp_path, token=None)

    def fake_stream(messages, model, timeout=300, popen=None, timing=None):
        if timing is not None:
            timing.update(first_ms=5, claude_ms=9)
        yield SECRET_A + ". More."

    app.llm = L.LLM(store, tmp_path, cli_stream=fake_stream)
    events = list(app.chat_stream(day, SECRET_Q, 120))
    assert events[-1]["type"] == "done"
    app.browser_timing({"kind": "ask", "mic_to_upload_ms": 12.5, "question": SECRET_Q})
    logs = caplog.text
    assert "voice server chat" in logs or "chat" in logs
    assert "first_ms=5" in logs and "reply_chars=" in logs
    for secret in (SECRET_Q, SECRET_A, SECRET_LESSON):
        assert secret not in logs
    assert "mic_to_upload_ms=12.5" in logs


# ---------- Claude CLI streaming ----------

class FakePopen:
    def __init__(self, cmd, lines, rc=0, err=""):
        self.cmd = cmd
        self.stdin = io.StringIO()
        self.stdout = iter(lines)
        self.stderr = io.StringIO(err)
        self.returncode = rc
        self.killed = False

    def poll(self):
        return self.returncode

    def wait(self):
        return self.returncode

    def kill(self):
        self.killed = True


def _delta(text):
    return json.dumps({"type": "stream_event", "event": {"type": "content_block_delta",
                                                       "delta": {"type": "text_delta", "text": text}}}) + "\n"


STREAM = [
    json.dumps({"type": "system", "subtype": "init"}) + "\n",
    _delta("Hel"),
    _delta("lo."),
    json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Hello."}]}}) + "\n",
    json.dumps({"type": "result", "is_error": False, "result": "Hello."}) + "\n",
]
MSGS = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]


def test_claude_stream_yields_text_as_it_is_written(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "t")
    made = {}

    def spawn(cmd, **kw):
        made.update(cmd=cmd, kw=kw)
        return FakePopen(cmd, STREAM)

    timing = {}
    pieces = list(L.run_claude_cli_stream(MSGS, "haiku", popen=spawn, timing=timing))
    assert pieces == ["Hel", "lo."]
    cmd = made["cmd"]
    assert "stream-json" in cmd and "--include-partial-messages" in cmd and "--verbose" in cmd
    assert cmd[cmd.index("--tools") + 1] == "" and "--strict-mcp-config" in cmd and "--no-session-persistence" in cmd
    assert made["kw"]["env"]["CLAUDE_CODE_OAUTH_TOKEN"] == "t"
    assert "first_ms" in timing and "claude_ms" in timing


def test_claude_stream_falls_back_to_the_whole_reply(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "t")
    lines = [json.dumps({"type": "result", "is_error": False, "result": "Whole reply."}) + "\n"]
    assert list(L.run_claude_cli_stream(MSGS, "haiku", popen=lambda cmd, **kw: FakePopen(cmd, lines))) == ["Whole reply."]


def test_claude_stream_reports_failures_plainly(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "t")
    lines = [json.dumps({"type": "result", "is_error": True, "result": "rate limited"}) + "\n"]
    with pytest.raises(RuntimeError, match="failed: rate limited"):
        list(L.run_claude_cli_stream(MSGS, "haiku", popen=lambda cmd, **kw: FakePopen(cmd, lines, rc=1)))


# ---------- state machine and sentence rule, run under Node against the shipped page ----------

def _node(script: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    core = UI.read_text().split("/* @@voice-core */")[1].split("/* @@end-voice-core */")[0]
    p = subprocess.run([node, "-e", core + "\n" + script], capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def test_state_machine_follows_its_transitions():
    out = _node(r"""
    const r = {};
    // Read is speaking; the student holds the mic. The new action supersedes the old speech.
    const m = createMachine();
    const read = m.begin(); m.to('idle', read); m.to('speaking', read);
    const ask = m.begin();
    r.speaking_then_recording = m.to('recording', ask) && m.state === 'recording';
    r.stale_read_cannot_resume = m.to('speaking', read) === false && m.state === 'recording';
    r.stale_read_cannot_idle = m.to('idle', read) === false;
    // A stale answer can't change the state after a newer question has started.
    const q = createMachine(); const a1 = q.begin(); q.to('idle', a1); q.to('thinking', a1);
    const a2 = q.begin();
    r.stale_answer_blocked = q.to('speaking', a1) === false && q.state === 'thinking';
    r.newer_question_proceeds = q.to('idle', a2) === true && q.state === 'idle';
    // Any action can return to idle, from every state.
    const paths = { idle: [], recording: ['recording'], transcribing: ['recording', 'transcribing'],
                    thinking: ['recording', 'transcribing', 'thinking'], speaking: ['recording', 'transcribing', 'thinking', 'speaking'] };
    r.any_state_back_to_idle = Object.entries(paths).every(([s, path]) => {
      const x = createMachine(); const t = x.begin(); x.to('idle', t); path.forEach(p => x.to(p, t));
      return x.state === s && x.to('idle', t) && x.state === 'idle';
    });
    // Moves the table doesn't allow are refused.
    const d = createMachine(); const td = d.begin(); d.to('idle', td); d.to('recording', td);
    r.recording_to_speaking_refused = d.to('speaking', td) === false && d.state === 'recording';
    d.to('transcribing', td);
    r.transcribing_to_recording_refused = d.to('recording', td) === false && d.state === 'transcribing';
    // The view is what the page renders from; say() changes the caption only, and subscribers hear every change.
    const seen = []; const v = createMachine(); v.subscribe(x => seen.push(x.state));
    const tv = v.begin(); v.to('idle', tv); v.say('Hello');
    r.say_changes_caption_only = v.view().caption === 'Hello' && v.state === 'idle';
    r.subscribers_hear_every_change = seen.join(',') === 'idle,idle,idle';
    console.log(JSON.stringify(r));
    """)
    assert all(out.values()), out


def test_browser_sentence_rule_matches_the_server():
    js = _node("console.log(JSON.stringify(splitSentences(" + json.dumps(SPLIT_SAMPLE) + ")))")
    assert js == SPLIT_EXPECTED


# ---------- routes ----------

@pytest.fixture
def served(tmp_path):
    day = dt.date(2026, 10, 6)
    store = Store(tmp_path / "t.db")
    app = App(load_pack(PACKS, "security-plus-sy0-701"), store, tmp_path, token="secret")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield {"base": f"http://127.0.0.1:{srv.server_port}", "store": store, "day": day, "data": tmp_path, "app": app}
    srv.shutdown()


@pytest.fixture
def server(served):
    yield served["base"], served["store"], served["day"]


def call(url, body, tok="secret"):
    req = urllib.request.Request(url, json.dumps(body).encode(),
                                 {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.headers.get("Content-Type"), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type"), e.read()


def post_raw(url, data: bytes, mime="audio/webm", tok="secret"):
    req = urllib.request.Request(url, data, {"Authorization": f"Bearer {tok}", "Content-Type": "application/octet-stream",
                                             "X-Audio-Mime": mime})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def usage(store):
    return store.db.execute("SELECT task, model, cost_usd FROM usage").fetchall()


def test_voice_routes_need_token(server):
    base, _, day = server
    assert call(f"{base}/api/voice/speak", {"date": str(day), "text": "hi"}, tok="wrong")[0] == 401
    assert post_raw(f"{base}/api/voice/transcribe?date={day}", b"AA", tok="wrong")[0] == 401


def test_voice_without_keys_gives_plain_502(server, monkeypatch):
    base, _, day = server
    monkeypatch.setenv("TRANSCRIBE", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    code, body = post_raw(f"{base}/api/voice/transcribe?date={day}", b"x" * 2000)
    assert code == 502 and b"OPENAI_API_KEY" in body
    code, _, body = call(f"{base}/api/voice/speak", {"date": str(day), "text": "hi"})
    assert code == 502 and b"Gemini key" in body


def test_voice_rejects_bad_input(server, monkeypatch):
    base, _, day = server
    monkeypatch.setenv("OPENAI_API_KEY", "sk")
    monkeypatch.setenv("TRANSCRIBE", "openai")
    code, body = post_raw(f"{base}/api/voice/transcribe?date={day}", b"x" * (V.MAX_AUDIO_BYTES + 1))
    assert code == 413
    code, _, _ = call(f"{base}/api/voice/speak", {"date": str(day), "text": "   "})
    assert code == 400


def test_usage_rows_name_the_engine_and_model(served, monkeypatch):
    base, day, store = served["base"], served["day"], served["store"]
    monkeypatch.delenv("TRANSCRIBE", raising=False)
    monkeypatch.delenv("WHISPER_MODEL", raising=False)
    monkeypatch.setattr(V, "_local_transcribe", lambda audio, name=None, duration_ms=None, timing=None, prompt=None: "a fuse")
    code, body = post_raw(f"{base}/api/voice/transcribe?date={day}&ms=4000", b"x" * 3000)
    assert code == 200 and json.loads(body)["text"] == "a fuse"
    assert ("voice question", "local:whisper-base.en", 0.0) in usage(store)

    monkeypatch.setenv("TRANSCRIBE", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("tutor.providers.http.post_json", lambda url, body, headers, timeout=90: {"text": "a fuse"})
    code, body = post_raw(f"{base}/api/voice/transcribe?date={day}", b"x" * 3000)
    assert code == 200
    rows = usage(store)
    assert any(t == "voice question" and m == "openai:whisper-1" and c > 0 for t, m, c in rows)


def test_gemini_speech_is_free_on_the_free_tier(served, monkeypatch):
    base, day, store = served["base"], served["day"], served["store"]
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.delenv("GEMINI_TTS_MODEL", raising=False)
    monkeypatch.setattr("tutor.providers.http.post_json", lambda *a, **k: {"candidates": [{"content": {"parts": [{"inlineData": {
        "data": base64.b64encode(b"\x00\x00" * 10).decode()}}]}}]})
    Settings(served["data"]).update({"gemini_billing": "free"})
    code, ctype, body = call(f"{base}/api/voice/speak", {"date": str(day), "text": "A fuse breaks the circuit."})
    assert code == 200 and ctype == "audio/wav" and body[:4] == b"RIFF"
    assert store.month_cost_usd(day.strftime("%Y-%m")) == 0.0
    assert ("voice reply", "gemini:" + gemini.DEFAULT_TTS_MODEL, 0.0) in usage(store)

    Settings(served["data"]).update({"gemini_billing": "paid"})
    assert call(f"{base}/api/voice/speak", {"date": str(day), "text": "A fuse."})[0] == 200
    assert store.month_cost_usd(day.strftime("%Y-%m")) > 0
    store.add_usage(day, "fill", "x", 10_000)  # spend far past the monthly cap
    code, _, body = call(f"{base}/api/voice/speak", {"date": str(day), "text": "A fuse."})
    assert code == 402 and b"cap" in body


def test_chat_stream_sends_sentences_as_they_arrive(served, monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION", "0")  # the one-shot path; the warm session has its own tests
    base, day = served["base"], served["day"]
    monkeypatch.setenv("LLM_PROVIDER", "claude-cli")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "t")

    def fake_stream(messages, model, timeout=300, popen=None, timing=None):
        if timing is not None:
            timing.update(first_ms=3, claude_ms=7)
        yield "A fuse "
        yield "breaks the circuit. "
        yield "Replace it."

    monkeypatch.setattr(L, "run_claude_cli_stream", fake_stream)
    code, _, body = call(f"{base}/api/chat/stream", {"date": str(day), "message": "What is a fuse?"})
    assert code == 200
    events = [json.loads(block[6:]) for block in body.decode().split("\n\n") if block.startswith("data: ")]
    assert [e["text"] for e in events if e["type"] == "sentence"] == ["A fuse breaks the circuit.", "Replace it."]
    assert any(e["type"] == "delta" for e in events)
    assert events[-1] == {"type": "done", "reply": "A fuse breaks the circuit. Replace it."}
    assert ("chat (subscription)", "haiku", 0.0) in usage(served["store"])


def test_chat_stream_refuses_an_empty_question(server):
    base, _, day = server
    assert call(f"{base}/api/chat/stream", {"date": str(day), "message": "   "})[0] == 400


def test_status_route_reports_the_voice_settings(served):
    Settings(served["data"]).update({"lesson_voice": "gemini"})
    req = urllib.request.Request(f"{served['base']}/api/voice/status", headers={"Authorization": "Bearer secret"})
    with urllib.request.urlopen(req) as r:
        s = json.loads(r.read())
    assert s["lesson_voice"] == "gemini" and s["gemini_billing"] == "free" and s["whisper_model"] == "base.en"


# ---------- voicebench ----------

def test_voicebench_writes_results_for_the_admin_page(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("TRANSCRIBE", raising=False)
    monkeypatch.setattr(VB, "whisper", lambda model, runs=3: {"model": model, "clip_s": 5.0, "ms": 300, "runs": [300, 300, 300]})
    lines = []
    result = VB.run(tmp_path, ["base.en"], out=lines.append)
    assert result["whisper"][0]["model"] == "base.en" and result["gemini"] is None
    assert any("gemini: skipped" in line for line in lines)
    assert VB.last_result(tmp_path)["whisper"][0]["ms"] == 300
    assert len(VB.TEN) == 10


def test_chat_is_haiku_and_lessons_stay_sonnet():
    assert L.CLI_MODELS["chat"] == "haiku"
    assert L.CLI_MODELS["lesson"] == "sonnet"


# ---------- local voices: Kokoro (primary) and Piper (fallback) ----------

JS_SPEECH_SAMPLE = ("Authentication checks who you are, and it happens before access is granted, "
                    "because nothing else is safe.")


class FakeVoice:
    def __init__(self, label, audio=None, fail=False):
        self._label, self.audio, self.fail, self.calls = label, audio, fail, 0

    def label(self):
        return self._label

    def synthesize(self, text):
        self.calls += 1
        if self.fail:
            raise RuntimeError("broken")
        return self.audio, 16000


def test_model_paths_live_on_the_writable_data_volume(monkeypatch):
    for k in ("KOKORO_MODEL_PATH", "KOKORO_VOICES_PATH", "PIPER_MODEL_PATH", "TUTOR_MODELS_DIR"):
        monkeypatch.delenv(k, raising=False)
    km, kv = TT.kokoro_paths()
    assert str(km).startswith("/data/") and str(kv).startswith("/data/") and str(TT.piper_path()).startswith("/data/")


def test_missing_voice_files_say_how_to_fix_them(tmp_path, monkeypatch):
    monkeypatch.setenv("KOKORO_MODEL_PATH", str(tmp_path / "no.onnx"))
    monkeypatch.setenv("KOKORO_VOICES_PATH", str(tmp_path / "no.bin"))
    monkeypatch.setenv("PIPER_MODEL_PATH", str(tmp_path / "no-piper.onnx"))
    with pytest.raises(RuntimeError, match="fetch-voices"):
        TT.KokoroProvider().synthesize("hi")
    with pytest.raises(RuntimeError, match="fetch-voices"):
        TT.PiperProvider().synthesize("hi")
    assert TT.ready() == {"kokoro": False, "piper": False}


def test_provider_selection_is_resident_and_labelled(monkeypatch):
    assert isinstance(TT.provider("kokoro"), TT.KokoroProvider)
    assert TT.provider("kokoro") is TT.provider("kokoro")  # one resident instance, not one per sentence
    assert TT.KokoroProvider(voice="af_heart").label() == "local:kokoro-af_heart"
    assert TT.PiperProvider().label().startswith("local:piper-")
    with pytest.raises(ValueError):
        TT.provider("cloud")


def test_fallback_speaks_once_and_only_when_the_primary_fails(monkeypatch):
    import numpy as np
    audio = np.zeros(1600, dtype=np.float32)
    good = FakeVoice("local:piper-x", audio)
    bad = FakeVoice("local:kokoro-af_heart", fail=True)
    monkeypatch.setitem(TT._PROVIDERS, "kokoro", bad)
    monkeypatch.setitem(TT._PROVIDERS, "piper", good)
    wav, label, info = TT.synthesize("A firewall filters traffic.", primary="kokoro", fallback="piper")
    assert label == "local:piper-x" and info["provider"] == "piper" and wav[:4] == b"RIFF"
    assert bad.calls == 1 and good.calls == 1  # one clip out, so the sentence can't play twice
    bad.fail, bad.audio, good.calls = False, audio, 0
    _, label2, _ = TT.synthesize("A firewall filters traffic.", primary="kokoro", fallback="piper")
    assert label2 == "local:kokoro-af_heart" and good.calls == 0  # primary works: fallback never runs


def test_no_local_voice_gives_a_plain_error(monkeypatch):
    monkeypatch.setitem(TT._PROVIDERS, "kokoro", FakeVoice("a", fail=True))
    monkeypatch.setitem(TT._PROVIDERS, "piper", FakeVoice("b", fail=True))
    with pytest.raises(RuntimeError, match="no local voice is ready"):
        TT.synthesize("hi", primary="kokoro", fallback="piper")


def test_long_sentences_split_at_clauses_without_losing_words():
    rep = "The purpose of authentication is to verify the identity of a user before allowing access to a system."
    assert TT.split_for_speech(rep) == ["The purpose of authentication is to verify the identity of a user",
                                        "before allowing access to a system."]
    assert TT.split_for_speech("Short one, yes.") == ["Short one, yes."]
    pieces = TT.split_for_speech(JS_SPEECH_SAMPLE)
    assert " ".join(pieces).split() == JS_SPEECH_SAMPLE.split()


def test_browser_clause_rule_matches_the_server():
    js = _node("console.log(JSON.stringify(splitForSpeech(" + json.dumps(JS_SPEECH_SAMPLE) + ")))")
    assert js == TT.split_for_speech(JS_SPEECH_SAMPLE)


def test_wav_from_float_audio_is_16_bit_mono():
    import numpy as np
    wav = TT.to_wav(np.array([0.0, 0.5, -0.5], dtype=np.float32), 22050)
    assert wav[:4] == b"RIFF" and struct.unpack("<I", wav[24:28])[0] == 22050
    assert struct.unpack("<H", wav[22:24])[0] == 1 and struct.unpack("<H", wav[34:36])[0] == 16


def test_local_voice_route_is_free_and_logs_no_text(served, monkeypatch, caplog):
    import numpy as np
    caplog.set_level(logging.INFO, logger="tutor.timing")
    monkeypatch.setitem(TT._PROVIDERS, "kokoro", FakeVoice("local:kokoro-af_heart", np.zeros(1600, dtype=np.float32)))
    Settings(served["data"]).update({"lesson_voice": "kokoro"})
    code, ctype, body = call(f"{served['base']}/api/voice/tts",
                             {"date": str(served["day"]), "text": "SECRETSPEECH about fuses.", "kind": "read"})
    assert code == 200 and ctype == "audio/wav" and body[:4] == b"RIFF"
    assert ("voice reply", "local:kokoro-af_heart", 0.0) in usage(served["store"])
    assert served["store"].month_cost_usd(served["day"].strftime("%Y-%m")) == 0.0
    assert "tts_ms=" in caplog.text and "model=local:kokoro-af_heart" in caplog.text
    assert "SECRETSPEECH" not in caplog.text


def test_temp_files_go_to_the_writable_volume():
    # espeak-ng unpacks a shared library into TMPDIR; the container's /tmp is noexec, so it must point at /data.
    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text()
    assert "TMPDIR=/data/tmp" in dockerfile


def test_local_route_with_gemini_setting_uses_kokoro(served, monkeypatch):
    import numpy as np
    monkeypatch.setitem(TT._PROVIDERS, "kokoro", FakeVoice("local:kokoro-af_heart", np.zeros(1600, dtype=np.float32)))
    Settings(served["data"]).update({"lesson_voice": "gemini"})
    code, ctype, body = call(f"{served['base']}/api/voice/tts", {"date": str(served["day"]), "text": "A fuse.", "kind": "read"})
    assert code == 200 and body[:4] == b"RIFF"
    assert ("voice reply", "local:kokoro-af_heart", 0.0) in usage(served["store"])


def test_every_downloaded_file_has_a_checksum():
    assert set(TT.SHA256) == set(TT.KOKORO_FILES) | set(TT.PIPER_FILES)
    assert all(len(v) == 64 and all(c in "0123456789abcdef" for c in v) for v in TT.SHA256.values())


def test_fetch_refuses_a_file_that_does_not_match(tmp_path, monkeypatch):
    monkeypatch.setattr(TT, "KOKORO_DIR", tmp_path / "kokoro")
    monkeypatch.setattr(TT, "PIPER_DIR", tmp_path / "piper")

    def wrong_bytes(url, dst):
        Path(dst).write_bytes(b"not the model")

    with pytest.raises(RuntimeError, match="checksum mismatch"):
        TT.fetch(out=lambda s: None, download=wrong_bytes)
    assert not list(tmp_path.rglob("*.onnx")) and not list(tmp_path.rglob("*.bin"))  # nothing unchecked is kept


def test_fetch_keeps_matching_files_and_does_not_download_them_again(tmp_path, monkeypatch):
    import hashlib
    content = b"fake voice file"
    digest = hashlib.sha256(content).hexdigest()
    for name in list(TT.SHA256):
        monkeypatch.setitem(TT.SHA256, name, digest)
    monkeypatch.setattr(TT, "KOKORO_DIR", tmp_path / "kokoro")
    monkeypatch.setattr(TT, "PIPER_DIR", tmp_path / "piper")
    calls = []

    def fake(url, dst):
        calls.append(url)
        Path(dst).write_bytes(content)

    TT.fetch(out=lambda s: None, download=fake)
    assert len(calls) == 4
    TT.fetch(out=lambda s: None, download=fake)
    assert len(calls) == 4  # the second run finds matching files and downloads nothing


# ---------- warm Claude session (one process, one question at a time) ----------

class FakeClaude:
    """Stands in for `claude -p` (stream-json in and out). Each stdin line gets one scripted reply; "CRASH" ends the output."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.sent = []
        self.killed = False
        self._out = []
        self.stdin = self._In(self)
        self.stdout = self._Out(self)

    class _In:
        def __init__(self, p):
            self.p = p

        def write(self, text):
            msg = json.loads(text)
            self.p.sent.append(msg["message"]["content"])
            reply = self.p.replies.pop(0) if self.p.replies else "CRASH"
            if reply == "CRASH":
                self.p._out.append("")
                return
            for piece in reply:
                self.p._out.append(_delta(piece))
            self.p._out.append(json.dumps({"type": "result", "is_error": False, "result": "".join(reply)}) + "\n")

        def flush(self):
            pass

    class _Out:
        def __init__(self, p):
            self.p = p

        def readline(self):
            return self.p._out.pop(0) if self.p._out else ""

    def poll(self):
        return -9 if self.killed else None

    def kill(self):
        self.killed = True


def _factory(scripts, spawns):
    def popen(cmd, **kw):
        spawns.append(cmd)
        return FakeClaude(scripts[len(spawns) - 1] if len(spawns) <= len(scripts) else [])
    return popen


def _llm(tmp_path, monkeypatch, scripts):
    monkeypatch.setenv("LLM_PROVIDER", "claude-cli")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "t")
    monkeypatch.delenv("CLAUDE_SESSION", raising=False)
    spawns = []
    store = Store(tmp_path / "s.db")
    llm = L.LLM(store, tmp_path, session=L.ClaudeSession(popen=_factory(scripts, spawns)))
    return llm, spawns


def _sys(text="You are a tutor."):
    return {"role": "system", "content": text}


def test_warm_session_reuses_one_process_and_sends_only_the_new_question(tmp_path, monkeypatch):
    llm, spawns = _llm(tmp_path, monkeypatch, [[["A fuse "], ["It protects."]]])
    timing = {}
    first = "".join(llm.stream([_sys(), {"role": "user", "content": "What is a fuse?"}], "", "chat", timing=timing))
    second = "".join(llm.stream([_sys(), {"role": "user", "content": "What is a fuse?"},
                                 {"role": "assistant", "content": first},
                                 {"role": "user", "content": "And what does it do?"}], "", "chat"))
    assert len(spawns) == 1
    assert second == "It protects."
    assert llm.session.proc.sent[1] == "And what does it do?"  # Claude already has the earlier turns
    assert "first_ms" in timing and timing["warm"] == 0
    assert "--input-format" in spawns[0] and "stream-json" in spawns[0] and "--include-partial-messages" in spawns[0]
    assert spawns[0][spawns[0].index("--tools") + 1] == ""


def test_a_changed_system_prompt_starts_a_new_session(tmp_path, monkeypatch):
    llm, spawns = _llm(tmp_path, monkeypatch, [[["one"]], [["two"]]])
    list(llm.stream([_sys("A"), {"role": "user", "content": "q1"}], "", "chat"))
    list(llm.stream([_sys("B"), {"role": "user", "content": "q2"}], "", "chat"))
    assert len(spawns) == 2


def test_session_restarts_after_its_turn_limit(tmp_path, monkeypatch):
    monkeypatch.setattr("tutor.providers.claude_cli.SESSION_MAX_TURNS", 2)
    llm, spawns = _llm(tmp_path, monkeypatch, [[["a"], ["b"]], [["c"]]])
    for q in ("q1", "q2", "q3"):
        assert "".join(llm.stream([_sys(), {"role": "user", "content": q}], "", "chat"))
    assert len(spawns) == 2


def test_a_crash_before_any_text_is_retried_once_with_the_full_history(tmp_path, monkeypatch):
    llm, spawns = _llm(tmp_path, monkeypatch, [["CRASH"], [["Recovered."]]])
    history = [_sys(), {"role": "user", "content": "first"}, {"role": "assistant", "content": "ok"},
               {"role": "user", "content": "second"}]
    assert "".join(llm.stream(history, "", "chat")) == "Recovered."
    assert len(spawns) == 2
    assert "Conversation so far" in llm.session.proc.sent[0]  # the fresh process gets the whole conversation


def test_two_crashes_give_a_plain_error(tmp_path, monkeypatch):
    llm, _ = _llm(tmp_path, monkeypatch, [["CRASH"], ["CRASH"]])
    with pytest.raises(RuntimeError, match="failed"):
        list(llm.stream([_sys(), {"role": "user", "content": "q"}], "", "chat"))


def test_stopping_early_kills_the_process(tmp_path, monkeypatch):
    llm, spawns = _llm(tmp_path, monkeypatch, [[["one ", "two ", "three."]]])
    gen = llm.stream([_sys(), {"role": "user", "content": "q"}], "", "chat")
    assert next(gen) == "one "
    gen.close()  # the student asked something else
    assert llm.session.proc is None and len(spawns) == 1


# ---------- pronunciation: the screen keeps the written form, speech uses the spoken form ----------

from tutor import pronounce as P  # noqa: E402

PRON_SAMPLE = "SIEM and SOAR, the CIA triad, 802.1X and IPsec, SY0-701, port 443, e.g., vs. etc. SIEMens 1443"


def test_pronunciation_rules_apply_whole_words_longest_first():
    rules = P.load(PACKS / "security-plus-sy0-701" / "pronounce.yaml")
    assert rules and rules[0][0] == max((w for w, _ in rules), key=len)
    assert P.apply("SIEM and SOAR", rules) == "sim and soar"
    assert P.apply("the CIA triad", rules) == "the C I A triad"  # the longer rule wins over CIA alone
    assert P.apply("port 443 and 1443", rules) == "port four four three and 1443"
    assert P.apply("SIEMens", rules) == "SIEMens"  # no match inside a longer word
    assert P.load(Path("/no/such/file.yaml")) == []  # a missing file means no rules, not a crash


def test_browser_pronunciation_matches_the_server():
    rules = P.load(PACKS / "security-plus-sy0-701" / "pronounce.yaml")
    js = _node("console.log(JSON.stringify(applyPronounce(" + json.dumps(PRON_SAMPLE) + ", " + json.dumps([list(r) for r in rules]) + ")))")
    assert js == P.apply(PRON_SAMPLE, rules)


def test_speech_gets_the_spoken_form_and_the_screen_does_not(served, monkeypatch):
    seen = {}

    def fake_synth(text, primary="kokoro", fallback="piper", cache=None):
        seen["text"] = text
        return b"RIFF", "local:kokoro-af_heart", {"tts_ms": 1.0, "audio_s": 0.1, "provider": "kokoro"}

    monkeypatch.setattr(TT, "synthesize", fake_synth)
    code, _, _ = call(f"{served['base']}/api/voice/tts", {"date": str(served["day"]), "text": "SIEM and port 443.", "kind": "read"})
    assert code == 200 and seen["text"] == "sim and port four four three."
    code, _, body = call(f"{served['base']}/api/admin/pronounce", {"text": "SIEM and SOAR"})
    assert code == 200 and json.loads(body)["spoken"] == "sim and soar"


def test_status_sends_the_rules_to_the_page(served):
    req = urllib.request.Request(f"{served['base']}/api/voice/status", headers={"Authorization": "Bearer secret"})
    with urllib.request.urlopen(req) as r:
        s = json.loads(r.read())
    assert ["SIEM", "sim"] in s["pronounce"]


# ---------- one chain per spoken question ----------

def test_chain_steps_are_ordered_and_summarised():
    import uuid
    cid = uuid.uuid4().hex[:24]
    T.chain_add(cid, transcribe_ms=410.0, chat_first_ms=1500.0)
    T.chain_add(cid, t_transcript=700, t_reply=1900, t_tts_ready=2100, t_audio=2300)
    summary = T.chains_summary()
    row = next(r for r in summary["chains"] if r["id"] == cid)
    assert row["t_transcript"] <= row["t_reply"] <= row["t_tts_ready"] <= row["t_audio"]
    assert row["transcribe_ms"] == 410.0 and row["chat_first_ms"] == 1500.0
    assert summary["medians"]["t_audio"] > 0


def test_bad_chain_ids_are_ignored():
    before = T.chains_summary()["started"]
    T.chain_add("not valid!", t_audio=1)
    T.chain_add(None, t_audio=1)
    assert T.chains_summary()["started"] == before


def test_browser_steps_join_the_server_chain_and_logs_hold_no_text(served, caplog):
    import uuid
    caplog.set_level(logging.INFO, logger="tutor.timing")
    cid = uuid.uuid4().hex[:24]
    code, _, _ = call(f"{served['base']}/api/voice/timings",
                      {"kind": "ask", "chain": cid, "t_transcript": 600, "t_reply": 1500, "t_tts_ready": 1800,
                       "t_audio": 2000, "question": "SECRETCHAIN"})
    assert code == 200
    assert f"voice chain {cid}" in caplog.text and "SECRETCHAIN" not in caplog.text
    req = urllib.request.Request(f"{served['base']}/api/admin", headers={"Authorization": "Bearer secret"})
    with urllib.request.urlopen(req) as r:
        admin = json.loads(r.read())
    assert any(c["id"] == cid and c["t_audio"] == 2000 for c in admin["chains"]["chains"])


# ---------- slide audio cache ----------

def test_cache_hit_skips_the_provider(tmp_path, monkeypatch):
    import numpy as np
    voice = FakeVoice("local:kokoro-af_heart", np.zeros(1600, dtype=np.float32))
    monkeypatch.setitem(TT._PROVIDERS, "kokoro", voice)
    cache = TT.SpeechCache(tmp_path)
    first = TT.synthesize("A firewall filters traffic.", primary="kokoro", fallback=None, cache=cache)
    second = TT.synthesize("A firewall filters traffic.", primary="kokoro", fallback=None, cache=cache)
    assert voice.calls == 1 and second[2]["provider"] == "cache" and second[0] == first[0]


def test_cache_key_changes_with_the_voice(tmp_path):
    cache = TT.SpeechCache(tmp_path)
    assert cache.key("local:kokoro-af_heart", "Hi.") != cache.key("local:kokoro-bf_emma", "Hi.")
    assert cache.key("local:kokoro-af_heart", "Hi.") != cache.key("local:piper-x", "Hi.")


def test_fallback_audio_is_not_cached_under_the_primary(tmp_path, monkeypatch):
    import numpy as np
    monkeypatch.setitem(TT._PROVIDERS, "kokoro", FakeVoice("local:kokoro-af_heart", fail=True))
    monkeypatch.setitem(TT._PROVIDERS, "piper", FakeVoice("local:piper-x", np.zeros(1600, dtype=np.float32)))
    cache = TT.SpeechCache(tmp_path)
    _, label, _ = TT.synthesize("Hi there.", primary="kokoro", fallback="piper", cache=cache)
    assert label == "local:piper-x"
    assert cache.get(cache.key("local:kokoro-af_heart", "Hi there.")) is None


def test_pruning_removes_old_files_and_keeps_the_size_cap(tmp_path):
    import os
    cache = TT.SpeechCache(tmp_path)
    now = 2_000_000_000.0
    for name, age_days in (("old", 9), ("mid", 3), ("new", 1)):
        cache.put(name, b"x" * 1000)
        os.utime(tmp_path / f"{name}.wav", (now - age_days * 86400, now - age_days * 86400))
    assert cache.prune(now=now, max_age=7 * 86400, max_bytes=10_000)["removed"] == 1
    assert not (tmp_path / "old.wav").exists() and (tmp_path / "new.wav").exists()
    assert cache.prune(now=now, max_age=7 * 86400, max_bytes=1500)["bytes"] <= 1500  # the oldest goes first
    assert (tmp_path / "new.wav").exists() and not (tmp_path / "mid.wav").exists()


def test_prebuild_builds_every_slide_once_and_skips_on_rerun(tmp_path, monkeypatch):
    import numpy as np
    from tutor import settings as S
    voice = FakeVoice("local:kokoro-af_heart", np.zeros(1600, dtype=np.float32))
    monkeypatch.setitem(TT._PROVIDERS, "kokoro", voice)
    S.Settings(tmp_path).update({"lesson_voice": "kokoro"})
    md = ("## Basics\n### Slide one\nAuthentication checks who you are. It happens before access is granted, because nothing else is safe.\n"
          "### Slide two\nSIEM collects logs.\n")
    expected = len(TT.slide_pieces(md))
    first = TT.prebuild_lesson(tmp_path, md, rules=[("SIEM", "sim")], cache_root=tmp_path / "cache", out=lambda s: None)
    assert first["built"] == expected == voice.calls and first["cache_bytes"] > 0
    again = TT.prebuild_lesson(tmp_path, md, rules=[("SIEM", "sim")], cache_root=tmp_path / "cache", out=lambda s: None)
    assert again["built"] == 0 and voice.calls == expected  # a rerun costs nothing


def test_prebuild_is_skipped_for_cloud_voices(tmp_path):
    from tutor import settings as S
    S.Settings(tmp_path).update({"lesson_voice": "gemini"})
    assert TT.prebuild_lesson(tmp_path, "## A\n### B\nHi.\n", out=lambda s: None) == {"skipped": "lesson voice is not local"}


def test_separators_are_not_spoken():
    pieces = TT.slide_pieces("## A\n### B\n---\nSIEM collects logs.\n")
    assert "SIEM collects logs." in pieces and not any("---" in p for p in pieces)
    with pytest.raises(ValueError):
        TT.synthesize("---", primary="kokoro", fallback=None)


# ---------- speech-to-text: word error rate and the Whisper prompt ----------

from tutor import stt as STT  # noqa: E402


def test_word_error_rate():
    assert STT.wer("the cat sat", "the cat sat") == 0.0
    assert STT.wer("the cat sat", "the bat sat") == pytest.approx(1 / 3)
    assert STT.wer("", "") == 0.0 and STT.wer("", "extra") == 1.0


def test_whisper_prompt_has_key_terms_and_today_objectives():
    pack = load_pack(PACKS, "security-plus-sy0-701")
    oid = pack.objectives[0]["id"]
    prompt = STT.build_prompt(pack, f"<!-- objectives: {oid} -->\n# Lesson", [("SIEM", "sim")])
    assert "SIEM" in prompt and pack.objectives[0]["title"] in prompt and len(prompt) <= 600


def test_prompt_is_passed_to_whisper_only_when_given(monkeypatch):
    model = FakeModel()
    monkeypatch.setattr(V, "_load_model", lambda name=None: (model, 0.0))
    wav = V.BENCH_CLIP.read_bytes()
    V._local_transcribe(wav, "base.en", 5000, {})
    assert "initial_prompt" not in model.calls[-1]
    V._local_transcribe(wav, "base.en", 5000, {}, prompt="Security+ terms")
    assert model.calls[-1]["initial_prompt"] == "Security+ terms"


def test_prompt_setting_is_on_or_off(tmp_path):
    s = Settings(tmp_path)
    assert s.get()["stt_prompt"] == "off"
    s.update({"stt_prompt": "on"})
    with pytest.raises(ValueError):
        s.update({"stt_prompt": "maybe"})


# ---------- blind voice test ----------

def test_blind_test_hides_voices_and_reveals_after_all_ratings(tmp_path, monkeypatch):
    import numpy as np
    from tutor.bench import blindtest as BT
    silent = np.zeros(800, dtype=np.float32)
    monkeypatch.setattr(TT, "KokoroProvider", lambda voice=None, threads=None: FakeVoice(f"local:kokoro-{voice}", silent))
    monkeypatch.setattr(TT, "PiperProvider", lambda: FakeVoice("local:piper-en_US-lessac-medium", silent))
    key = BT.build(tmp_path, out=lambda s: None)
    assert len(key) == len(BT.SENTENCES) * len(BT.VOICES) == 12
    items = BT.playlist(tmp_path, rng=random.Random(1))
    assert len(items) == 12 and all(set(i) == {"id", "sentence", "text"} for i in items)
    assert "kokoro" not in json.dumps(items) and "piper" not in json.dumps(items)  # voice names never shown
    assert [i["id"] for i in items] != [i["id"] for i in BT.playlist(tmp_path, rng=random.Random(2))]
    assert BT.results(tmp_path)["done"] is False
    for n, item in enumerate(items):
        assert BT.vote(tmp_path, item["id"], 3 + n % 3)
    res = BT.results(tmp_path)
    assert res["done"] and res["rated"] == 12 and len(res["by_voice"]) == 4
    assert BT.clip_path(tmp_path, items[0]["id"]).exists() and BT.clip_path(tmp_path, "../key") is None
    assert not BT.vote(tmp_path, "nope", 3) and not BT.vote(tmp_path, items[0]["id"], 9)


def test_blind_test_routes_need_the_token(served, monkeypatch):
    import numpy as np
    from tutor.bench import blindtest as BT
    silent = np.zeros(800, dtype=np.float32)
    monkeypatch.setattr(TT, "KokoroProvider", lambda voice=None, threads=None: FakeVoice(f"local:kokoro-{voice}", silent))
    monkeypatch.setattr(TT, "PiperProvider", lambda: FakeVoice("local:piper-x", silent))
    base = served["base"]
    assert call(f"{base}/api/admin/blindtest/build", {}, tok="wrong")[0] == 401
    assert call(f"{base}/api/admin/blindtest/build", {})[0] == 200
    req = urllib.request.Request(f"{base}/api/admin/blindtest", headers={"Authorization": "Bearer secret"})
    with urllib.request.urlopen(req) as r:
        listing = json.loads(r.read())
    clip = listing["items"][0]["id"]
    req = urllib.request.Request(f"{base}/api/admin/blindtest/audio/{clip}", headers={"Authorization": "Bearer secret"})
    with urllib.request.urlopen(req) as r:
        assert r.headers.get("Content-Type") == "audio/wav" and r.read()[:4] == b"RIFF"
