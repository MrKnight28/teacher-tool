"""Google Gemini speech (text-to-speech). Free on the free tier; estimated only on the paid tier."""
from __future__ import annotations
import base64
import json
import time
import os
from . import http
from ..timing import ms_since

SPEECH_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_TTS_MODEL = "gemini-2.5-flash-preview-tts"
DEFAULT_VOICE = "Kore"


def speech_pcm(text: str, key: str, post=None, timing=None) -> bytes:
    """Raw 16-bit mono PCM at 24 kHz for one piece of text. Raises RuntimeError if the service returns no audio."""
    post = post or http.post_json
    model = os.environ.get("GEMINI_TTS_MODEL", DEFAULT_TTS_MODEL)
    voice = os.environ.get("GEMINI_VOICE", DEFAULT_VOICE)
    body = json.dumps({
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {"responseModalities": ["AUDIO"],
                             "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}},
    }).encode()
    t0 = time.perf_counter()
    out = post(SPEECH_URL.format(model=model), body, {"x-goog-api-key": key, "Content-Type": "application/json"})
    try:
        pcm = base64.b64decode(out["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    except (KeyError, IndexError, TypeError, ValueError):
        raise RuntimeError("the speech service returned no audio")
    if timing is not None:
        timing.update(gemini_ms=ms_since(t0), gemini_req_bytes=len(body),
                      audio_s=round(len(pcm) / 48000, 2))
    return pcm


def models(key: str) -> list[dict]:
    return http.get_json(MODELS_URL, {"x-goog-api-key": key}).get("models", [])
