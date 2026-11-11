"""`python3 -m tutor sttbench`: compare speech-to-text engines on your own recordings.

Samples go in data/stt-samples (git-ignored): a .wav with a .txt of the exact words said, same name.
Every engine and thread count runs in its own process, so load time and peak RAM aren't shared between them.
Results go to data/sttbench.json; the admin Voice card shows them beside the engine choice.

Scores per engine:
- word error rate over all words (stt.wer), with and without the Whisper prompt for Whisper;
- term recall for Security+ terms, split into acronyms (all capitals: SIEM, MFA, SY0-701) and other terms (IPsec, CIA triad);
- warm latency per clip (median and worst of REPS runs), real-time factor (audio seconds per processing second),
  cold load time (model load plus one silent call), and peak RAM (Linux only: the process's VmHWM).
"""
from __future__ import annotations
import datetime as dt
import io
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path

from .. import stt as STT

ENGINES = [  # label, engine, model (Whisper size, or Parakeet precision)
    ("whisper base.en", "whisper", "base.en"),
    ("whisper small.en", "whisper", "small.en"),
    ("parakeet int8", "parakeet", "int8"),
    ("parakeet float", "parakeet", "float"),
]
THREADS = (4, 8, 16)
REPS = 3                   # warm runs per clip; the median and worst are reported
VAD_MIN_S = 3.0            # same rule as the app: Whisper's voice-activity filter is skipped for clips under 3 s
WORKER_TIMEOUT_S = 1800
# Security+ terms to score. Acronyms are counted separately from other terms.
TERMS = ["SIEM", "SOAR", "XDR", "IPsec", "802.1X", "CIA triad", "MFA", "RADIUS", "TACACS+", "PKI", "SY0-701"]
RESULTS = "sttbench.json"


def is_acronym(term: str) -> bool:
    return bool(re.fullmatch(r"[A-Z0-9+.\-]+", term))


def _count(seq: list[str], sub: list[str]) -> int:
    n = len(sub)
    return sum(1 for i in range(len(seq) - n + 1) if seq[i:i + n] == sub) if n else 0


def term_hits(ref: str, hyp: str) -> dict:
    """For each term in the reference: how many times it occurs, and how many of those the transcript got back."""
    r, h = STT.words(ref), STT.words(hyp)
    out = {}
    for term in TERMS:
        seq = STT.words(term)
        n_ref = _count(r, seq)
        if n_ref:
            out[term] = {"ref": n_ref, "hit": min(n_ref, _count(h, seq))}
    return out


def _peak_ram_mb() -> float | None:
    """Peak resident memory of this process, from the Linux kernel (the container). None elsewhere."""
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmHWM:"):
                return round(int(line.split()[1]) / 1024, 1)
    except (OSError, ValueError):
        pass
    return None


# ---------- worker: one engine, one thread count, one process ----------

def worker(spec: dict) -> dict:
    """Loads one engine, warms it up, then runs every clip REPS times. Runs in its own process (see _spawn)."""
    import numpy as np
    from faster_whisper.audio import decode_audio

    threads = int(spec["threads"])
    t0 = time.perf_counter()
    if spec["engine"] == "whisper":
        from faster_whisper import WhisperModel
        model = WhisperModel(spec["model"], device="cpu", compute_type="int8", cpu_threads=threads,
                             download_root=spec["model_dir"])

        def run(samples, prompt):
            vad = len(samples) / 16000 >= VAD_MIN_S
            extra = {"initial_prompt": prompt} if prompt else {}
            segments, _ = model.transcribe(samples, language="en", beam_size=1, vad_filter=vad, **extra)
            return " ".join(s.text.strip() for s in segments).strip()
    else:
        from .. import parakeet as PK
        model = PK.load(spec["model"], threads)

        def run(samples, prompt):
            return PK.recognize(model, samples)

    run(np.zeros(16000, dtype=np.float32), None)           # first call is slower: include it in the cold time
    cold_ms = round((time.perf_counter() - t0) * 1000)

    variants = {"plain": None}
    if spec.get("prompt"):
        variants["prompt"] = spec["prompt"]
    out = {"cold_load_ms": cold_ms, "peak_ram_mb": None, "variants": {}}
    for name, prompt in variants.items():
        hyps, runs = [], []
        for wav in spec["clips"]:
            samples = decode_audio(wav, sampling_rate=16000)
            audio_s = round(len(samples) / 16000, 2)
            times = []
            for _ in range(REPS):
                t = time.perf_counter()
                hyp = run(samples, prompt)
                times.append(round((time.perf_counter() - t) * 1000, 1))
            hyps.append(hyp)
            runs.append({"audio_s": audio_s, "ms": times})
        out["variants"][name] = {"hyps": hyps, "runs": runs}
    out["peak_ram_mb"] = _peak_ram_mb()
    return out


