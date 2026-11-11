"""What gets installed into the image is pinned, so a rebuild is the thing that was tested."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_the_dockerfile_pins_the_base_image_and_claude_code():
    text = (ROOT / "apps" / "api" / "Dockerfile").read_text()
    assert re.search(r"^FROM node:22-bookworm-slim@sha256:[0-9a-f]{64}$", text, re.M)
    assert re.search(r"npm install -g @anthropic-ai/claude-code@\d+\.\d+\.\d+ ", text)


def test_direct_python_dependencies_are_exact():
    text = (ROOT / "apps" / "api" / "pyproject.toml").read_text()
    deps = re.findall(r'"([A-Za-z0-9_.\-]+(?:\[[a-z]+\])?)([<>=!~]+)([^"]+)"', text.split("[project.optional-dependencies]")[0]
                      + text.split("voice = ")[1].split("\n")[0])
    names = {n.lower() for n, _, _ in deps}
    assert {"pyyaml", "tzdata", "faster-whisper", "kokoro-onnx", "piper-tts", "onnx-asr[cpu]"} <= names
    assert all(op == "==" for _, op, _ in deps), deps


def test_the_openclaw_image_is_a_pinned_tag():
    text = (ROOT / "docker-compose.yml").read_text()
    assert "ghcr.io/openclaw/openclaw:2026.9.8" in text and "openclaw:latest" not in text
