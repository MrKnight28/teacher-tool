"""Voice in and out. Speech-to-text runs on this PC (faster-whisper) by default; Gemini speech is optional.

Only these services ever receive audio or text for speech. Costs are estimates (see the constants). They count toward
the monthly cap, except Gemini on the free tier, which costs nothing. Callers pass a `timing` dict to collect step
times (see timing.py); this module never logs text.
"""
from __future__ import annotations
import io
import os
import re
import struct
import threading
import time
from pathlib import Path

from .timing import ms_since
from .providers import gemini, openai

WHISPER_MODELS = ("tiny.en", "base.en", "small.en")
DEFAULT_WHISPER = "base.en"
# Estimates in USD, deliberately on the high side so the cap is never under-counted. Paid options only.
WHISPER_USD_PER_REQUEST = 0.01       # OpenAI Whisper; a question is well under a minute
TTS_USD_PER_CHAR = 0.00003           # Gemini on the paid tier
MAX_AUDIO_BYTES = 3_000_000          # about two minutes of recorded audio
MAX_SPEAK_CHARS = 1500
VAD_MIN_MS = 3000                    # shorter clips skip the voice-activity filter, which costs more time than it saves
BENCH_CLIP = Path(__file__).with_name("assets") / "voicebench-5s.wav"


def engine() -> str:
    """'local' (default, free, on this PC) or 'openai' (paid, only if TRANSCRIBE=openai)."""
    return "openai" if os.environ.get("TRANSCRIBE", "local").strip().lower() == "openai" else "local"


def wav_from_pcm(pcm: bytes, rate: int = 24000) -> bytes:
    """Gemini returns raw 16-bit mono PCM; browsers play WAV."""
    data_len = len(pcm)
    header = b"RIFF" + struct.pack("<I", 36 + data_len) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
    header += b"data" + struct.pack("<I", data_len)
    return header + pcm


# ---------- local Whisper ----------

_MODEL = None
_MODEL_NAME = None
_LOAD_LOCK = threading.Lock()   # one load at a time (the background preload and the first question can race)
_RUN_LOCK = threading.Lock()    # one transcription at a time on the CPU


def _model_name(name=None) -> str:
    """The chosen model: the admin setting, then WHISPER_MODEL from the environment, then base.en."""
    for candidate in (name, os.environ.get("WHISPER_MODEL")):
        if candidate and candidate.strip() in WHISPER_MODELS:
            return candidate.strip()
    return DEFAULT_WHISPER


def _warm_up(model) -> None:
    """One short silent clip, so the first real question doesn't pay for the first-run set-up."""
    import numpy as np
    segments, _ = model.transcribe(np.zeros(8000, dtype=np.float32), language="en", beam_size=1, vad_filter=False)
    list(segments)


def _load_model(name=None):
    """Load a speech model once (thread-safe). Returns (model, wait_ms): the wait includes any load in progress."""
    global _MODEL, _MODEL_NAME
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError("local speech recognition is not installed in this build")
    name = _model_name(name)
    t0 = time.perf_counter()
    with _LOAD_LOCK:
        if _MODEL is None or _MODEL_NAME != name:
            model_dir = os.environ.get("WHISPER_MODEL_DIR", "/data/models")
            try:
                os.makedirs(model_dir, exist_ok=True)
                # 8 threads measured fastest on a 16-core PC (358 ms vs 956 ms with 16, see docs/VOICE-DEBUG.md).
                model = WhisperModel(name, device="cpu", compute_type="int8",
                                     cpu_threads=min(8, os.cpu_count() or 4), download_root=model_dir)
            except Exception as e:  # no internet on the first run, or a bad model name
                raise RuntimeError("could not load the speech model; it downloads once, so it needs internet the first time "
                                   f"({str(e)[:120]})")
            _warm_up(model)
            _MODEL, _MODEL_NAME = model, name
    return _MODEL, ms_since(t0)


def preload(name=None) -> None:
    """Load the speech model in the background, so the first question doesn't wait for it. Never raises."""
    if engine() == "openai":
        return
    try:
        _load_model(name)
    except RuntimeError:
        pass  # the first question reports the same problem in plain words


