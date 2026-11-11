"""Speech: transcribe a question, speak a sentence or a reply, and the browser's own timing numbers."""
from __future__ import annotations
import os
import time
from .. import pronounce as P
from ..providers import gemini
from .. import say as S
from .. import stt as STT
from .. import timing as T
from .. import tts as TT
from .. import voice as V


class VoiceMixin:
    def stt_prompt(self, day):
        """Whisper's initial prompt for today's lesson, when the setting is on (see stt.py)."""
        if self.settings.get().get("stt_prompt") != "on":
            return None
        f = self.data / "lessons" / f"{day}.md"
        return STT.build_prompt(self.pack, f.read_text() if f.exists() else "", self.pronounce)

    def bench_prompt(self):
        """The Whisper prompt sttbench scores against: the latest lesson's terms and objectives."""
        lessons = sorted((self.data / "lessons").glob("*.md"))
        return STT.build_prompt(self.pack, lessons[-1].read_text() if lessons else "", self.pronounce)

    def voice_status(self):
        s = self.settings.get()
        return dict(V.status(s), pronounce=[list(r) for r in self.pronounce], auto_advance=s["auto_advance"], name=S.student_name(self.context))

    def voice_transcribe(self, day, audio: bytes, mime: str, duration_ms=None, chain=None):
        s = self.settings.get()
        timing = {"request_bytes": len(audio)}
        t0 = time.perf_counter()
        # Local Whisper costs nothing, so only the paid OpenAI option is capped (see LLM.speech).
        text = self.llm.speech(day, "voice question", V.transcribe_label(s["whisper_model"]), V.transcribe_cost(),
                               lambda: V.transcribe(audio, mime, duration_ms=duration_ms, model=s["whisper_model"],
                                                    timing=timing, prompt=self.stt_prompt(day)))
        T.record("ask", text_chars=len(text), total_ms=T.ms_since(t0), **timing)
        T.chain_add(chain, transcribe_ms=T.ms_since(t0))
        return {"text": text}

    def voice_tts(self, day, text: str, kind: str = "read", chain=None):
        """One sentence through the local voices (Kokoro, then Piper if set). Free: recorded at cost 0."""
        s = self.settings.get()
        fallback = None if s["tts_fallback"] == "none" else s["tts_fallback"]
        t0 = time.perf_counter()
        # Gemini has its own route; a local request with that setting uses Kokoro rather than failing.
        primary = s["lesson_voice"] if s["lesson_voice"] in ("kokoro", "piper") else "kokoro"
        wav, label, info = TT.synthesize(P.apply(text, self.pronounce), primary=primary, fallback=fallback, cache=self.speech_cache)
        T.chain_add(chain, tts_ms=info["tts_ms"])
        self.store.add_usage(day, "voice reply", label, 0.0)
        T.record(kind if kind in ("read", "answer") else "read", text_chars=min(len(text), TT.MAX_CHARS),
                 total_ms=T.ms_since(t0), tts_ms=info["tts_ms"], audio_s=info["audio_s"], model=label)
        return wav

    def voice_speak(self, day, text: str, kind: str = "read", chain=None):
        billing = self.settings.get()["gemini_billing"]
        timing = {}
        t0 = time.perf_counter()
        model = os.environ.get("GEMINI_TTS_MODEL", gemini.DEFAULT_TTS_MODEL)
        # The free tier costs nothing, so only the paid tier is capped (see LLM.speech).
        wav = self.llm.speech(day, "voice reply", f"gemini:{model}", V.speak_cost(text, billing),
                              lambda: V.speak(P.apply(text, self.pronounce), timing=timing))
        T.record(kind if kind in ("read", "answer") else "read", text_chars=min(len(text), V.MAX_SPEAK_CHARS),
                 total_ms=T.ms_since(t0), **timing)
        return wav

    def browser_timing(self, data: dict):
        """Step times measured in the page. Numbers only; see timing.py. The chain steps join the question's chain."""
        T.chain_add(str(data.get("chain", "")), **{k: v for k, v in data.items() if k in T.CHAIN_STEPS})
        return T.record(str(data.get("kind", "")), source="browser",
                        **{k: v for k, v in data.items() if k in T.BROWSER_FIELDS})
