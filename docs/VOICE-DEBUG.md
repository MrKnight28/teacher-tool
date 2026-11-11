# Voice debugging notes

Notes on how speech is wired, and timings measured on a desktop PC. The numbers are from one machine; re-measure on yours.

You are helping debug a self-hosted study tutor. It runs in Docker on Windows (Docker Desktop). The API container has a read-only root filesystem, `cap_drop: ALL`, and `/tmp` mounted `noexec`. Only `/data` (a bind mount of `./data`) is writable. The app is pure Python stdlib (`http.server`) plus `faster-whisper` for speech-to-text. Voice is meant to run locally and free. A Claude subscription is an optional paid path for lesson text, not for the microphone.

Repo: the Teacher Tool checkout. Relevant files:
- `apps/api/tutor/voice.py`: local Whisper (`_load_model`, `_local_transcribe`, `transcribe`, `preload`), Gemini text-to-speech (`speak`), `SentenceSplitter`, WAV wrapping.
- `apps/api/tutor/timing.py`: per-request step timing. Logs numbers and step names only, never text. Last 10 rows are kept for the admin page.
- `apps/api/tutor/voicebench.py`: `python3 -m tutor voicebench`, which times Whisper on a bundled 5-second clip (`tutor/assets/voicebench-5s.wav`) and Gemini on 1-sentence and 10-sentence texts when a key is set.
- `apps/api/tutor/llm.py`: `run_claude_cli` (one-shot JSON) and `run_claude_cli_stream` (stream-json, partial messages), plus `LLM.stream()`. Both keep the same isolation flags.
- `apps/api/tutor/server.py`: `/api/voice/transcribe` (raw audio bytes), `/api/voice/speak`, `/api/voice/status`, `/api/voice/timings`, `/api/chat/stream` (server-sent events: `delta`, `sentence`, `done`).
- `apps/api/tutor/ui.html`: the lesson page. One state machine (`createMachine`, `TUTOR_ALLOWED`) between `@@voice-core` markers. The speech controller (`begin`, `reset`, `makeSpeaker`, `speakBrowser`, `speakGemini`, `ask`, `startAsk`, `sendRecording`) is the only code that changes state. `render` is the only code that writes the state chip, caption and mic/Read/Ask buttons.
- `apps/api/tutor/admin.html`: Voice card (Whisper model with the benchmark beside it, lesson voice, Gemini billing) and the Voice timings panel under Setup & health.
- `apps/api/tests/test_voice.py`: the tests, including the state machine and the sentence rule, run under Node against the shipped `ui.html`.
- `apps/api/Dockerfile`: installs `.[voice]`, sets `HF_HOME=/data/hf`, `WHISPER_MODEL_DIR=/data/models`, `TRANSCRIBE=local`.

