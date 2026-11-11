"""Claude Code (`claude -p`) through the Pro/Max subscription. Only this module starts the process.

The subprocess runs isolated: no tools, no settings, no MCP servers, no saved session, and an empty HOME.
"""
from __future__ import annotations
import json
import logging
import os
import subprocess
import threading
import time

log = logging.getLogger("tutor.claude_cli")


def _flatten(messages: list[dict]) -> tuple[str, str]:
    """Turn chat messages into (system prompt, single prompt) for `claude -p`."""
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    turns = [m for m in messages if m["role"] != "system"]
    for m in turns:
        if not isinstance(m["content"], str):
            raise ValueError("images aren't supported through the Claude subscription; book photos use OpenRouter")
    if len(turns) == 1:
        return system, turns[0]["content"]
    hist = "\n".join(f"{'Student' if m['role'] == 'user' else 'Tutor'}: {m['content']}" for m in turns[:-1])
    return system, f"Conversation so far:\n{hist}\n\nStudent's new message:\n{turns[-1]['content']}"


def run_claude_cli(messages: list[dict], model: str, timeout: int = 300, runner=None) -> dict:
    """One isolated, tool-less `claude -p` call. Auth: CLAUDE_CODE_OAUTH_TOKEN from `claude setup-token`."""
    import subprocess
    import tempfile
    system, prompt = _flatten(messages)
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
    if not token:
        raise RuntimeError("CLAUDE_CODE_OAUTH_TOKEN is not set (run setup and paste the token from `claude setup-token`)")
    with tempfile.TemporaryDirectory(prefix="tutor-claude-") as home:
        cmd = ["claude", "-p", "--output-format", "json", "--model", model,
               "--system-prompt", system or "You are a helpful tutor.",
               "--tools", "", "--permission-mode", "dontAsk", "--setting-sources", "",
               "--strict-mcp-config", "--no-session-persistence"]
        env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"), "HOME": home,
               "CLAUDE_CODE_OAUTH_TOKEN": token, "DISABLE_AUTOUPDATER": "1", "DISABLE_TELEMETRY": "1"}
        run = runner or subprocess.run
        try:
            p = run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout, cwd=home, env=env)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Claude subscription call timed out after {timeout}s")
    try:
        out = json.loads(p.stdout or "{}")
    except json.JSONDecodeError:
        out = {}
    if p.returncode != 0 or out.get("is_error"):
        msg = out.get("result") or (p.stderr or p.stdout or "").strip()[:300]
        raise RuntimeError(f"Claude subscription call failed: {msg}")
    return out


def _json_line(line: str) -> dict:
    try:
        ev = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return {}
    return ev if isinstance(ev, dict) else {}


def _text_delta(ev: dict) -> str:
    """The text piece in a stream-json partial-message event, or '' for any other event."""
    if ev.get("type") != "stream_event":
        return ""
    e = ev.get("event") or {}
    d = e.get("delta") or {}
    if e.get("type") == "content_block_delta" and d.get("type") == "text_delta":
        return d.get("text") or ""
    return ""


def run_claude_cli_stream(messages: list[dict], model: str, timeout: int = 300, popen=None, timing: dict | None = None):
    """Like run_claude_cli, but yields the reply's text as Claude writes it (stream-json with partial messages).

    `timing` (optional dict) gets first_ms (start to first text) and claude_ms (start to finish). The isolation is
    the same as run_claude_cli: no tools, no settings, no MCP servers, no saved session.
    """
    import subprocess
    import tempfile
    system, prompt = _flatten(messages)
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
    if not token:
        raise RuntimeError("CLAUDE_CODE_OAUTH_TOKEN is not set (run setup and paste the token from `claude setup-token`)")
    with tempfile.TemporaryDirectory(prefix="tutor-claude-") as home:
        cmd = ["claude", "-p", "--output-format", "stream-json", "--verbose", "--include-partial-messages",
               "--model", model, "--system-prompt", system or "You are a helpful tutor.",
               "--tools", "", "--permission-mode", "dontAsk", "--setting-sources", "",
               "--strict-mcp-config", "--no-session-persistence"]
        env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"), "HOME": home,
               "CLAUDE_CODE_OAUTH_TOKEN": token, "DISABLE_AUTOUPDATER": "1", "DISABLE_TELEMETRY": "1"}
        start = time.perf_counter()
        spawn = popen or subprocess.Popen
        p = spawn(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                  text=True, cwd=home, env=env)
        timed_out = threading.Event()

        def expire():
            timed_out.set()
            p.kill()

        timer = threading.Timer(timeout, expire)
        timer.start()
        final, streamed = {}, False
        try:
            p.stdin.write(prompt)
            p.stdin.close()
            for line in p.stdout:
                ev = _json_line(line)
                piece = _text_delta(ev)
                if piece:
                    if timing is not None and "first_ms" not in timing:
                        timing["first_ms"] = (time.perf_counter() - start) * 1000
                    streamed = True
                    yield piece
                elif ev.get("type") == "result":
                    final = ev
            p.wait()
        finally:
            timer.cancel()
            if p.poll() is None:  # the caller stopped reading (the student moved on), so don't leave Claude running
                p.kill()
        if timed_out.is_set():
            raise RuntimeError(f"Claude subscription call timed out after {timeout}s")
        if timing is not None:
            timing["claude_ms"] = (time.perf_counter() - start) * 1000
        if p.returncode != 0 or final.get("is_error"):
            msg = final.get("result") or (p.stderr.read() if p.stderr else "")
            raise RuntimeError(f"Claude subscription call failed: {str(msg).strip()[:300]}")
        if not streamed and final.get("result"):  # no partial messages came through: send the whole reply at once
            yield final["result"]


