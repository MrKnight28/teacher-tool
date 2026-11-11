"""Timing for the voice and chat routes. Logs step names and numbers only: never the question, the answer or lesson text.

The last 10 server rows and the last 10 browser rows are kept in memory for the admin panel (they clear on restart).
"""
from __future__ import annotations
import datetime as dt
import logging
import re
import statistics
import threading
import time
from collections import OrderedDict, deque

log = logging.getLogger("tutor.timing")
KINDS = ("ask", "read", "answer", "chat")
FIELDS = {
    "request_bytes", "decode_ms", "model_wait_ms", "transcribe_ms", "audio_s", "text_chars", "vad", "model",
    "first_ms", "claude_ms", "reply_chars", "sentences", "gemini_ms", "gemini_req_bytes", "total_ms", "tts_ms", "warm",
}
BROWSER_FIELDS = {"mic_to_upload_ms", "upload_to_transcript_ms", "transcript_to_reply_ms", "reply_to_audio_ms",
                  "read_to_audio_ms"}
_LOCK = threading.Lock()
_SERVER: deque = deque(maxlen=10)
_BROWSER: deque = deque(maxlen=10)


def ms_since(t0: float) -> float:
    return (time.perf_counter() - t0) * 1000


def clean(fields: dict, allowed: set) -> dict:
    """Only whitelisted keys, numbers in range, and short model labels. Anything else is refused, so text can't slip in."""
    out = {}
    for k, v in fields.items():
        if k not in allowed:
            raise ValueError(f"not a timing field: {k}")
        if k == "model":
            if not (isinstance(v, str) and re.fullmatch(r"[\w.:\-]{1,40}", v)):
                raise ValueError("bad model label")
            out[k] = v
        elif isinstance(v, bool) or not isinstance(v, (int, float)) or not (0 <= v <= 1e9):
            raise ValueError(f"{k} must be a number")
        else:
            out[k] = round(v, 1) if isinstance(v, float) else v
    return out


def record(kind: str, source: str = "server", **fields) -> dict:
    if kind not in KINDS:
        raise ValueError("unknown timing kind")
    data = clean(fields, BROWSER_FIELDS if source == "browser" else FIELDS)
    row = {"time": dt.datetime.now().strftime("%H:%M:%S"), "kind": kind, **data}
    log.info("voice %s %s %s", source, kind, " ".join(f"{k}={v}" for k, v in data.items()))
    with _LOCK:
        (_BROWSER if source == "browser" else _SERVER).append(row)
    return row


def recent() -> dict:
    with _LOCK:
        return {"server": list(_SERVER), "browser": list(_BROWSER)}


# ---------- one chain per spoken question: browser and server steps under one id ----------

CHAIN_STEPS = ("t_transcript", "t_reply", "t_tts_ready", "t_audio")  # browser: ms from mic release
CHAIN_SERVER = ("transcribe_ms", "chat_first_ms", "tts_ms")          # server: step durations
CHAIN_ID = re.compile(r"[a-z0-9-]{8,40}")
_CHAINS: "OrderedDict[str, dict]" = OrderedDict()
CHAIN_KEEP = 50


def chain_add(chain, **fields) -> None:
    """Merge numbers into the chain with this id. A missing or badly formed id is ignored, so nothing is stored under it."""
    if not chain or not CHAIN_ID.fullmatch(str(chain)):
        return
    data = clean(fields, set(CHAIN_STEPS) | set(CHAIN_SERVER))
    if not data:
        return
    with _LOCK:
        row = _CHAINS.setdefault(str(chain), {"id": str(chain)})
        row.update(data)
        while len(_CHAINS) > CHAIN_KEEP:
            _CHAINS.popitem(last=False)
    log.info("voice chain %s %s", chain, " ".join(f"{k}={v}" for k, v in data.items()))


def chains_summary() -> dict:
    """The last 10 complete questions (all browser steps present) and the median of each step across complete ones."""
    with _LOCK:
        rows = [dict(v) for v in _CHAINS.values()]
    complete = [r for r in rows if all(k in r for k in ("t_transcript", "t_reply", "t_tts_ready", "t_audio"))]
    keys = CHAIN_STEPS + CHAIN_SERVER
    medians = {k: round(statistics.median(r[k] for r in complete if k in r)) for k in keys
               if any(k in r for r in complete)}
    return {"chains": complete[-10:][::-1], "medians": medians, "complete": len(complete), "started": len(rows)}
