"""`python3 -m tutor ttsbench`: how fast the local voices start speaking on this PC.

Measures, for the representative sentence from the brief:
- cold load: the time to load the model the first time in the process
- whole sentence: synthesis time for the full sentence (warm, median of 5)
- first audio: synthesis of the first clause plus WAV encoding (warm, median of 5). This is the wait before sound starts.
Kokoro is swept over several ONNX thread counts; the fastest first-audio count is the one to use.
Results go to data/ttsbench.json. Nothing here logs or stores text.
"""
from __future__ import annotations
import datetime as dt
import json
import statistics as st
import time
from pathlib import Path

from .. import tts as TT

REP = "The purpose of authentication is to verify the identity of a user before allowing access to a system."
RUNS = 5


def _timed(fn, runs=RUNS):
    xs, last = [], None
    for _ in range(runs):
        t0 = time.perf_counter()
        last = fn()
        xs.append((time.perf_counter() - t0) * 1000)
    return st.median(xs), xs, last


def _bench(p, label: str, out) -> dict:
    t0 = time.perf_counter()
    p.load()
    cold = (time.perf_counter() - t0) * 1000
    first = TT.split_for_speech(REP)[0]
    p.synthesize(REP)  # one warm-up pass, not timed
    whole_ms, whole_runs, (audio, rate) = _timed(lambda: p.synthesize(REP))
    first_ms, first_runs, _ = _timed(lambda: _first_audio(p, first))
    row = {"voice": label, "cold_load_ms": round(cold), "whole_ms": round(whole_ms), "whole_audio_s": round(len(audio) / rate, 2),
           "first_audio_ms": round(first_ms), "first_audio_runs": [round(x) for x in first_runs],
           "first_clause": first}
    out(f"{label:24} cold load {row['cold_load_ms']:5} ms | whole sentence {row['whole_ms']:5} ms ({row['whole_audio_s']} s audio) "
        f"| first audio {row['first_audio_ms']:5} ms  runs {row['first_audio_runs']}")
    return row


def _first_audio(p, clause: str):
    audio, rate = p.synthesize(clause)
    return TT.to_wav(audio, rate), rate


def run(data_dir, threads=(4, 8, 16), out=print, with_extras=False) -> dict:
    result = {"time": dt.datetime.now().isoformat(timespec="minutes"), "kokoro": [], "piper": None}
    km, kv = TT.kokoro_paths()
    if km.exists() and kv.exists():
        for n in threads:
            result["kokoro"].append({"threads": n, **_bench(TT.KokoroProvider(threads=n), f"kokoro threads={n}", out)})
        best = min(result["kokoro"], key=lambda r: r["first_audio_ms"])
        result["kokoro_best_threads"] = best["threads"]
        out(f"fastest first audio: {best['threads']} threads")
    else:
        out("kokoro: skipped (files missing; run: python3 -m tutor fetch-voices)")
    if TT.piper_path().exists():
        result["piper"] = _bench(TT.PiperProvider(), "piper", out)
    else:
        out("piper: skipped (files missing; run: python3 -m tutor fetch-voices)")
    if with_extras:
        result["extras"] = extras(out)
    path = Path(data_dir) / "ttsbench.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2))
    return result


def last_result(data_dir) -> dict | None:
    f = Path(data_dir) / "ttsbench.json"
    try:
        return json.loads(f.read_text()) if f.exists() else None
    except (OSError, json.JSONDecodeError):
        return None


# ---------- extras: CPU use, inter-op threads, and Kokoro competing with Whisper ----------

def cpu_snapshot():
    """Total and idle jiffies from /proc/stat (the whole machine, as the container sees it)."""
    with open("/proc/stat") as f:
        vals = [int(x) for x in f.readline().split()[1:]]
    return sum(vals), vals[3] + vals[4]


def cpu_percent(a, b) -> float:
    total, idle = b[0] - a[0], b[1] - a[1]
    return round(100 * (1 - idle / total), 1) if total > 0 else 0.0


def extras(out=print) -> dict:
    """Run after the thread sweep. Everything here is measured on the machine it runs on."""
    import threading
    from .. import voice as V
    res = {}
    first = TT.split_for_speech(REP)[0]
    for inter in (1, 2):
        p = TT.KokoroProvider(threads=16, inter=inter)
        p.load()
        p.synthesize(REP)
        a = cpu_snapshot()
        med, runs, _ = _timed(lambda: _first_audio(p, first))
        b = cpu_snapshot()
        res[f"inter={inter}"] = {"first_audio_ms": round(med), "cpu_percent": cpu_percent(a, b)}
        out(f"kokoro threads=16 inter_op={inter}: first audio {round(med)} ms, CPU {cpu_percent(a, b)}% during the runs")
    # Kokoro alone, then Kokoro while Whisper transcribes the bundled clip in a loop (same process, same clip).
    p = TT.KokoroProvider(threads=16, inter=1)
    p.load()
    p.synthesize(REP)
    V._load_model()
    clip = V.BENCH_CLIP.read_bytes()
    V._local_transcribe(clip, "base.en", 5000, {})
    solo_k, _, _ = _timed(lambda: _first_audio(p, first), 5)
    stop, w_times = threading.Event(), []

    def whisper_loop():
        while not stop.is_set():
            t0 = time.perf_counter()
            V._local_transcribe(clip, "base.en", 5000, {})
            w_times.append((time.perf_counter() - t0) * 1000)

    solo_w_t = [] 
    t0 = time.perf_counter()
    for _ in range(3):
        t1 = time.perf_counter()
        V._local_transcribe(clip, "base.en", 5000, {})
        solo_w_t.append((time.perf_counter() - t1) * 1000)
    th = threading.Thread(target=whisper_loop, daemon=True)
    th.start()
    busy_k, _, _ = _timed(lambda: _first_audio(p, first), 5)
    stop.set()
    th.join(timeout=60)
    res["contention"] = {"kokoro_first_audio_alone_ms": round(solo_k), "kokoro_first_audio_with_whisper_ms": round(busy_k),
                         "whisper_alone_ms": round(st.median(solo_w_t)),
                         "whisper_with_kokoro_ms": round(st.median(w_times)) if w_times else None}
    out(f"contention: kokoro first audio alone {round(solo_k)} ms, with whisper running {round(busy_k)} ms; "
        f"whisper alone {round(st.median(solo_w_t))} ms, with kokoro {round(st.median(w_times)) if w_times else 'n/a'} ms")
    return res