def _spawn(spec: dict) -> dict:
    """Runs one worker in a fresh process. Returns its result, or {"error": ...} if it failed."""
    try:
        proc = subprocess.run([sys.executable, "-m", "tutor", "stt-worker", json.dumps(spec)],
                              capture_output=True, text=True, timeout=WORKER_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return {"error": "timed out"}
    for line in proc.stdout.splitlines():
        if line.startswith("RESULT "):
            return json.loads(line[len("RESULT "):])
    last = (proc.stderr.strip().splitlines() or ["no output"])[-1]
    return {"error": last[:200]}


# ---------- scoring and the report ----------

def _score(label: str, engine: str, model: str, threads: int, res: dict, refs: list[str], names: list[str]) -> dict:
    row = {"engine": engine, "model": model, "label": label, "threads": threads}
    if "error" in res:
        row["error"] = res["error"]
        return row
    row["cold_load_ms"] = res["cold_load_ms"]
    row["peak_ram_mb"] = res["peak_ram_mb"]
    all_ms, audio_s = [], 0.0
    for clip in res["variants"]["plain"]["runs"]:
        all_ms += clip["ms"]
        audio_s += clip["audio_s"] * REPS
    row["warm_median_ms"] = round(statistics.median(all_ms))
    row["warm_worst_ms"] = round(max(all_ms))
    row["rtf"] = round(audio_s / (sum(all_ms) / 1000), 2)
    for variant, key in (("plain", "wer"), ("prompt", "wer_prompt")):
        if variant not in res["variants"]:
            continue
        hyps = res["variants"][variant]["hyps"]
        row[key] = round(statistics.mean(STT.wer(r, h) for r, h in zip(refs, hyps)), 3)
        acr = {"ref": 0, "hit": 0}
        oth = {"ref": 0, "hit": 0}
        terms = {}
        for ref, hyp in zip(refs, hyps):
            for term, c in term_hits(ref, hyp).items():
                bucket = acr if is_acronym(term) else oth
                bucket["ref"] += c["ref"]
                bucket["hit"] += c["hit"]
                t = terms.setdefault(term, {"ref": 0, "hit": 0})
                t["ref"] += c["ref"]
                t["hit"] += c["hit"]
        row[f"acronyms_{variant}"] = acr
        row[f"terms_{variant}"] = oth
        row[f"per_term_{variant}"] = terms
        row[f"hyps_{variant}"] = dict(zip(names, hyps))
    return row


def _table(rows: list[dict]) -> str:
    head = f"{'engine':18}{'thr':>4}{'cold ms':>9}{'warm med':>10}{'worst':>8}{'RTF':>6}{'RAM MB':>8}{'WER':>7}{'acr':>9}{'terms':>9}"
    lines = [head, "-" * len(head)]
    for r in rows:
        if "error" in r:
            lines.append(f"{r['label']:18}{r['threads']:>4}  {r['error']}")
            continue
        acr = r.get("acronyms_plain", {})
        oth = r.get("terms_plain", {})
        lines.append(
            f"{r['label']:18}{r['threads']:>4}{r['cold_load_ms']:>9}{r['warm_median_ms']:>10}{r['warm_worst_ms']:>8}"
            f"{r['rtf']:>6}{str(r['peak_ram_mb'] or 'n/a'):>8}{r.get('wer', 0):>7}"
            f"{_frac(acr):>9}{_frac(oth):>9}")
    return "\n".join(lines)


def _frac(b: dict) -> str:
    return f"{b['hit']}/{b['ref']}" if b.get("ref") else "-"


def run(data_dir, prompt_text=None, samples=None, threads=THREADS, out=print) -> dict | None:
    """Score every engine on the samples. Engines that aren't downloaded or fail are reported, not fatal."""
    folder = Path(samples) if samples else Path(data_dir) / "stt-samples"
    pairs = [(w, w.with_suffix(".txt")) for w in sorted(folder.glob("*.wav")) if w.with_suffix(".txt").exists()]
    if not pairs:
        out(f"no samples in {folder}: add a .wav and a .txt with the same name (the exact words said)")
        return None
    names = [w.name for w, _ in pairs]
    refs = [t.read_text(encoding="utf-8").strip() for _, t in pairs]
    clips = [str(w) for w, _ in pairs]
    model_dir = os.environ.get("WHISPER_MODEL_DIR", "/data/models")
    rows = []
    for label, engine, model in ENGINES:
        for n in threads:
            spec = {"engine": engine, "model": model, "threads": n, "clips": clips, "model_dir": model_dir,
                    "prompt": prompt_text if engine == "whisper" else None}
            out(f"{label}, {n} threads ...")
            res = _spawn(spec)
            rows.append(_score(label, engine, model, n, res, refs, names))
    result = {"time": dt.datetime.now().isoformat(timespec="minutes"), "samples": names,
              "reference_words": sum(len(STT.words(r)) for r in refs), "cpu": f"{platform.machine()}, {os.cpu_count()} logical cores",
              "reps": REPS, "rows": rows}
    path = Path(data_dir) / RESULTS
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    out(_table(rows))
    return result


def last_result(data_dir) -> dict | None:
    f = Path(data_dir) / RESULTS
    try:
        return json.loads(f.read_text()) if f.exists() else None
    except (OSError, json.JSONDecodeError):
        return None


# ---------- recording samples from the admin page ----------

SAMPLE_RATE = 16000
MAX_SAMPLE_SECONDS = 60
MAX_SAMPLE_BYTES = 2_000_000          # 60 s of 16 kHz 16-bit mono is 1.92 MB, plus the header
SAMPLE_NAME = re.compile(r"[A-Za-z0-9_-]{1,40}")


def sample_dir(data_dir) -> Path:
    return Path(data_dir) / "stt-samples"


def sample_names(data_dir) -> list[str]:
    """The sample names come only from the .txt files in the folder. A name is never used as a path until it is in this list."""
    folder = sample_dir(data_dir)
    if not folder.is_dir():
        return []
    return sorted(p.stem for p in folder.glob("*.txt") if SAMPLE_NAME.fullmatch(p.stem))


def samples_status(data_dir) -> list[dict]:
    """Each sentence with its text and whether a recording is saved. Text only; no audio is returned."""
    folder = sample_dir(data_dir)
    out = []
    for name in sample_names(data_dir):
        out.append({"name": name, "text": (folder / f"{name}.txt").read_text(encoding="utf-8").strip(),
                    "recorded": (folder / f"{name}.wav").exists()})
    return out


def check_wav(body: bytes) -> None:
    """Raise ValueError unless the bytes are a 16 kHz mono 16-bit PCM WAV of at most MAX_SAMPLE_SECONDS."""
    if not body:
        raise ValueError("the recording is empty")
    if len(body) > MAX_SAMPLE_BYTES:
        raise ValueError("the recording is too large (max about one minute)")
    try:
        with wave.open(io.BytesIO(body), "rb") as w:
            channels, width, rate, frames = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    except (wave.Error, EOFError):
        raise ValueError("not a WAV file")
    if (channels, width, rate) != (1, 2, SAMPLE_RATE):
        raise ValueError("the recording must be 16 kHz mono 16-bit WAV")
    if frames == 0 or frames > MAX_SAMPLE_SECONDS * SAMPLE_RATE:
        raise ValueError("the recording must be between 1 second and one minute long")


def save_sample(data_dir, name: str, body: bytes) -> Path:
    """Save a recording as <name>.wav, once the name is one of the sentences and the WAV checks out."""
    if name not in sample_names(data_dir):
        raise ValueError("unknown sentence")
    check_wav(body)
    folder = sample_dir(data_dir)
    dst = folder / f"{name}.wav"
    tmp = folder / f"{name}.wav.part"
    tmp.write_bytes(body)
    os.replace(tmp, dst)
    return dst


# ---------- running the benchmark from the admin page (in the background; it takes minutes) ----------

_JOB = {"running": False, "progress": [], "error": None}
_JOB_LOCK = threading.Lock()


def start(data_dir, prompt_text=None, threads=THREADS) -> bool:
    """Start sttbench in a background thread. False if one is already running."""
    with _JOB_LOCK:
        if _JOB["running"]:
            return False
        _JOB.update(running=True, progress=[], error=None)

    def job():
        try:
            run(data_dir, prompt_text=prompt_text, threads=threads, out=lambda s: _JOB["progress"].append(s))
        except Exception as e:  # shown on the page; the page can run it again
            _JOB["error"] = str(e)[:200]
        finally:
            _JOB["running"] = False

    threading.Thread(target=job, daemon=True).start()
    return True


def job_status(data_dir) -> dict:
    return {"running": _JOB["running"], "progress": list(_JOB["progress"][-40:]), "error": _JOB["error"],
            "result": last_result(data_dir)}
