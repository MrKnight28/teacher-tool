"""Local text-to-speech for the lesson voice. Kokoro is the primary voice; Piper is the explicit fallback.

Both run on this PC: no API key, no network after the files are fetched once (`python3 -m tutor fetch-voices`), no cost.
Each provider loads its model once and keeps it resident. One lock serialises synthesis, so only one TTS job runs at a
time. A fallback runs only if the primary fails before it produces audio, so the same sentence never plays twice.

Model files live under the writable data folder (the container's root filesystem is read-only).
"""
from __future__ import annotations
import io
import logging
import os
import re
import threading
import time
import urllib.request
import wave
from pathlib import Path

log = logging.getLogger("tutor.tts")

MODELS_DIR = Path(os.environ.get("TUTOR_MODELS_DIR", "/data/models"))  # the writable data volume, never the image
KOKORO_DIR = MODELS_DIR / "kokoro"
PIPER_DIR = MODELS_DIR / "piper"
KOKORO_FILES = {
    # float32 is about 4x faster than the int8 file on this CPU (measured; see docs/VOICE-DEBUG.md)
    "kokoro-v1.0.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
    "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
}
PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/"
PIPER_FILES = ["en_US-lessac-medium.onnx", "en_US-lessac-medium.onnx.json"]
MAX_CHARS = 1500
DEFAULT_KOKORO_VOICE = "af_heart"  # US English; not compared by ear yet (see docs/VOICE-DEBUG.md)
# Long sentences go out in clauses so the first sound starts sooner (measured: 4.1 s clause 0.8-0.9 s vs whole 6.4 s sentence 1.4 s).
CLAUSE_BREAK = re.compile(r"[,;:](?=\s)|\s(?=(?:before|after|while|because|which|when|so that)\s)")
CLAUSE_MIN_FIRST = 40
CLAUSE_MIN_REST = 15


def kokoro_paths() -> tuple[Path, Path]:
    return (Path(os.environ.get("KOKORO_MODEL_PATH") or KOKORO_DIR / "kokoro-v1.0.onnx"),
            Path(os.environ.get("KOKORO_VOICES_PATH") or KOKORO_DIR / "voices-v1.0.bin"))


def piper_path() -> Path:
    return Path(os.environ.get("PIPER_MODEL_PATH") or PIPER_DIR / "en_US-lessac-medium.onnx")


def ready() -> dict:
    """Which local voices have their files. Cheap: only checks that the files exist."""
    km, kv = kokoro_paths()
    return {"kokoro": km.exists() and kv.exists(), "piper": piper_path().exists()}


# SHA-256 of each file, as downloaded and checked on this PC. A file that doesn't match is never used. See LICENSES.md.
SHA256 = {
    "kokoro-v1.0.onnx": "7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5",
    "voices-v1.0.bin": "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
    "en_US-lessac-medium.onnx": "5efe09e69902187827af646e1a6e9d269dee769f9877d17b16b1b46eeaaf019f",
    "en_US-lessac-medium.onnx.json": "efe19c417bed055f2d69908248c6ba650fa135bc868b0e6abb3da181dab690a0",
}


def sha256_file(path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(out=print, download=urllib.request.urlretrieve) -> None:
    """Download the voice files once and check each SHA-256. Needs internet only for this command; afterwards everything runs offline."""
    targets = [(KOKORO_DIR / name, url) for name, url in KOKORO_FILES.items()]
    targets += [(PIPER_DIR / name, PIPER_BASE + name) for name in PIPER_FILES]
    for dst, url in targets:
        dst.parent.mkdir(parents=True, exist_ok=True)
        digest = SHA256[dst.name]
        if dst.exists() and sha256_file(dst) == digest:
            out(f"ok {dst} (checksum matches)")
            continue
        out(f"fetching {dst.name} ...")
        tmp = dst.with_suffix(dst.suffix + ".part")
        download(url, tmp)
        if sha256_file(tmp) != digest:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"checksum mismatch for {dst.name}: not saved. Check the download or the release.")
        os.replace(tmp, dst)
        out(f"saved {dst} ({dst.stat().st_size // 1_000_000} MB, checksum matches)")


def split_for_speech(sentence: str) -> list[str]:
    """Split a long sentence at a comma or a clause word, so the first clause can be spoken sooner.
    Short sentences stay whole. The browser has the same rule in splitForSpeech (keep them in step)."""
    s = sentence.strip()
    if len(s) < 60:
        return [s] if s else []
    pieces, rest = [], s
    while True:
        cut = -1
        for m in CLAUSE_BREAK.finditer(rest):
            c = m.end() if m.group() in ",;:" else m.start()
            if c >= CLAUSE_MIN_FIRST:
                cut = c
                break
        if cut < 0 or len(rest) - cut < CLAUSE_MIN_REST:
            break
        pieces.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    pieces.append(rest)
    return [p for p in pieces if p]


def to_wav(audio, rate: int) -> bytes:
    import numpy as np
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


