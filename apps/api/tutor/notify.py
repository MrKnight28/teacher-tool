"""Message channels. WhatsApp (via OpenClaw) plugs in as another Notifier in Phase 5."""
from __future__ import annotations
import json
import os
import urllib.request


class Notifier:
    name = "base"

    def send(self, text: str) -> bool:
        raise NotImplementedError


class Console(Notifier):
    name = "console"

    def __init__(self):
        self.sent: list[str] = []

    def send(self, text):
        self.sent.append(text)
        print(f"[notify] {text}")
        return True


class Ntfy(Notifier):
    """ntfy.sh or self-hosted ntfy. Topic should be long and random (it is effectively a password)."""
    name = "ntfy"

    def __init__(self, url: str, token: str | None = None):
        self.url, self.token = url, token

    def send(self, text):
        h = {"Title": "Security+ Tutor"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        try:
            with urllib.request.urlopen(urllib.request.Request(self.url, text.encode(), h), timeout=15) as r:
                return 200 <= r.status < 300
        except OSError:
            return False


class Webhook(Notifier):
    """Generic JSON POST, e.g. to an OpenClaw gateway hook that forwards to WhatsApp."""
    name = "webhook"

    def __init__(self, url: str, token: str | None = None):
        self.url, self.token = url, token

    def send(self, text):
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        try:
            req = urllib.request.Request(self.url, json.dumps({"text": text}).encode(), h)
            with urllib.request.urlopen(req, timeout=15) as r:
                return 200 <= r.status < 300
        except OSError:
            return False


# What OpenClaw's model is told to do with every reminder. Setup tests candidate models with this exact instruction.
RELAY_INSTRUCTION = "Send the following reminder to the student exactly as written, with no changes and no extra text:\n\n"


class OpenClawHook(Notifier):
    """Sends via OpenClaw's inbound webhook (POST /hooks/agent, deliver to WhatsApp).
    Uses the dedicated hooks token, not the gateway operator token (least privilege)."""
    name = "openclaw"

    def __init__(self, url: str, token: str, to: str, agent_id: str = "main"):
        self.url, self.token, self.to, self.agent_id = url.rstrip("/"), token, to, agent_id

    def send(self, text):
        body = {"message": f"{RELAY_INSTRUCTION}{text}",
                "agentId": self.agent_id, "deliver": True, "channel": "whatsapp", "to": self.to}
        h = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        try:
            req = urllib.request.Request(f"{self.url}/hooks/agent", json.dumps(body).encode(), h)
            with urllib.request.urlopen(req, timeout=30) as r:
                return 200 <= r.status < 300 and json.load(r).get("ok", False)
        except (OSError, ValueError):
            return False


class Fallback(Notifier):
    """Try channels in order (e.g. WhatsApp first, ntfy if WhatsApp is down)."""
    name = "fallback"

    def __init__(self, channels: list[Notifier]):
        self.channels = channels
        self.name = " then ".join(c.name for c in channels)  # e.g. "openclaw then ntfy"

    def send(self, text):
        return any(c.send(text) for c in self.channels)


def from_env() -> Notifier:
    chans: list[Notifier] = []
    if os.environ.get("OPENCLAW_HOOK_URL") and os.environ.get("OPENCLAW_HOOK_TOKEN") and os.environ.get("WHATSAPP_TO"):
        chans.append(OpenClawHook(os.environ["OPENCLAW_HOOK_URL"], os.environ["OPENCLAW_HOOK_TOKEN"], os.environ["WHATSAPP_TO"]))
    if os.environ.get("NOTIFY_WEBHOOK_URL"):
        chans.append(Webhook(os.environ["NOTIFY_WEBHOOK_URL"], os.environ.get("NOTIFY_WEBHOOK_TOKEN")))
    if os.environ.get("NTFY_URL"):
        chans.append(Ntfy(os.environ["NTFY_URL"], os.environ.get("NTFY_TOKEN")))
    return Fallback(chans) if chans else Console()