def _local_transcribe(audio: bytes, name=None, duration_ms=None, timing=None, prompt=None) -> str:
    """Whisper on this PC. Clips under VAD_MIN_MS skip the voice-activity filter (it costs more time than it saves)."""
    try:
        from faster_whisper.audio import decode_audio
    except ImportError:
        raise RuntimeError("local speech recognition is not installed in this build")
    t0 = time.perf_counter()
    try:
        samples = decode_audio(io.BytesIO(audio), sampling_rate=16000)
    except Exception:
        raise ValueError("recording could not be read")
    decode_ms = ms_since(t0)
    model, wait_ms = _load_model(name)
    vad = duration_ms is None or duration_ms >= VAD_MIN_MS
    t1 = time.perf_counter()
    with _RUN_LOCK:
        extra = {"initial_prompt": prompt} if prompt else {}
        segments, _ = model.transcribe(samples, language="en", beam_size=1, vad_filter=vad, **extra)
        text = " ".join(s.text.strip() for s in segments).strip()
    if timing is not None:
        timing.update(decode_ms=decode_ms, model_wait_ms=wait_ms, transcribe_ms=ms_since(t1),
                      audio_s=round(len(samples) / 16000, 2), vad=int(vad), model=transcribe_label(name))
    return text


def transcribe_label(name=None) -> str:
    """The usage row's model column: 'local:base.en', or 'openai:whisper-1' only for the paid option."""
    return "openai:whisper-1" if engine() == "openai" else f"local:whisper-{_model_name(name)}"


def transcribe_cost() -> float:
    """Local transcription costs nothing; only the paid OpenAI option is estimated."""
    return WHISPER_USD_PER_REQUEST if engine() == "openai" else 0.0


def transcribe(audio: bytes, mime: str, *, duration_ms=None, model=None, timing=None, post=None, prompt=None) -> str:
    """Speech-to-text from the raw recorded bytes. Local Whisper by default; OpenAI only if TRANSCRIBE=openai (paid).

    Raises RuntimeError with a plain message if it can't; ValueError for a bad or oversized recording.
    """
    if not audio:
        raise ValueError("recording could not be read")
    if len(audio) > MAX_AUDIO_BYTES:
        raise ValueError("recording too long (max about two minutes)")
    if engine() != "openai":
        return _local_transcribe(audio, model, duration_ms, timing, prompt).strip()
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("TRANSCRIBE=openai needs a valid OPENAI_API_KEY")
    t0 = time.perf_counter()
    text = openai.transcribe(audio, mime, key, post=post)
    if timing is not None:
        timing.update(transcribe_ms=ms_since(t0), model=transcribe_label(), vad=0)
    return text


# ---------- Gemini speech ----------

def speak(text: str, post=None, timing=None) -> bytes:
    """Gemini text-to-speech, returned as WAV bytes. Raises RuntimeError with a plain message if it can't."""
    text = text.strip()[:MAX_SPEAK_CHARS]
    if not text:
        raise ValueError("nothing to read")
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError("Spoken answers need a Gemini key (set it in setup)")
    return wav_from_pcm(gemini.speech_pcm(text, key, post=post, timing=timing))


def speak_cost(text: str, billing: str = "free") -> float:
    """Gemini's free tier costs nothing, so it doesn't count toward the cap. Only the paid tier is estimated."""
    if billing != "paid":
        return 0.0
    return len(text[:MAX_SPEAK_CHARS]) * TTS_USD_PER_CHAR


def status(settings: dict | None = None) -> dict:
    """What the page needs up front: where speech-to-text runs, whether spoken replies can work, and the voice choice."""
    s = settings or {}
    return {"transcribe": engine(), "speak": bool(os.environ.get("GEMINI_API_KEY")), "model_ready": _MODEL is not None,
            "whisper_model": _model_name(s.get("whisper_model")), "lesson_voice": s.get("lesson_voice", "kokoro"),
            "tts_fallback": s.get("tts_fallback", "piper"), "gemini_billing": s.get("gemini_billing", "free")}


# ---------- sentences (speaking answers as they stream) ----------

# A sentence ends at . ! or ? (optionally followed by a closing quote or bracket), then whitespace.
_BOUNDARY = re.compile(r"""[.!?]['")\]]?\s+""")


class SentenceSplitter:
    """Takes text in pieces and returns each sentence once it is complete. The unfinished end waits for more text."""

    def __init__(self):
        self.buf = ""

    def feed(self, piece: str) -> list[str]:
        self.buf += piece
        out, last = [], 0
        for m in _BOUNDARY.finditer(self.buf):
            s = self.buf[last:m.end()].strip()
            if s:
                out.append(s)
            last = m.end()
        self.buf = self.buf[last:]
        return out

    def flush(self) -> list[str]:
        rest, self.buf = self.buf.strip(), ""
        return [rest] if rest else []


def split_sentences(text: str) -> list[str]:
    s = SentenceSplitter()
    return s.feed(text) + s.flush()