class KokoroProvider:
    """Kokoro-82M through ONNX Runtime on the CPU. Loaded once, on first use, then kept."""

    def __init__(self, voice: str | None = None, threads: int | None = None, inter: int = 1):
        self.voice = voice or os.environ.get("KOKORO_VOICE", DEFAULT_KOKORO_VOICE)
        self.threads = threads or int(os.environ.get("KOKORO_THREADS", "16"))
        self.inter = inter
        self._kokoro = None
        self._lock = threading.Lock()

    def label(self) -> str:
        return f"local:kokoro-{self.voice}"

    def load(self):
        with self._lock:
            if self._kokoro is None:
                model, voices = kokoro_paths()
                if not (model.exists() and voices.exists()):
                    raise RuntimeError("Kokoro voice files are missing (run: python3 -m tutor fetch-voices)")
                # espeak-ng unpacks its library into TMPDIR; the container's /tmp is noexec, so TMPDIR is /data/tmp.
                os.makedirs(os.environ.get("TMPDIR", "/tmp"), exist_ok=True)
                try:
                    import onnxruntime as ort
                    from kokoro_onnx import Kokoro
                except ImportError:
                    raise RuntimeError("Kokoro is not installed in this build")
                so = ort.SessionOptions()
                so.intra_op_num_threads = self.threads
                so.inter_op_num_threads = self.inter
                sess = ort.InferenceSession(str(model), sess_options=so, providers=["CPUExecutionProvider"])
                self._kokoro = Kokoro.from_session(sess, str(voices))
        return self._kokoro

    def synthesize(self, text: str):
        audio, rate = self.load().create(text, voice=self.voice, lang="en-us")
        return audio, rate


class PiperProvider:
    """Piper (piper-tts, GPL-3.0) with a small English voice. Loaded once, on first use, then kept."""

    def __init__(self):
        self.model = piper_path()
        self.voice_name = self.model.stem
        self._piper = None
        self._lock = threading.Lock()

    def label(self) -> str:
        return f"local:piper-{self.voice_name}"

    def load(self):
        with self._lock:
            if self._piper is None:
                if not self.model.exists():
                    raise RuntimeError("Piper voice file is missing (run: python3 -m tutor fetch-voices)")
                try:
                    from piper import PiperVoice
                except ImportError:
                    raise RuntimeError("Piper is not installed in this build")
                self._piper = PiperVoice.load(str(self.model))
        return self._piper

    def synthesize(self, text: str):
        import numpy as np
        voice = self.load()
        chunks = list(voice.synthesize(text))
        if not chunks:
            raise RuntimeError("Piper returned no audio")
        return np.concatenate([c.audio_float_array for c in chunks]), voice.config.sample_rate


_PROVIDERS: dict = {}
_PROVIDERS_LOCK = threading.Lock()
_TTS_LOCK = threading.Lock()  # one synthesis at a time on the server


def provider(name: str):
    with _PROVIDERS_LOCK:
        if name not in _PROVIDERS:
            if name == "kokoro":
                _PROVIDERS[name] = KokoroProvider()
            elif name == "piper":
                _PROVIDERS[name] = PiperProvider()
            else:
                raise ValueError("unknown local voice")
        return _PROVIDERS[name]


def synthesize(text: str, primary: str = "kokoro", fallback: str | None = "piper", cache=None) -> tuple[bytes, str, dict]:
    """One sentence to WAV bytes. Returns (wav, usage label, timing). Raises RuntimeError if no local voice works.

    With a cache, a hit returns the stored WAV without calling any provider. Only audio from the primary voice is
    stored, so a fallback's audio is never served later under the primary's key.
    """
    text = text.strip()[:MAX_CHARS]
    if not re.search(r"[A-Za-z0-9]", text):
        raise ValueError("nothing to read")
    primary_label = provider(primary).label()
    key = cache.key(primary_label, text) if cache is not None else None
    if cache is not None:
        hit = cache.get(key)
        if hit is not None:
            import wave
            with wave.open(io.BytesIO(hit)) as w:
                audio_s = round(w.getnframes() / w.getframerate(), 2)
            return hit, primary_label, {"tts_ms": 0.0, "audio_s": audio_s, "provider": "cache"}
    names = [primary] + ([fallback] if fallback and fallback != primary else [])
    errors = []
    with _TTS_LOCK:
        for name in names:
            p = provider(name)
            t0 = time.perf_counter()
            try:
                audio, rate = p.synthesize(text)
            except Exception as e:  # missing files, a failed load, or a runtime error: try the next voice
                errors.append(f"{name}: {str(e)[:120]}")
                log.warning("voice %s failed, trying the next voice: %s", name, str(e)[:120])
                continue
            tts_ms = (time.perf_counter() - t0) * 1000
            timing = {"tts_ms": round(tts_ms, 1), "audio_s": round(len(audio) / rate, 2), "provider": name}
            wav = to_wav(audio, rate)
            if cache is not None and name == primary:
                cache.put(key, wav)
            return wav, p.label(), timing
    raise RuntimeError("no local voice is ready: " + "; ".join(errors)[:200])


