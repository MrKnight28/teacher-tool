# Licences for downloaded and bundled files

Checked on 6 Oct 2026. "Verified" means I read the licence from the source. "Not verified" means I could not find it and it needs checking before any wider sharing. This is not legal advice.

## Important: the Piper voice (en_US-lessac-medium)

The model card for `en_US-lessac-medium` says it was trained on the Blizzard 2013 Lessac dataset. That dataset's licence (cstr.ed.ac.uk, Blizzard 2013, Lessac Technologies / Voice Factory) grants use **"for Research Purposes only"** and needs a manual approval. The Piper repository's MIT licence does not override this. Using this voice for personal study is probably fine, but its terms are restrictive and it should not be shared or used in anything commercial. Consider a Piper voice trained on a permissively licensed dataset before any wider use.

## Files on disk

| File | Source | Licence | Checked |
|---|---|---|---|
| `kokoro-v1.0.onnx` (325 MB, float32) | github.com/thewh1teagle/kokoro-onnx, release `model-files-v1.0`, converted from hexgrad/Kokoro-82M | Apache-2.0 (the Kokoro-82M model card) | Verified (model card). The conversion's own licence not checked |
| `voices-v1.0.bin` (28 MB, voice styles incl. af_heart, bf_emma, bf_isabella) | same release | Apache-2.0 (assumed to follow Kokoro-82M) | Not verified for the voice file itself |
| `en_US-lessac-medium.onnx` (63 MB) and `.onnx.json` | huggingface.co/rhasspy/piper-voices, `en/en_US/lessac/medium` | repository MIT; **the training dataset is research-only** (see above) | Verified (repo metadata and dataset licence) |
| faster-whisper `base.en` model (`Systran/faster-whisper-base.en`, about 145 MB) | huggingface.co/Systran/faster-whisper-base.en | MIT (model card) | Verified |
| faster-whisper `small.en` model (`Systran/faster-whisper-small.en`, about 480 MB), benchmark only | huggingface.co/Systran/faster-whisper-small.en | MIT (assumed to match base.en; the card was not read) | Not verified |
| Parakeet TDT 0.6B v3, ONNX int8 and float (`istupakov/parakeet-tdt-0.6b-v3-onnx` at revision `8f23f0c`, about 0.7 GB int8 and 2.5 GB float, benchmark only) | huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx, converted from nvidia/parakeet-tdt-0.6b-v3 | CC-BY-4.0 (the model card's licence field). **Attribution is required** if shared. NVIDIA's own page was not read | Verified (model card metadata) |

Hashes are checked by `python3 -m tutor fetch-voices` (SHA-256, in `apps/api/tutor/tts.py`):

- kokoro-v1.0.onnx `7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5`
- voices-v1.0.bin `bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d`
- en_US-lessac-medium.onnx `5efe09e69902187827af646e1a6e9d269dee769f9877d17b16b1b46eeaaf019f`
- en_US-lessac-medium.onnx.json `efe19c417bed055f2d69908248c6ba650fa135bc868b0e6abb3da181dab690a0`

## Code and packages

| Package | Licence | Checked |
|---|---|---|
| kokoro-onnx (pip) | MIT (LICENSE file in the repository) | Verified |
| piper-tts (pip, piper1-gpl) | GPL-3.0-or-later (PyPI metadata) | Verified |
| espeakng-loader (pip, a dependency of kokoro-onnx) | bundles espeak-ng, which is GPL-3.0 upstream | Not verified: the package metadata gives no licence |
| faster-whisper (pip) | MIT | Verified |
| onnx-asr 0.12.0 (pip, runs Parakeet for sttbench) | MIT (LICENSE file in the repository) | Verified |
| onnxruntime, numpy | MIT / BSD (upstream) | Not checked in this pass |
| Claude Code CLI (npm, @anthropic-ai/claude-code) | Anthropic terms | Not checked in this pass |

GPL-3.0 components (piper-tts, and espeak-ng through espeakng-loader) mean that distributing this image as a whole would carry GPL obligations. Running it privately for yourself does not.
