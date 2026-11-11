"""OpenRouter: chat and vision (pay per token), plus the model list and key check the setup uses."""
from __future__ import annotations
import json
from . import http

CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
MODELS_URL = "https://openrouter.ai/api/v1/models"
KEY_URL = "https://openrouter.ai/api/v1/key"


def chat(body: dict, key: str) -> dict:
    return http.post_json(CHAT_URL, json.dumps(body).encode(),
                          {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, timeout=120)


def models(key: str) -> list[dict]:
    return http.get_json(MODELS_URL, {"Authorization": f"Bearer {key}"}).get("data", [])


def key_info(key: str) -> dict:
    return http.get_json(KEY_URL, {"Authorization": f"Bearer {key}"}).get("data", {})