**What the user sees (one PC, Chrome or Edge on http://127.0.0.1:8080):**
1. **Hold to ask:** a delay between letting go of the mic button and the answer.
2. **Read (🔊) on a slide:** a long wait before speech starts.
3. **Spoken answers:** a delay before the answer is spoken, and then the full answer is read after it has been written.
4. **Once (before this change):** the lesson began reading slide content again, and then an answer talked over it.

**Measurements (6 Oct 2026, same PC, same model, same question). Full numbers in the table below.**

| Step | Before | After |
|---|---|---|
| Whisper `base.en`, 5.0 s clip, warm | 447, 439 ms. First call after start: 1,779 ms | 414 ms median. The first call is warmed at load, so it no longer pays the 1.8 s cold start |
| Whisper CPU threads | library default | 8 threads: 358 ms. 16 threads (the core count): 956 ms. Capped at 8 |
| `claude -p` Haiku, one question, total | 3,877 to 4,533 ms (one-shot JSON, live container) | 3,608 ms median one-shot; 3,676 ms median streamed total (same process, alternating runs) |
| `claude -p` Haiku, first full sentence on screen and speakable | not available (the whole answer arrives at the end) | 1,962 ms median |
| Gemini TTS, 1 sentence / 10 sentences | not measured: HTTP 429 (free-tier quota) on both calls | still HTTP 429 when re-run on the same day; re-run `voicebench` when the quota resets |
| Browser: mic release to upload complete | not recorded | 108 ms (headless Edge, fake microphone, 2.5 s clip) |
| Browser: upload complete to transcript | not recorded | 210 to 295 ms |
| Browser: Read to first speech | Gemini call first (user reports 20+ seconds) | browser voice starts at once. Not timed in a real browser (headless Edge has no audio output) |

Notes on the numbers:
- Gemini is the open question. Its free-tier quota was used up on 6 Oct, so no Gemini timing exists yet. Its 20-second Read delay is not explained by these numbers.
- The 5-second clip is 5.24 s of speech trimmed to 5.00 s. The trimmed clip still transcribes correctly.
- `claude -p` has a fixed cost of about 2 s before the first token. Streaming does not reduce that. It only starts speech at the first full sentence.

**Facts established:**
- Gemini text-to-speech calls succeed when quota is available. On 5 Oct the app logged about a dozen successful `/api/voice/speak` calls.
- Local transcription costs nothing and is labelled `local:base.en` in usage. Only `TRANSCRIBE=openai` is labelled `openai:whisper-1` and estimated.
- Read and welcome use the browser voice by default (setting "Lesson voice"). Gemini is one request per sentence, with the next sentence fetched while the current one plays.
- Every speech action gets a token. Starting anything cancels the old one's requests (AbortController), its playback and its speech. Stale tokens can't change the state.
- Gemini on the free tier is recorded at cost 0 and doesn't count toward the £ cap ("Gemini billing" setting).

**What to do next:**
1. Re-run `docker compose exec api python3 -m tutor voicebench --all` when the Gemini quota resets. Add the Gemini numbers to the table above.
2. Measure Read and spoken answers in the real browser on the PC, using the Voice timings panel in admin.
3. If Read is still slow with the browser voice, the cause is the browser itself (no network involved).
4. Keep every timing line free of text. Don't add a log field that could hold a question, answer or lesson.

Constraints: no paid services, no new keys, keep the container read-only with no shell features beyond what it has, and keep the Windows path behaviour. Don't suggest a card-based service as the main fix.

---

---

## Local voices: Kokoro (default) and Piper (fallback), 6 Oct 2026

Supersedes the Gemini-first notes above. The lesson voice is now local.

**Measured on a desktop CPU (8 cores / 16 threads, Docker Desktop, `python3 -m tutor ttsbench`).** Representative sentence: "The purpose of authentication is to verify the identity of a user before allowing access to a system." (6.44 s of audio when spoken whole.) First audio = synthesis of the first clause plus WAV encoding, warm, median of 5.

| Voice | Threads | Cold load | Whole sentence | First audio |
|---|---|---|---|---|
| Kokoro v1.0 float32 | 4 | 2,200 ms | 1,595 ms | 1,073 ms |
| Kokoro v1.0 float32 | 8 | 1,619 ms | 1,393 ms | 923 ms |
| Kokoro v1.0 float32 | **16 (chosen)** | 1,541 ms | 1,358 ms | **851 ms** |
| Piper en_US-lessac-medium | ONNX CPU | 943 ms | 159 ms (5.49 s audio) | 122 ms |

Earlier, outside the app: Kokoro **int8** took 6.3 s for the same sentence (real-time factor about 1.0), so it was rejected. The float32 file is about 4.5× faster here. Clause splitting took the first clause from 1.38 s to about 0.85 s.

**Target (about 1 s to first audio):** met on the server side (851 ms synthesis + WAV), with the browser round trip and playback start still to add. Not timed end to end in a real browser. Headless browser tests use mocked audio, so they don't measure it.

**Choices:**
- Kokoro voice `af_heart` (US English) is the default. I did not compare voices by ear here, so judge it by listening.
- Sentences longer than about 60 characters are split at a comma or at "before/after/while/because/which/when/so that", once the first part is at least 40 characters. This trades a little prosody for a sooner first sound. Short sentences stay whole.
- Piper is the fallback, not the default: its audio is faster but less natural. Kokoro stays selectable.
- Gemini stays available as an option, off by default (its free tier allows 10 requests, which one slide can use up).

**Files (under the writable data volume):**
- `/data/models/kokoro/kokoro-v1.0.onnx` (325 MB, float32) and `/data/models/kokoro/voices-v1.0.bin` (28 MB). Source: github.com/thewh1teagle/kokoro-onnx, release model-files-v1.0.
- `/data/models/piper/en_US-lessac-medium.onnx` (63 MB) and `.onnx.json`. Source: huggingface.co/rhasspy/piper-voices.
- Fetch once, needs internet: `docker compose exec api python3 -m tutor fetch-voices`. Afterwards everything runs offline.

**Licence:** `piper-tts` (piper1-gpl) is GPL-3.0-or-later. It is a dependency of the Docker image. The licences of kokoro-onnx and the Kokoro model were not verified here (the PyPI metadata gives none). Check them in their repositories before any wider sharing.

**Configuration (environment, all optional):** `KOKORO_MODEL_PATH`, `KOKORO_VOICES_PATH`, `KOKORO_VOICE` (default `af_heart`), `KOKORO_THREADS` (default 16), `PIPER_MODEL_PATH`, `TUTOR_MODELS_DIR` (default `/data/models`). Admin settings: "Lesson voice" (kokoro, piper, browser, gemini) and "Fallback if the lesson voice fails" (piper or none).

**Usage rows:** `local:kokoro-af_heart`, `local:piper-en_US-lessac-medium`, `local:whisper-base.en`, all cost 0. `openai:whisper-1` only for the paid OpenAI option.

**Playback:** one server synthesis at a time (one lock), one browser queue (one request per sentence, the next fetched while the current plays), one audio element. Stop clears the queue; a new question or Read cancels the old one.

**Browser fallback:** the built-in voice is used only if the local voices fail, and it prefers an installed "Natural" English voice (Edge on Windows) over the default.

**Tests:** Python covers providers, paths, the fallback (speaks once), costs and the clause rule (checked against the browser's copy). `apps/api/tests/browser/voice.test.mjs` runs three checks in installed Edge with mocked routes: one queue, Stop, and a new answer cancelling old speech. Run from `apps/api/tests/browser`: `npm install`, then `node voice.test.mjs`.

---

## Round of 7 Oct 2026: measured on this PC

Measured numbers are marked "measured". Anything else is not measured.

**1. End to end (chain id per spoken question).** Implemented; tests pass (ordered steps under one id, bad ids ignored, logs hold the id and numbers, no text). **Not measured** on a real question yet. Admin shows the last 10 complete chains and the median per step once Kyle asks a few questions.

**2. Claude first reply: before and after (measured, 5 runs before, 4 turns after).**

| | Before (one process per question) | After (warm session, turns 2-5) |
|---|---|---|
| first text | 2,114 ms median | **1,633 ms** |
| first full sentence | 2,362 ms | 1,945 ms |
| whole answer | 3,760 ms | **2,121 ms** |

The 1.5 s target for first text is **not met** (1.6 s). The warm turns range from 1.25 s to 2.1 s. Crash handling, the restart after 12 turns and the one-question-at-a-time lock are tested with a fake process, not with real crashes.

**3. Slide audio cache (measured).** The 5 Oct lesson gives 128 sentences. 111 were built in 78 s, and the cache is **18.5 MB** for that lesson. A rerun builds nothing. Files older than 7 days are deleted, and the total is kept under `TTS_CACHE_MAX_MB` (default 500).

**4. Pronunciation.** Rules in `packs/security-plus-sy0-701/pronounce.yaml`. Applied before Kokoro, Piper and Gemini, and in the browser voice. Python and browser match on the same text (test). **Not measured by ear.** Admin has "Show how it will be spoken".

**5. Whisper prompt and sttbench.** The prompt is built from the pronunciation terms and today's objective titles. It is **off by default**. `python3 -m tutor sttbench` reads `data/stt-samples` (a .wav and a .txt with the exact words, same name). **No recordings exist yet, so no word error rate has been measured.** Record 5 to 10 short clips of your own voice, then run sttbench.

**6. Blind voice test.** Built into admin: three sentences in Kokoro af_heart, bf_emma, bf_isabella and Piper lessac, in random order, scored 1 to 5. The names stay hidden until every clip is scored. **Clips not built or scored yet**: press "Build test clips" on the PC.

**7. ttsbench extras (measured, 16 threads).**
- CPU during the warm runs: about 97% of the machine.
- ONNX inter_op_num_threads 1 vs 2: first audio 808 ms vs 815 ms. No gain, so it stays at 1.
- Contention: Kokoro first audio 831 ms alone, **1,645 ms** while Whisper transcribes. Whisper 395 ms alone, **2,052 ms** while Kokoro runs. The two shouldn't run at once.

**8. Licences and checksums.** `LICENSES.md` lists each downloaded file. `fetch-voices` checks the SHA-256 of each file and keeps none that don't match. **The Piper Lessac voice was trained on a dataset licensed for research purposes only**: it's flagged in LICENSES.md, and it's a decision for Kyle before any sharing.

**Bugs found and fixed on the way.**
- A "---" line in a lesson was sent as speech and made both voices fail. Now skipped on the server, in the cache, and in the page.
- A local-voice request with the setting on Gemini failed with "unknown local voice". Now uses Kokoro.
- espeak-ng needs its temporary files outside the `noexec` /tmp (fixed with TMPDIR).

**Tests:** 172 Python tests and 3 browser checks, all passing.

---

## Parakeet TDT 0.6B v3 against Whisper: step 1 (measurement only), 6 Oct 2026

Status: the harness is built and tested. **The default is still Whisper base.en.** Parakeet changes nothing until your own recordings are scored.

**What was added**
- Runtime: `onnx-asr` 0.12.0 (MIT) on onnxruntime. No PyTorch, NeMo or FFmpeg. Pinned in `apps/api/pyproject.toml`.
- Model: `istupakov/parakeet-tdt-0.6b-v3-onnx` at revision `8f23f0c` (CC-BY-4.0, attribution required). Int8 and float. Pinned by file, with SHA-256 and size (`apps/api/tutor/parakeet.py`).
- Fetch: `python3 -m tutor fetch-voices --stt parakeet`. Downloads both precisions.
- Harness: `python3 -m tutor sttbench [--samples DIR] [--threads 4,8,16]`. Each engine and thread count runs in its own process, so load time and peak RAM aren't shared. Results go to `data/sttbench.json` and the admin Voice card.
- Engines compared: whisper base.en (plain and with the Whisper prompt), whisper small.en, parakeet int8, parakeet float.

**Files on disk (this PC, downloaded and checksum-checked on 6 Oct)**
- `data/models/parakeet-tdt-0.6b-v3/`: 3.0 GB (int8 encoder 652 MB, int8 decoder 18 MB, float encoder 2,435 MB plus 42 MB graph, float decoder 73 MB, shared 0.2 MB). Under `data/` and git-ignored.
- whisper small.en is not downloaded yet. `sttbench` fetches it on first use (about 480 MB, needs internet).

**Measured on a desktop CPU (Docker Desktop, the bundled 5 s clip, warm median of 3 runs).** This clip is a question, "What does a firewall do, and where does it sit on a network?", not your voice. All four engines transcribed it exactly. So this table measures speed only, and it can't decide the default.

| Engine | Threads | Cold load (ms) | Warm median (ms) | Worst (ms) | Real-time factor | Peak RAM (MB) |
|---|---|---|---|---|---|---|
| whisper base.en | 4 | 1,635 | 516 | 563 | 9.6 | 341 |
| whisper base.en | **8** | 1,484 | **427** | 463 | 11.7 | 355 |
| whisper base.en | 16 | 1,546 | 1,041 | 1,046 | 4.8 | 358 |
| whisper small.en | 4 | 4,009 | 1,268 | 1,269 | 3.9 | 675 |
| whisper small.en | 8 | 3,681 | 1,141 | 1,162 | 4.4 | 621 |
| whisper small.en | 16 | 4,208 | 2,329 | 2,346 | 2.2 | 620 |
| parakeet int8 | 4 | 4,537 | 308 | 325 | 16.1 | 1,031 |
| parakeet int8 | 8 | 4,964 | 339 | 343 | 15.0 | 1,317 |
| parakeet int8 | 16 | 4,885 | 366 | 388 | 13.5 | 1,065 |
| parakeet float | 4 | 17,932 | 340 | 357 | 15.0 | 2,611 |
| parakeet float | 8 | 17,221 | 295 | 336 | 16.3 | 2,613 |
| parakeet float | 16 | 17,547 | 302 | 316 | 16.4 | 2,620 |

Reading the numbers:
- Whisper's best is 8 threads (as the app already uses). 16 threads is slower for both Whisper models.
- Parakeet is flat across thread counts. On this clip, int8 at 4 threads is about the same speed as float.
- Parakeet's cold load is 4.5 s for int8 and 17 s for float. The app loads once and keeps the model resident, so cold load matters only at start-up.
- Peak RAM: Parakeet int8 uses about 1.0 to 1.3 GB, float about 2.6 GB. Whisper uses 0.3 to 0.7 GB. None of these engines use a GPU.

**Not measured yet (needs your own recordings):** word error rate, Security+ term recall, and acronym recall. The bundled clip has no terms in it.

**Hotwords and context biasing:** onnx-asr 0.12.0 has no hotword or biasing parameter (checked in the package source). The Security+ term test can't run on Parakeet. The Whisper prompt is the only biasing available, and it stays Whisper-only.

**Japanese course:** Parakeet TDT v3 supports 25 European languages and not Japanese, so the Japanese course must use Whisper. This rule is for step 2 and isn't in the code yet.

**Recording the test clips (about 10 minutes)**
Make 10 WAV files, 16-bit mono, 16 kHz (Audacity: Export as WAV, Other uncompressed, 16-bit PCM; set the project rate to 16000 first). Read each sentence in your normal voice, in a quiet room, at your normal distance from the mic. For each `NN.wav`, save `NN.txt` with the same sentence, spelled exactly as written. Save all of them in `C:\Users\you\teacher-tool\data\stt-samples\`.

1. `01` What does a SIEM do with logs from your firewalls and servers?
2. `02` Which tool automates responses to alerts? That is a SOAR platform.
3. `03` XDR collects telemetry from endpoints, email and the network into one view.
4. `04` Does IPsec encrypt the payload, or only authenticate the packet headers?
5. `05` Port-based access control with 802.1X stops unknown devices at the switch.
6. `06` Which part of the CIA triad does hashing protect?
7. `07` Is MFA still needed if the user has a strong password?
8. `08` RADIUS and TACACS+ both handle authentication, but only one encrypts the whole packet.
9. `09` A PKI issues certificates, and a certificate authority signs them.
10. `10` The SY0-701 exam covers five domains. Which one covers incident response?

**Running it (on the PC, with nothing else heavy running)**
```powershell
cd C:\Users\you\teacher-tool
docker compose up -d --build
docker compose exec api python3 -m tutor sttbench
```
The first run loads whisper small.en (needs internet once). Expect 10 to 20 minutes, because each engine runs three thread counts and every clip is repeated three times. Results show in the admin Voice card, and `data\sttbench.json` holds the full numbers.
