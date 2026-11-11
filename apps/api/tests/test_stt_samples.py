import io
import json
import threading
import time
import urllib.error
import urllib.request
import wave
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from tutor.bench import sttbench as SB
from tutor.pack import load_pack
from tutor.server import App, make_handler
from tutor.store import Store

PACKS = Path(__file__).resolve().parents[3] / "packs"


def make_wav(seconds=0.5, rate=16000, channels=1, width=2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(b"\x01\x00" * int(seconds * rate) * channels if width == 2 else b"\x01" * int(seconds * rate) * channels)
    return buf.getvalue()


@pytest.fixture
def samples(tmp_path):
    folder = tmp_path / "stt-samples"
    folder.mkdir()
    (folder / "q01.txt").write_text("What does a SIEM do?")
    (folder / "q02.txt").write_text("Which tool automates responses?")
    (folder / "bad name.txt").write_text("not a valid name")   # excluded by the name rule
    return tmp_path


# ---------- names and traversal ----------

def test_only_sentence_files_give_valid_names(samples):
    assert SB.sample_names(samples) == ["q01", "q02"]


@pytest.mark.parametrize("name", ["../q01", "..", "q01/../../x", "..\\q01", "q01.wav", "q99", "Q01", "", "q01\x00"])
def test_names_outside_the_sentence_list_are_refused(samples, name):
    with pytest.raises(ValueError, match="unknown sentence"):
        SB.save_sample(samples, name, make_wav())
    assert not list(samples.rglob("*.wav"))   # nothing written anywhere


def test_traversal_never_writes_outside_the_folder(samples):
    outside = samples / "outside.txt"
    outside.write_text("secret")
    with pytest.raises(ValueError):
        SB.save_sample(samples, "../outside", make_wav())
    assert outside.read_text() == "secret"


def test_a_sentence_name_always_stays_in_the_folder(samples):
    dst = SB.save_sample(samples, "q01", make_wav())
    assert dst.parent == samples / "stt-samples" and dst.name == "q01.wav"


# ---------- WAV checks and size ----------

@pytest.mark.parametrize("body,why", [
    (b"", "empty"),
    (b"not a wav file at all", "not a WAV"),
    (make_wav(rate=8000), "wrong rate"),
    (make_wav(channels=2), "stereo"),
    (make_wav(width=1), "8-bit"),
    (make_wav(seconds=61), "longer than a minute"),
])
def test_bad_recordings_are_rejected(samples, body, why):
    with pytest.raises(ValueError):
        SB.save_sample(samples, "q01", body)
    assert not (samples / "stt-samples" / "q01.wav").exists()


def test_size_limit(samples):
    with pytest.raises(ValueError, match="too large"):
        SB.save_sample(samples, "q01", b"\x00" * (SB.MAX_SAMPLE_BYTES + 1))


def test_saved_file_round_trips(samples):
    body = make_wav(seconds=1.5)
    dst = SB.save_sample(samples, "q01", body)
    assert dst.read_bytes() == body
    with wave.open(str(dst), "rb") as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 16000)
        assert w.getnframes() == 24000
    status = {s["name"]: s for s in SB.samples_status(samples)}
    assert status["q01"]["recorded"] is True and status["q02"]["recorded"] is False
    assert status["q01"]["text"] == "What does a SIEM do?"


# ---------- HTTP: token, limits, the sttbench button ----------

@pytest.fixture
def served(tmp_path, samples):
    store = Store(tmp_path / "t.db")
    app = App(load_pack(PACKS, "security-plus-sy0-701"), store, samples, token="secret")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield {"base": f"http://127.0.0.1:{srv.server_port}", "data": samples}
    srv.shutdown()
    for _ in range(400):   # the benchmark job is module-level: let it finish before the next test starts one
        if not SB._JOB["running"]:
            break
        time.sleep(0.05)


def call(base, method, path, body=b"", ctype="application/json", token="secret"):
    req = urllib.request.Request(base + path, data=body if method == "POST" else None, method=method)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_upload_needs_the_token(served):
    status, _ = call(served["base"], "POST", "/api/admin/stt-sample/q01", make_wav(), "audio/wav", token="")
    assert status == 401
    assert not (served["data"] / "stt-samples" / "q01.wav").exists()


def test_upload_saves_a_good_recording(served):
    status, body = call(served["base"], "POST", "/api/admin/stt-sample/q01", make_wav(), "audio/wav")
    assert status == 200 and b'"ok": true' in body
    assert (served["data"] / "stt-samples" / "q01.wav").exists()
    status, body = call(served["base"], "GET", "/api/admin/stt-samples")
    assert b'"recorded": true' in body


def test_upload_refuses_a_bad_name_and_a_bad_wav(served):
    status, _ = call(served["base"], "POST", "/api/admin/stt-sample/..%2Fq01", make_wav(), "audio/wav")
    assert status == 400
    status, body = call(served["base"], "POST", "/api/admin/stt-sample/q01", b"not audio", "audio/wav")
    assert status == 400 and b"WAV" in body


def test_upload_size_limit_is_checked_before_reading(served):
    status, body = call(served["base"], "POST", "/api/admin/stt-sample/q01", b"\x00" * (SB.MAX_SAMPLE_BYTES + 10), "audio/wav")
    assert status == 413 and b"too large" in body


def test_sttbench_button_returns_results(served, monkeypatch):
    def fake_spawn(spec):
        return {"cold_load_ms": 100, "peak_ram_mb": 10.0,
                "variants": {"plain": {"hyps": ["what does a siem do"], "runs": [{"audio_s": 2.0, "ms": [50.0]}]}}}

    monkeypatch.setattr(SB, "_spawn", fake_spawn)
    monkeypatch.setattr(SB, "THREADS", (8,))
    (served["data"] / "stt-samples" / "q01.wav").write_bytes(make_wav())
    status, body = call(served["base"], "POST", "/api/admin/sttbench/run", b"{}")
    assert status == 202
    deadline = time.time() + 20
    while time.time() < deadline:
        _, body = call(served["base"], "GET", "/api/admin/sttbench")
        state = json.loads(body)
        if not state["running"]:
            break
        time.sleep(0.05)
    assert state["running"] is False and state["error"] is None
    assert state["result"] and state["result"]["rows"]
    assert {r["engine"] for r in state["result"]["rows"]} >= {"whisper", "parakeet"}


def test_sttbench_refuses_a_second_run_while_one_is_going(served, monkeypatch):
    release = threading.Event()

    def slow_spawn(spec):
        release.wait(10)
        return {"error": "stopped for the test"}

    monkeypatch.setattr(SB, "_spawn", slow_spawn)
    monkeypatch.setattr(SB, "THREADS", (8,))
    (served["data"] / "stt-samples" / "q01.wav").write_bytes(make_wav())
    try:
        assert call(served["base"], "POST", "/api/admin/sttbench/run", b"{}")[0] == 202
        assert call(served["base"], "POST", "/api/admin/sttbench/run", b"{}")[0] == 409
    finally:
        release.set()
