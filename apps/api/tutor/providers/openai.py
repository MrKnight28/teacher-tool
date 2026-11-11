"""OpenAI speech-to-text (Whisper). Paid, and used only if TRANSCRIBE=openai."""
from __future__ import annotations
from . import http

TRANSCRIBE_URL = "https://api.openai.com/v1/audio/transcriptions"
MODELS_URL = "https://api.openai.com/v1/models"


def transcribe(audio: bytes, mime: str, key: str, post=None) -> str:
    post = post or http.post_json
    ext = "webm" if "webm" in mime else "ogg" if "ogg" in mime else "mp4" if "mp4" in mime else "wav"
    body, ctype = http.multipart({"model": "whisper-1", "language": "en"}, "file", f"question.{ext}", audio,
                                 mime or "audio/webm")
    out = post(TRANSCRIBE_URL, body, {"Authorization": f"Bearer {key}", "Content-Type": ctype})
    return (out.get("text") or "").strip()


def models(key: str) -> list[dict]:
    return http.get_json(MODELS_URL, {"Authorization": f"Bearer {key}"}).get("data", [])
