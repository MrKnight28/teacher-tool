"""The public tree must not carry private paths, the private account, real dates, or a personal budget."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".pytest_cache", ".venv", "venv"}
SKIP_SUFFIX = {".png", ".wav", ".pyc", ".onnx", ".bin"}
# Built from pieces so this file does not itself contain the private strings.
MARKERS = (
    "kyleknight" + "226@" + "gmail.com",
    "kyleknight" + "226",
    "Users\\" + "Knight",
    "Users/" + "Knight",
    "C:/Users/" + "Knight",
    "Users\\" + "Kyle",
    "Users/" + "Kyle",
    "C:/Users/" + "Kyle",
    "Teacher" + "AI",
    "Un" + "raid",
    "sei" + "dl",
    "Sei" + "dl",
    "2026-12-" + "23",
    "2026, 12, " + "23",
    "23/12/" + "2026",
    "12/23/" + "2026",
    "2026-11-" + "20",
    "2026, 11, " + "20",
    "2026-12-" + "02",
    "2026, 12, " + "2)",
    "2026-12-" + "03",
    "£" + "40",
    "£" + "30",
    "30" + "80",
    "5800" + "X",
    "Ry" + "zen",
)


def test_tree_has_no_private_markers():
    hits = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIX:
            continue
        data = path.read_bytes()
        if b"\0" in data[:4096]:
            continue
        text = data.decode("utf-8", "replace")
        rel = path.relative_to(ROOT).as_posix()
        for marker in MARKERS:
            if marker in text:
                hits.append(f"{rel}: {marker}")
    assert hits == []