SESSION_MAX_TURNS = 12   # restart a warm session after this many questions, so its memory can't grow without limit


class SessionCrashed(RuntimeError):
    pass


class ClaudeSession:
    """One long-running `claude -p` (stream-json in and out) that answers one question at a time.

    It is reused while the model and system prompt stay the same. It restarts after SESSION_MAX_TURNS, on a crash,
    or when either changes. A failed turn is retried once on a fresh process, which gets the full history. The
    isolation flags are the same as run_claude_cli. Only LLM.stream() uses it.
    """

    def __init__(self, popen=None, timeout: int = 300):
        import subprocess
        self.popen = popen or subprocess.Popen
        self.timeout = timeout
        self.lock = threading.Lock()
        self.proc = None
        self.key = None
        self.turns = 0
        self.home = None

    def _start(self, model: str, system: str):
        import subprocess
        import tempfile
        token = _token()
        self.close()
        self.home = tempfile.mkdtemp(prefix="tutor-claude-session-")
        cmd = ["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json",
               "--include-partial-messages", "--verbose", "--model", model,
               "--system-prompt", system or "You are a helpful tutor.",
               "--tools", "", "--permission-mode", "dontAsk", "--setting-sources", "",
               "--strict-mcp-config", "--no-session-persistence"]
        self.proc = self.popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               text=True, bufsize=1, cwd=self.home, env=_isolated_env(self.home, token))
        self.key = (model, system)
        self.turns = 0

    def needs_start(self, model: str, system: str) -> bool:
        return (self.proc is None or self.key != (model, system) or self.turns >= SESSION_MAX_TURNS
                or self.proc.poll() is not None)

    def close(self):
        import shutil
        p, self.proc, self.key = self.proc, None, None
        if p is not None:
            try:
                p.kill()
            except OSError:
                pass
        if self.home:
            shutil.rmtree(self.home, ignore_errors=True)
            self.home = None

    def turn(self, model: str, system: str, new_prompt: str, full_prompt: str, timing: dict | None = None):
        """Yields the reply's text pieces for one question. One question at a time: this holds the lock."""
        with self.lock:
            try:
                fresh = self.needs_start(model, system)
                if fresh:
                    self._start(model, system)
                p = self.proc
                content = full_prompt if fresh else new_prompt
                start = time.perf_counter()
                timer = threading.Timer(self.timeout, p.kill)
                timer.start()
                try:
                    p.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": content}}) + "\n")
                    p.stdin.flush()
                    streamed, final = False, {}
                    while True:
                        line = p.stdout.readline()
                        if not line:
                            raise SessionCrashed("the Claude session ended")
                        ev = _json_line(line)
                        piece = _text_delta(ev)
                        if piece:
                            if timing is not None and "first_ms" not in timing:
                                timing["first_ms"] = (time.perf_counter() - start) * 1000
                            streamed = True
                            yield piece
                        elif ev.get("type") == "result":
                            final = ev
                            break
                finally:
                    timer.cancel()
                self.turns += 1
                if timing is not None:
                    timing["claude_ms"] = (time.perf_counter() - start) * 1000
                    timing["warm"] = int(not fresh)
                if final.get("is_error"):
                    raise RuntimeError(f"Claude subscription call failed: {str(final.get('result') or '').strip()[:300]}")
                if not streamed and final.get("result"):
                    yield final["result"]
            except BaseException:
                self.close()  # the process state is unknown after any error or an early stop: start clean next time
                raise


def _token() -> str:
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
    if not token:
        raise RuntimeError("CLAUDE_CODE_OAUTH_TOKEN is not set (run setup and paste the token from `claude setup-token`)")
    return token


def _isolated_env(home: str, token: str) -> dict:
    return {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"), "HOME": home,
            "CLAUDE_CODE_OAUTH_TOKEN": token, "DISABLE_AUTOUPDATER": "1", "DISABLE_TELEMETRY": "1"}




def version() -> str:
    """`claude --version`, or "" if Claude Code is not installed."""
    return subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
