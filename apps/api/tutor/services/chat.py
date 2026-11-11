"""In-lesson chat: one reply, or a stream of pieces for the caption and for speech."""
from __future__ import annotations
import time
from .. import chat as C
from .. import timing as T
from .. import voice as V


class ChatMixin:
    def chat(self, day, message):
        message = message.strip()[:2000]
        if not message:
            return None
        hist = self.store.chat_history(day)
        model = self.settings.get()["chat_model"]
        try:
            r = C.reply(self.pack, self.soul, self.context, day, self.data, hist, message, model, self.llm)
        except (OSError, RuntimeError, ValueError) as e:
            r = f"(The model didn't respond: {str(e)[:200]}. Try again in a minute.)"
        self.store.add_chat(day, "user", message)
        self.store.add_chat(day, "assistant", r)
        return {"reply": r}

    def chat_stream(self, day, message, request_bytes=0, chain=None):
        """Yields {"type": "delta"} pieces for the caption, {"type": "sentence"} for each finished sentence (for speech),
        then {"type": "done"}. If the page cancels, nothing is saved. The timing log holds numbers only, never the text."""
        message = message.strip()[:2000]
        hist = self.store.chat_history(day)
        model = self.settings.get()["chat_model"]
        timing, parts, sentences = {}, [], 0
        split = V.SentenceSplitter()
        t0 = time.perf_counter()
        gen = C.reply_stream(self.pack, self.soul, self.context, day, self.data, hist, message, model, self.llm, timing=timing)
        try:
            for piece in gen:
                parts.append(piece)
                yield {"type": "delta", "text": piece}
                for s in split.feed(piece):
                    sentences += 1
                    yield {"type": "sentence", "text": s}
            for s in split.flush():
                sentences += 1
                yield {"type": "sentence", "text": s}
        except (OSError, RuntimeError, ValueError) as e:
            piece = f"(The model didn't respond: {str(e)[:200]}. Try again in a minute.)"
            parts.append(piece)
            yield {"type": "delta", "text": piece}
        finally:
            gen.close()
        reply = "".join(parts)
        self.store.add_chat(day, "user", message)
        self.store.add_chat(day, "assistant", reply)
        if "first_ms" in timing:
            T.chain_add(chain, chat_first_ms=timing["first_ms"])
        T.record("chat", request_bytes=request_bytes, reply_chars=len(reply), sentences=sentences,
                 total_ms=T.ms_since(t0), **{k: v for k, v in timing.items() if k in ("first_ms", "claude_ms", "warm")})
        yield {"type": "done", "reply": reply}
