import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from tutor import parakeet as PK
from tutor.bench import sttbench as SB
from tutor import tts as TT

BENCH_CLIP = Path(__file__).resolve().parents[1] / "tutor" / "assets" / "voicebench-5s.wav"


def test_acronyms_are_counted_apart_from_other_terms():
    assert SB.is_acronym("SIEM") and SB.is_acronym("SY0-701") and SB.is_acronym("TACACS+") and SB.is_acronym("802.1X")
    assert not SB.is_acronym("IPsec") and not SB.is_acronym("CIA triad")


def test_term_hits_count_each_occurrence():
    ref = "The SIEM and the SIEM feed MFA alerts, and IPsec protects traffic."
    hyp = "The sim and the SIEM feed MFA alerts, and ip sec protects traffic."
    hits = SB.term_hits(ref, hyp)
    assert hits["SIEM"] == {"ref": 2, "hit": 1}
    assert hits["MFA"] == {"ref": 1, "hit": 1}
    assert hits["IPsec"] == {"ref": 1, "hit": 0}   # "ip sec" is a miss, and the report shows it
    assert "XDR" not in hits                       # absent from the reference, so not scored


def test_term_hits_do_not_count_more_than_the_reference():
    hits = SB.term_hits("PKI", "PKI PKI PKI")
    assert hits == {"PKI": {"ref": 1, "hit": 1}}


def test_parakeet_files_by_precision():
    int8 = PK.files("int8")
    flt = PK.files("float")
    assert "encoder-model.int8.onnx" in int8 and "encoder-model.onnx.data" not in int8
    assert "encoder-model.onnx.data" in flt and "encoder-model.int8.onnx" not in flt
    assert "vocab.txt" in int8 and "vocab.txt" in flt         # shared files are in both
    with pytest.raises(ValueError):
        PK.files("fp16")


def test_parakeet_lives_under_the_models_folder():
    assert PK.DIR.parent == TT.MODELS_DIR


def test_parakeet_fetch_saves_a_matching_file(tmp_path, monkeypatch):
    payload = b"model bytes"
    digest = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(PK, "DIR", tmp_path / "parakeet")
    monkeypatch.setattr(PK, "COMMON", {"vocab.txt": (digest, len(payload))})
    monkeypatch.setattr(PK, "FILES_BY_PRECISION", {"int8": {}, "float": {}})

    def download(url, dst):
        assert url.startswith(PK.BASE) and url.endswith("vocab.txt")
        Path(dst).write_bytes(payload)

    PK.fetch(precisions=("int8",), out=lambda *_: None, download=download)
    assert (tmp_path / "parakeet" / "vocab.txt").read_bytes() == payload
    assert not list((tmp_path / "parakeet").glob("*.part"))


def test_parakeet_fetch_rejects_a_bad_download(tmp_path, monkeypatch):
    monkeypatch.setattr(PK, "DIR", tmp_path / "parakeet")
    monkeypatch.setattr(PK, "COMMON", {"vocab.txt": ("0" * 64, 3)})
    monkeypatch.setattr(PK, "FILES_BY_PRECISION", {"int8": {}, "float": {}})

    def download(url, dst):
        Path(dst).write_bytes(b"bad")

    with pytest.raises(RuntimeError, match="checksum mismatch"):
        PK.fetch(precisions=("int8",), out=lambda *_: None, download=download)
    assert not (tmp_path / "parakeet" / "vocab.txt").exists()
    assert not (tmp_path / "parakeet" / "vocab.txt.part").exists()


def test_parakeet_load_explains_missing_files(tmp_path, monkeypatch):
    monkeypatch.setattr(PK, "DIR", tmp_path / "nothing")
    with pytest.raises(RuntimeError, match="fetch-voices --stt parakeet"):
        PK.load("int8")


def _fake_result(hyps, ms=(100.0, 120.0, 90.0), ram=512.0):
    runs = [{"audio_s": 5.0, "ms": list(ms)} for _ in hyps]
    return {"cold_load_ms": 2000, "peak_ram_mb": ram, "variants": {"plain": {"hyps": hyps, "runs": runs}}}


def test_sttbench_writes_the_report_format(tmp_path, monkeypatch):
    folder = tmp_path / "stt-samples"
    folder.mkdir()
    (folder / "a.wav").write_bytes(b"x")
    (folder / "a.txt").write_text("Configure the SIEM and MFA.")
    (folder / "b.wav").write_bytes(b"x")
    (folder / "b.txt").write_text("IPsec protects traffic.")
    calls = []

    def fake_spawn(spec):
        calls.append((spec["engine"], spec["model"], spec["threads"]))
        if spec["engine"] == "parakeet" and spec["model"] == "float":
            return {"error": "Parakeet files are missing"}
        return _fake_result(["configure the siem and mfa", "ipsec protects traffic"])

    monkeypatch.setattr(SB, "_spawn", fake_spawn)
    result = SB.run(tmp_path, prompt_text="Security+ terms", threads=(4, 8), out=lambda *_: None)

    assert len(calls) == len(SB.ENGINES) * 2
    assert {c[2] for c in calls} == {4, 8}
    assert result["samples"] == ["a.wav", "b.wav"]
    assert result["reference_words"] > 0
    rows = {(r["label"], r["threads"]): r for r in result["rows"]}
    ok = rows[("whisper base.en", 8)]
    assert ok["wer"] == 0.0 and ok["acronyms_plain"] == {"ref": 2, "hit": 2}
    assert ok["terms_plain"] == {"ref": 1, "hit": 1}
    assert ok["cold_load_ms"] == 2000 and ok["peak_ram_mb"] == 512.0
    assert ok["warm_median_ms"] == 100 and ok["warm_worst_ms"] == 120
    # 2 clips x 5 s x 3 warm runs = 30 s of audio, processed in 0.62 s
    assert ok["rtf"] == round(30 / 0.62, 2)
    assert rows[("parakeet float", 4)]["error"].startswith("Parakeet files")
    saved = json.loads((tmp_path / SB.RESULTS).read_text())
    assert saved["rows"] and saved["time"]
    assert SB.last_result(tmp_path)["rows"] == saved["rows"]


def test_sttbench_without_samples_says_so(tmp_path):
    messages = []
    assert SB.run(tmp_path, samples=tmp_path / "empty", out=messages.append) is None
    assert "no samples" in messages[0]


def test_sttbench_does_not_write_a_result_on_no_samples(tmp_path):
    SB.run(tmp_path, samples=tmp_path / "empty", out=lambda *_: None)
    assert SB.last_result(tmp_path) is None


@pytest.mark.skipif(not (PK.ready("int8") and importlib.util.find_spec("onnx_asr")),
                    reason="Parakeet int8 files or onnx-asr not installed on this machine")
def test_parakeet_int8_transcribes_the_bundled_clip():
    from faster_whisper.audio import decode_audio
    model = PK.load("int8", threads=4)
    text = PK.recognize(model, decode_audio(str(BENCH_CLIP), sampling_rate=16000))
    assert text and "firewall" in text.lower()
