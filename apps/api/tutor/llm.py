"""Single gateway for all model calls (OpenRouter, OpenAI-compatible). Tracks spend and enforces the monthly cap."""
from __future__ import annotations
import datetime as dt
import logging
import os

from pathlib import Path
from .settings import Settings
from .store import Store
from .providers import openrouter
from .providers.claude_cli import ClaudeSession, SessionCrashed, _flatten, run_claude_cli, run_claude_cli_stream

log = logging.getLogger("tutor.llm")
FALLBACK_USD_PER_MTOK = 15.0  # conservative estimate if the provider doesn't report cost
# Output caps per task. Without one, providers reserve the model's maximum (e.g. 65k tokens),
# which fails on low-credit accounts and makes runaway answers expensive.
MAX_TOKENS = {"lesson": 9000, "chat": 800, "mark": 10, "transcribe": 3000, "probe": 150}
OPENROUTER_ONLY = {"transcribe", "probe"}   # never the Claude subscription: setup probes a specific OpenRouter model


class CapReached(Exception):
    pass


CLI_MODELS = {"lesson": "sonnet", "chat": "haiku", "mark": "haiku"}  # chat is Haiku for speed; lessons stay on Sonnet


def provider() -> str:
    """'claude-cli' uses your Claude Pro/Max subscription through Claude Code; 'openrouter' uses API credit."""
    return os.environ.get("LLM_PROVIDER", "openrouter").strip().lower()


class LLM:
    def __init__(self, store: Store, data_dir: Path, post=openrouter.chat, cli=None, cli_stream=None, session=None):
        self.store, self.settings, self.post, self.cli = store, Settings(data_dir), post, cli
        self.cli_stream = cli_stream
        self.session = session or ClaudeSession()  # no process starts until the first chat question

    def month_spend_gbp(self, today: dt.date | None = None) -> float:
        s = self.settings.get()
        month = (today or dt.date.today()).strftime("%Y-%m")
        return self.store.month_cost_usd(month) / s["gbp_usd_rate"]

    def remaining_gbp(self, today=None) -> float:
        return self.settings.get()["monthly_cap_gbp"] - self.month_spend_gbp(today)

    def complete(self, messages: list[dict], model: str, task: str) -> str:
        """Returns '' if no key/model is configured. Raises CapReached when the monthly cap is used up."""
        if provider() == "claude-cli" and task not in OPENROUTER_ONLY:
            cli_model = os.environ.get(f"CLAUDE_MODEL_{task.upper()}") or CLI_MODELS.get(task, "sonnet")
            out = (self.cli or run_claude_cli)(messages, cli_model)
            # Subscription usage isn't billed per token, so it doesn't count toward the £ cap.
            self.store.add_usage(dt.date.today(), f"{task} (subscription)", cli_model, 0.0)
            return out.get("result", "") or ""
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key or not model:
            return ""
        if self.remaining_gbp() <= 0:
            raise CapReached(f"monthly cap of £{self.settings.get()['monthly_cap_gbp']} reached")
        data = self.post({"model": model, "messages": messages, "usage": {"include": True},
                          "max_tokens": MAX_TOKENS.get(task, 1500)}, key)
        u = data.get("usage") or {}
        cost = u.get("cost")
        if not isinstance(cost, (int, float)):
            cost = (u.get("prompt_tokens", 0) + u.get("completion_tokens", 0)) / 1e6 * FALLBACK_USD_PER_MTOK
        self.store.add_usage(dt.date.today(), task, model, float(cost))
        return data["choices"][0]["message"]["content"] or ""

    def speech(self, day: dt.date, task: str, model: str, cost_usd: float, call):
        """Speech calls (OpenAI Whisper, Gemini TTS) go through here, the same gate and usage record as complete().
        cost_usd is the estimate before the call; 0 means free (local speech, Gemini free tier) and skips the cap.
        Raises CapReached before any call when the cap is used up."""
        if cost_usd > 0 and self.remaining_gbp() <= 0:
            raise CapReached(f"monthly cap of £{self.settings.get()['monthly_cap_gbp']} reached")
        out = call()
        self.store.add_usage(day, task, model, float(cost_usd))
        return out

    def stream(self, messages: list[dict], model: str, task: str, timing: dict | None = None):
        """Yields the reply as it is written. Same gateway and usage record as complete(); OpenRouter replies come in one piece."""
        if provider() == "claude-cli" and task != "transcribe":
            cli_model = os.environ.get(f"CLAUDE_MODEL_{task.upper()}") or CLI_MODELS.get(task, "sonnet")
            if self.cli_stream is None and task == "chat" and os.environ.get("CLAUDE_SESSION", "1") != "0":
                yield from self._session_stream(messages, cli_model, timing)
            else:
                for piece in (self.cli_stream or run_claude_cli_stream)(messages, cli_model, timing=timing):
                    yield piece
            self.store.add_usage(dt.date.today(), f"{task} (subscription)", cli_model, 0.0)
            return
        text = self.complete(messages, model, task)
        if text:
            yield text

    def _session_stream(self, messages: list[dict], model: str, timing: dict | None):
        """A chat turn through the warm session. A fresh process gets the whole conversation; a warm one gets only
        the new message, because Claude already has the rest. A crash before any text is retried once."""
        system, full = _flatten(messages)
        new = messages[-1]["content"]
        sent = False
        for attempt in (1, 2):
            try:
                for piece in self.session.turn(model, system, new, full, timing=timing):
                    sent = True
                    yield piece
                return
            except SessionCrashed as e:
                if sent or attempt == 2:
                    raise RuntimeError(f"Claude subscription call failed: {e}")
                log.warning("claude session crashed before any text; retrying once on a fresh process")
