"""Health checks used by setup and the admin Setup tab. Never prints secrets."""
from __future__ import annotations
import os
import subprocess
import urllib.request
from pathlib import Path
from .notify import from_env
from .providers import claude_cli, openrouter


def _writable(p: str | None) -> tuple[bool, str]:
    if not p:
        return False, "not configured"
    d = Path(p)
    try:
        t = d / ".tutor-write-test"
        t.write_text("ok")
        t.unlink()
        return True, "writable"
    except OSError as e:
        return False, f"not writable: {e.strerror}"



def run_checks(data_dir: Path, pack_ok: bool = True, send_test: bool = False) -> list[dict]:
    out = []

    def add(name, ok, detail):
        out.append({"name": name, "ok": bool(ok), "detail": detail})

    add("Course pack", pack_ok, "Security+ SY0-701 loaded" if pack_ok else "failed to load")
    ok, d = _writable(str(data_dir))
    add("Data folder", ok, d)
    if os.environ.get("LLM_PROVIDER") == "claude-cli":
        import shutil
        if not shutil.which("claude"):
            add("Claude subscription", False, "Claude Code CLI not found in the container (rebuild: docker compose up -d --build)")
        elif not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
            add("Claude subscription", False, "no token: re-run setup and paste the token from `claude setup-token`")
        else:
            try:
                v = claude_cli.version()
                add("Claude subscription", True, f"token set; Claude Code {v.split()[0] if v else '?'} (lessons use your plan's limits)")
            except (OSError, subprocess.SubprocessError) as e:
                add("Claude subscription", False, type(e).__name__)
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        try:
            info = openrouter.key_info(key)
            add("OpenRouter", True, f"key valid; used ${info.get('usage', '?')} of limit {info.get('limit')}")
        except Exception as e:  # noqa: BLE001
            add("OpenRouter", False, f"{type(e).__name__}")
    elif os.environ.get("LLM_PROVIDER") != "claude-cli":
        add("OpenRouter", False, "no key: lessons will be study-list stubs")
    if os.environ.get("LLM_PROVIDER") != "claude-cli":
        missing = [m for m in ("MODEL_PLAN", "MODEL_TEACH", "MODEL_MARK") if not os.environ.get(m)]
        add("Models", not missing, "all set" if not missing else f"missing {', '.join(missing)}")
    voice = []
    if os.environ.get("GEMINI_API_KEY"):
        voice.append("Gemini")
    if os.environ.get("OPENAI_API_KEY"):
        voice.append("OpenAI")
    add("Voice keys", bool(voice), ", ".join(voice) if voice else "none yet (voice not built yet either)")
    if os.environ.get("TUTOR_VAULT_DIR"):
        ok, d = _writable(os.environ["TUTOR_VAULT_DIR"])
        add("Obsidian Tutor folder", ok, d)
    if os.environ.get("TUTOR_BACKUP_DIR"):
        ok, d = _writable(os.environ["TUTOR_BACKUP_DIR"])
        add("Backup folder", ok, d)
    if os.environ.get("OPENCLAW_HOOK_URL"):
        try:
            urllib.request.urlopen(os.environ["OPENCLAW_HOOK_URL"], timeout=5).close()
            add("OpenClaw gateway", True, "reachable")
        except urllib.error.HTTPError:
            add("OpenClaw gateway", True, "reachable")
        except OSError as e:
            add("OpenClaw gateway", False, f"not reachable ({type(e).__name__}); is the whatsapp profile running?")
    n = from_env()
    add("Reminder channel", n.name != "console", n.name if n.name != "console" else "none: reminders only go to the log")
    if send_test:
        sent = n.send("Security+ Tutor test message. Reminders will arrive here.")
        add("Test message", sent, "sent" if sent else "failed to send")
    return out


def main(data_dir: Path, send_test: bool) -> int:
    try:
        from .pack import load_pack
        load_pack(Path(os.environ.get("TUTOR_PACKS_DIR", "./packs")), os.environ.get("TUTOR_PACK", "security-plus-sy0-701"), data_dir)
        pack_ok = True
    except Exception:  # noqa: BLE001
        pack_ok = False
    checks = run_checks(data_dir, pack_ok, send_test)
    for c in checks:
        print(f"  {'OK  ' if c['ok'] else 'FAIL'}  {c['name']}: {c['detail']}")
    return 0 if all(c["ok"] for c in checks if c["name"] in ("Course pack", "Data folder")) else 1
