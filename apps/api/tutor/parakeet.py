"""NVIDIA Parakeet TDT 0.6B v3 as a second speech-to-text engine, for measuring against Whisper (docs/VOICE-DEBUG.md).

Runs through onnx-asr (MIT) on onnxruntime: no PyTorch, no NeMo, no FFmpeg. The model files live in the writable data
folder, pinned to one Hugging Face revision, and each file is checked by SHA-256 before use. Upstream model:
nvidia/parakeet-tdt-0.6b-v3 (CC-BY-4.0); the ONNX conversion is istupakov/parakeet-tdt-0.6b-v3-onnx (CC-BY-4.0).

Parakeet is not the default. `sttbench` measures it; the engine is switched only after the numbers are checked.
"""
from __future__ import annotations
import os
import urllib.request
from pathlib import Path

from .tts import MODELS_DIR, sha256_file

REVISION = "8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce"
BASE = f"https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx/resolve/{REVISION}/"
DIR = MODELS_DIR / "parakeet-tdt-0.6b-v3"
MODEL_NAME = "nemo-parakeet-tdt-0.6b-v3"   # onnx-asr's name for Parakeet TDT v3
PRECISIONS = ("int8", "float")

# filename: (SHA-256, bytes). Sizes and hashes come from the Hugging Face file list for REVISION.
COMMON = {
    "config.json": ("666903c76b9798caf2c210afd4f6cd60b08a8dbf9800ec8d7a3bc0d2148ac466", 97),
    "vocab.txt": ("d58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d", 93939),
    "nemo128.onnx": ("a9fde1486ebfcc08f328d75ad4610c67835fea58c73ba57e3209a6f6cf019e9f", 139764),
}
FILES_BY_PRECISION = {
    "int8": {
        "encoder-model.int8.onnx": ("6139d2fa7e1b086097b277c7149725edbab89cc7c7ae64b23c741be4055aff09", 652183999),
        "decoder_joint-model.int8.onnx": ("eea7483ee3d1a30375daedc8ed83e3960c91b098812127a0d99d1c8977667a70", 18202004),
    },
    "float": {
        "encoder-model.onnx": ("98a74b21b4cc0017c1e7030319a4a96f4a9506e50f0708f3a516d02a77c96bb1", 41770866),
        "encoder-model.onnx.data": ("9a22d372c51455c34f13405da2520baefb7125bd16981397561423ed32d24f36", 2435420160),
        "decoder_joint-model.onnx": ("e978ddf6688527182c10fde2eb4b83068421648985ef23f7a86be732be8706c1", 72520893),
    },
}


def files(precision: str) -> dict:
    """Every file one precision needs: the shared ones plus that precision's encoder and decoder."""
    if precision not in PRECISIONS:
        raise ValueError(f"precision must be one of {', '.join(PRECISIONS)}")
    return {**COMMON, **FILES_BY_PRECISION[precision]}


def download_mb(precision: str) -> int:
    return sum(size for _, size in files(precision).values()) // 1_000_000


def ready(precision: str) -> bool:
    """Cheap check that the files exist (the checksum is checked once, by fetch)."""
    return all((DIR / name).exists() for name in files(precision))


def fetch(precisions=PRECISIONS, out=print, download=urllib.request.urlretrieve) -> None:
    """Download the files once and check each SHA-256. A file that doesn't match is never kept."""
    DIR.mkdir(parents=True, exist_ok=True)
    wanted = {}
    for p in precisions:
        wanted.update(files(p))
    for name, (digest, size) in wanted.items():
        dst = DIR / name
        if dst.exists() and sha256_file(dst) == digest:
            out(f"ok {name} (checksum matches)")
            continue
        out(f"fetching {name} ({size // 1_000_000} MB) ...")
        tmp = dst.with_suffix(dst.suffix + ".part")
        download(BASE + name, tmp)
        if sha256_file(tmp) != digest:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"checksum mismatch for {name}: not saved. Check the download.")
        os.replace(tmp, dst)
        out(f"saved {dst} ({size // 1_000_000} MB, checksum matches)")


def load(precision: str = "int8", threads: int = 8):
    """Load one precision once, on the CPU, with ONNX intra-op threads set to `threads`."""
    if not ready(precision):
        raise RuntimeError("Parakeet files are missing; run: docker compose exec api python3 -m tutor fetch-voices --stt parakeet")
    try:
        import onnx_asr
        import onnxruntime as rt
    except ImportError:
        raise RuntimeError("Parakeet is not installed in this build (onnx-asr is missing)")
    so = rt.SessionOptions()
    so.intra_op_num_threads = threads
    so.inter_op_num_threads = 1
    return onnx_asr.load_model(MODEL_NAME, path=DIR, quantization="int8" if precision == "int8" else None,
                               sess_options=so, providers=["CPUExecutionProvider"])


def recognize(model, samples) -> str:
    """Text from 16 kHz mono float32 samples (the same decode as Whisper, so the engines get identical input)."""
    return (model.recognize(samples, sample_rate=16000) or "").strip()
