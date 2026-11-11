"""Blind voice test: the same sentences in several voices, shown in random order with the voice names hidden.

Clips are built once into data/blindtest. The voice of each clip is only in key.json, which the routes never send.
Results are shown only when every clip has a score.
"""
from __future__ import annotations
import json
import random
import secrets
from pathlib import Path

from .. import tts as TT

SENTENCES = [
    "The purpose of authentication is to verify the identity of a user before allowing access to a system.",
    "A firewall filters traffic between networks, and an IDS detects suspicious activity.",
    "Least privilege gives each user only the access the job needs, so a breach stays small.",
]
VOICES = [("kokoro", "af_heart"), ("kokoro", "bf_emma"), ("kokoro", "bf_isabella"), ("piper", None)]


def _dir(data_dir) -> Path:
    return Path(data_dir) / "blindtest"


def _label(kind, voice) -> str:
    return f"local:kokoro-{voice}" if kind == "kokoro" else f"local:piper-{TT.piper_path().stem}"


def build(data_dir, out=print) -> dict:
    """Synthesize every sentence in every voice (once). Returns the key: clip id -> voice label, sentence number."""
    root = _dir(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    key_file = root / "key.json"
    key = json.loads(key_file.read_text()) if key_file.exists() else {}
    have = {(v["sentence"], v["voice"]) for v in key.values()}
    for n, sentence in enumerate(SENTENCES, 1):
        for kind, voice in VOICES:
            label = _label(kind, voice)
            if (n, label) in have:
                continue
            p = TT.KokoroProvider(voice=voice) if kind == "kokoro" else TT.PiperProvider()
            audio, rate = p.synthesize(sentence)
            clip = secrets.token_hex(4)
            (root / f"{clip}.wav").write_bytes(TT.to_wav(audio, rate))
            key[clip] = {"sentence": n, "voice": label}
            out(f"built sentence {n} in {label}")
    key_file.write_text(json.dumps(key, indent=2))
    return key


def playlist(data_dir, rng=None) -> list[dict]:
    """The clips in random order, without voice names. Each has a sentence number and an audio id."""
    key = json.loads((_dir(data_dir) / "key.json").read_text()) if (_dir(data_dir) / "key.json").exists() else {}
    ids = list(key)
    (rng or random).shuffle(ids)
    return [{"id": i, "sentence": key[i]["sentence"], "text": SENTENCES[key[i]["sentence"] - 1]} for i in ids]


def clip_path(data_dir, clip_id: str):
    if not clip_id.isalnum():
        return None
    f = _dir(data_dir) / f"{clip_id}.wav"
    return f if f.exists() else None


def vote(data_dir, clip_id: str, score: int) -> bool:
    key = json.loads((_dir(data_dir) / "key.json").read_text()) if (_dir(data_dir) / "key.json").exists() else {}
    if clip_id not in key or not (1 <= int(score) <= 5):
        return False
    f = _dir(data_dir) / "votes.json"
    votes = json.loads(f.read_text()) if f.exists() else {}
    votes[clip_id] = int(score)
    f.write_text(json.dumps(votes, indent=2))
    return True


def results(data_dir) -> dict:
    """Scores per voice, shown only once every clip has been rated."""
    key = json.loads((_dir(data_dir) / "key.json").read_text()) if (_dir(data_dir) / "key.json").exists() else {}
    f = _dir(data_dir) / "votes.json"
    votes = json.loads(f.read_text()) if f.exists() else {}
    rated = sum(1 for k in key if k in votes)
    out = {"clips": len(key), "rated": rated, "done": bool(key) and rated == len(key)}
    if out["done"]:
        by = {}
        for k, v in key.items():
            by.setdefault(v["voice"], []).append(votes[k])
        out["by_voice"] = {label: round(sum(s) / len(s), 2) for label, s in sorted(by.items())}
    return out
