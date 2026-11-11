"""`python3 -m tutor voicebench`: how long speech takes on this PC.

Whisper runs on the bundled 5-second clip (median of 3 runs, after the model is loaded and warmed up).
Gemini runs a 1-sentence and a 10-sentence text, but only if GEMINI_API_KEY is set, because those calls use the free-tier quota.
The results go to data/voicebench.json, where the admin page shows them next to the Whisper model choice.
"""
from __future__ import annotations
import datetime as dt
import json
import os
import statistics
from pathlib import Path

from .. import voice as V

ONE = "A firewall filters traffic between networks using rules you define."
TEN = [
    "A firewall filters traffic between networks using rules you define.",
    "Stateful firewalls remember each connection and allow replies to it.",
    "A proxy forwards requests on behalf of a client, which hides the client address.",
    "An IDS detects suspicious activity and alerts, while an IPS also blocks it.",
    "Port security limits which MAC addresses can use a switch port.",
    "A VPN encrypts traffic across an untrusted network to a remote endpoint.",
    "Segmentation splits a network so a breach in one zone stays contained.",
    "Least privilege gives each user only the access the job needs.",
    "MFA needs two or more different kinds of proof before access is granted.",
    "Hashing checks integrity, while encryption protects confidentiality.",
]
RESULTS = "voicebench.json"


def whisper(model: str, runs: int = 3) -> dict:
    audio = V.BENCH_CLIP.read_bytes()
    V._load_model(model)  # loads and warms the model, so the timed runs below don't include that
    rows = []
    for _ in range(runs):
        timing: dict = {}
        V._local_transcribe(audio, model, 5000, timing)
        rows.append(timing["decode_ms"] + timing["model_wait_ms"] + timing["transcribe_ms"])
    return {"model": model, "clip_s": timing["audio_s"], "ms": round(statistics.median(rows)), "runs": [round(r) for r in rows]}


def gemini(runs: int = 2) -> dict:
    out = {}
    for label, text in (("one_sentence", ONE), ("ten_sentences", " ".join(TEN))):
        rows = []
        for _ in range(runs):
            timing: dict = {}
            V.speak(text, timing=timing)
            rows.append({"ms": round(timing["gemini_ms"]), "audio_s": timing["audio_s"]})
        out[label] = {"chars": len(text), "ms": round(statistics.median(r["ms"] for r in rows)), "runs": rows}
    return out


def run(data_dir, models=None, out=print) -> dict:
    result = {"time": dt.datetime.now().isoformat(timespec="minutes"), "whisper": [], "gemini": None}
    if V.engine() == "openai":
        out("whisper: skipped (TRANSCRIBE=openai, so speech-to-text runs on OpenAI)")
    else:
        for m in models or [V._model_name()]:
            r = whisper(m)
            result["whisper"].append(r)
            out(f"whisper {m:8} {r['ms']:6} ms  (5.0 s clip, median of {len(r['runs'])}; runs {r['runs']})")
    if os.environ.get("GEMINI_API_KEY"):
        try:
            result["gemini"] = gemini()
            for label, g in result["gemini"].items():
                out(f"gemini {label:14} {g['ms']:6} ms  ({g['chars']} characters; audio {g['runs'][0]['audio_s']} s)")
        except (RuntimeError, OSError, ValueError) as e:
            result["gemini"] = {"error": str(e)[:160]}
            out(f"gemini: failed ({str(e)[:160]})")
    else:
        out("gemini: skipped (no GEMINI_API_KEY set)")
    path = Path(data_dir) / RESULTS
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2))
    return result


def last_result(data_dir) -> dict | None:
    f = Path(data_dir) / RESULTS
    try:
        return json.loads(f.read_text()) if f.exists() else None
    except (OSError, json.JSONDecodeError):
        return None