# ---------- slide audio cache (built after each lesson is written; served on Read) ----------

CACHE_DIR = Path(os.environ.get("TUTOR_CACHE_DIR", "/data/cache")) / "tts"
CACHE_MAX_AGE_S = 7 * 86400
CACHE_MAX_BYTES = int(os.environ.get("TTS_CACHE_MAX_MB", "500")) * 1_000_000


class SpeechCache:
    """WAV files named by a hash of (voice label, spoken text). Written once, served until pruned."""

    def __init__(self, root=None):
        self.root = Path(root) if root else CACHE_DIR

    @staticmethod
    def key(label: str, spoken: str) -> str:
        import hashlib
        return hashlib.sha256(f"{label}\n{spoken}".encode()).hexdigest()

    def get(self, key: str):
        f = self.root / f"{key}.wav"
        return f.read_bytes() if f.exists() else None

    def put(self, key: str, wav: bytes) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.root / f"{key}.part"
        tmp.write_bytes(wav)
        os.replace(tmp, self.root / f"{key}.wav")

    def size(self) -> int:
        return sum(f.stat().st_size for f in self.root.glob("*.wav")) if self.root.exists() else 0

    def prune(self, now: float | None = None, max_age: int = CACHE_MAX_AGE_S, max_bytes: int = CACHE_MAX_BYTES) -> dict:
        """Delete files older than max_age, then the oldest files until the total is under max_bytes."""
        now = time.time() if now is None else now
        if not self.root.exists():
            return {"removed": 0, "bytes": 0}
        files = sorted(self.root.glob("*.wav"), key=lambda f: f.stat().st_mtime)
        removed = 0
        for f in list(files):
            if now - f.stat().st_mtime > max_age:
                f.unlink(missing_ok=True)
                files.remove(f)
                removed += 1
        total = sum(f.stat().st_size for f in files)
        while files and total > max_bytes:
            f = files.pop(0)
            total -= f.stat().st_size
            f.unlink(missing_ok=True)
            removed += 1
        return {"removed": removed, "bytes": total}


def slide_pieces(markdown: str) -> list[str]:
    """The speech pieces the page will ask for, for every slide. Same rule as the page's slideText + splitSentences + splitForSpeech."""
    from .voice import split_sentences
    slides, cur, fence = [], None, False
    for line in markdown.split("\n"):
        if line.startswith("<!--"):
            continue
        if re.match(r"^##+ ", line):
            if cur is not None:
                slides.append(cur)
            cur = [re.sub(r"^##+ ", "", line).strip()]
            continue
        if cur is None:
            continue
        t = line.strip()
        if t.startswith("```"):
            fence = not fence
            continue
        if fence or not t:
            continue
        cur.append(re.sub(r"^[-*] ", "", t.replace("**", "").replace("`", "")))
    if cur is not None:
        slides.append(cur)
    pieces = []
    for parts in slides:
        for sentence in split_sentences(". ".join(parts)):
            pieces.extend(p for p in split_for_speech(sentence) if re.search(r"[A-Za-z0-9]", p))  # "---" and symbols aren't speech
    return pieces


def prebuild_lesson(data_dir, markdown: str, rules=(), cache_root=None, out=None) -> dict:
    """Build the slide audio for one lesson into the cache. Only the local voices are cached; costs nothing.
    Already-cached sentences are skipped, so running it again costs nothing."""
    from .settings import Settings
    from . import pronounce as P
    s = Settings(data_dir).get()
    if s["lesson_voice"] not in ("kokoro", "piper"):
        return {"skipped": "lesson voice is not local"}
    cache = SpeechCache(cache_root)
    fallback = None if s["tts_fallback"] == "none" else s["tts_fallback"]
    pieces = speech_pieces(markdown)
    built = 0
    for piece in pieces:
        spoken = P.apply(piece, rules)
        label = provider(s["lesson_voice"]).label()
        if cache.get(cache.key(label, spoken)) is None:
            synthesize(spoken, primary=s["lesson_voice"], fallback=fallback, cache=cache)
            built += 1
    result = {"sentences": len(pieces), "built": built, "cache_bytes": cache.size(), **cache.prune()}
    (out or print)(f"slide audio: {result['sentences']} sentences, {built} new, cache {result['cache_bytes'] // 1000} KB")
    return result


def speech_pieces(markdown: str) -> list[str]:
    """What the page speaks for a lesson: each slide's teacher script where there is one (check-in questions included,
    expect lines never), else the slide text. Same pieces as the page sends, so the cache can serve them."""
    from .lesson import Lesson
    from .voice import split_sentences
    lesson = Lesson.parse(markdown)
    if not lesson.scripts:
        return slide_pieces(markdown)
    out = []
    for idx in range(len(lesson.slides)):
        for line in lesson.scripts.get(idx, []):
            for sentence in split_sentences(line["text"]):
                out.extend(p for p in split_for_speech(sentence) if re.search(r"[A-Za-z0-9]", p))
    return out
