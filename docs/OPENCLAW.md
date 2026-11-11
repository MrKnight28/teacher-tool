# Connecting OpenClaw (WhatsApp reminders)

**The setup script does all of this for you** (config, tokens, plugin install, QR pairing, test message). This page explains what it sets up, for reference and troubleshooting.

The tutor sends reminders to OpenClaw's **inbound webhook** (`POST /hooks/agent`, `deliver: true`, `channel: whatsapp`). It uses the dedicated hooks token, never the gateway operator token. The direct `/tools/invoke` API was rejected because it needs operator-level credentials.

Trade-off: each reminder is one short agent turn, so it costs a tiny amount and the agent could reword it. The SOUL instruction below keeps it verbatim. A future option is a custom hook mapping that delivers the text without an agent turn.

## Replies: the tutor-replies plugin

Inbound WhatsApp messages are answered by `openclaw-plugin/tutor-replies` (plain JavaScript, no dependencies, in this
repo). It registers one `before_dispatch` hook that claims every WhatsApp DM before the OpenClaw agent sees it, posts
`{text, sender}` to the tutor's `/api/wa/inbound`, and returns the tutor's reply. So:
- the agent never runs on an inbound message: a message can't instruct it, and replies cost nothing;
- `/api/wa/inbound` accepts only `TUTOR_WA_TOKEN` (written to `.env` and `openclaw/openclaw.env` by setup), and that
  token opens nothing else. The main `TUTOR_TOKEN` never goes to OpenClaw;
- the tutor answers only `WHATSAPP_TO`; anything else gets 403 and the plugin stays silent;
- commands are fixed (status, move, skip, quiz, help). Quiz answers are shown only after an attempt.

On Windows, Docker Desktop shows every shared folder as owned by `root` and world-writable, and the OpenClaw container runs as the
unprivileged `node` user (uid 1000). On such a folder OpenClaw cannot `chmod` its own files (`EPERM: operation not permitted,
fchmod`), refuses to load plugins (`path_world_writable`; shown as "Plugin artifact has no valid plugin manifest"), and cannot lock
its SQLite state (the gateway loops in "OpenClaw doctor" with `failed to verify agent database maintenance lease`). So none of
OpenClaw's files are in a Windows folder: `/home/node/.openclaw` (config, state, workspace, installed plugins) is the
`openclaw-home` volume, the WhatsApp login is `openclaw-auth`, and the plugin is copied into `openclaw-plugins`.

`docker compose --profile whatsapp --profile whatsapp-cli run --rm openclaw-plugin-sync` prepares them: it gives the first two to
uid 1000, copies the config setup wrote (`openclaw/config/openclaw.json`, so setup stays the source of truth) and `SOUL.md` into
`openclaw-home`, and copies `openclaw-plugin/` into `openclaw-plugins`. Setup runs it before the gateway starts; run it again after
changing the plugin's code or `openclaw/config/openclaw.json`. Look at OpenClaw's files with
`docker compose --profile whatsapp --profile whatsapp-cli run --rm -T --entrypoint sh openclaw-cli -c "ls -la ~/.openclaw"`.
Deleting the `openclaw-home`/`openclaw-auth` volumes resets OpenClaw and unpairs WhatsApp.

The one-off `openclaw-cli` container also shares the gateway's *process* namespace (`pid: service:openclaw-gateway`). OpenClaw
locks its database with the owner's pid and start time. From another container, "pid 7" is a different process, so the CLI
declares the gateway's lock stale and takes it, and the gateway then drops every WhatsApp message with `OpenClaw state ownership
... could not be verified`. If you see that, `docker compose --profile whatsapp restart openclaw-gateway` clears it.

The gateway has public DNS servers (1.1.1.1, 8.8.8.8) set, because Docker Desktop's resolver sometimes fails a lookup
(`EAI_AGAIN`), which broke the plugin download. The WhatsApp plugin is installed from npm only (`npm:@openclaw/whatsapp`, three tries).

Setup installs it with `plugins install --link /home/node/plugins/tutor-replies --force --accept-capabilities` and
`plugins enable tutor-replies` (the folder is mounted read-only into both OpenClaw containers). Check it with
`docker compose --profile whatsapp --profile whatsapp-cli run --rm openclaw-cli plugins inspect tutor-replies --runtime --json`:
expect `status: loaded` and one typed hook, `before_dispatch`. Tested against OpenClaw 2026.9.8 (install, enable,
inspect); the full WhatsApp round trip needs a paired phone. The plugin's own checks: `node test.mjs` in its folder.

## Which model passes the reminders on

Replies to your commands use no model. Reminders, nudges, the evening check-in and the Sunday report are written by the tutor and
handed to OpenClaw with the instruction "send this exactly as written, with no changes and no extra text" (`RELAY_INSTRUCTION` in
`notify.py`). A small model on OpenRouter follows it, so it has to be obedient more than clever, and it should cost nothing.

During setup (stage 6) the tutor ranks OpenRouter's free models: text only, 32k+ context, no reasoning, vision or code-only models
(a reasoning model can put its thinking into your WhatsApp message), biggest first. It then sends each of the best eight, in order,
a sample reminder and keeps the first that repeats it word for word, plus the next two as backups (`MODEL_CHEAP` and
`OPENCLAW_FALLBACK_MODELS` in `.env`; `agents.defaults.model.primary` and `.fallbacks` in OpenClaw's config). Free models get
rate-limited or withdrawn, so a rerun of setup picks again; run `.\setup.ps1` if reminders stop arriving. The test calls go
through `LLM.complete(..., task="probe")`, always to OpenRouter, even when lessons use the Claude subscription. A reminder sent
with a `:free` model adds nothing to the monthly spend.

## OpenClaw config (merge into your gateway config)

```json5
{
  gateway: { auth: { password: "<strong password>" } },  // always set
  hooks: {
    enabled: true,
    token: "<long random hooks token>",   // goes in the tutor's OPENCLAW_HOOK_TOKEN
    path: "/hooks",
    allowedAgentIds: ["main"],
    allowRequestSessionKey: false,
  },
}
```

Then `openclaw config validate` and `openclaw gateway restart`. Test:

```
curl http://127.0.0.1:18789/hooks/agent -H 'Authorization: Bearer <hooks token>' \
  -H 'Content-Type: application/json' --data '{"message":"Test","agentId":"main","deliver":false}'
```

## Hardening checklist (from OpenClaw's security history; verify against current docs)

- Run a current, pinned release (several 2026 CVEs, including one-click RCE fixed in 2026.1.29). Run `openclaw security audit --deep --fix`.
- Gateway and Control UI on 127.0.0.1 / Tailscale only. Never expose to the internet.
- No ClawHub skills. Only skills you wrote and read.
- Container: `--read-only`, `--cap-drop=ALL`, no Docker socket, no home-directory mounts.
- Hard spending limit on every model API key.
- Incoming WhatsApp messages are untrusted input: allow commands only from your own number and give message-triggered runs no shell, file or browser tools.
- You chose your own WhatsApp number: a ban or session problem affects your personal WhatsApp. A second SIM/eSIM removes that risk.

## Add to the OpenClaw agent's SOUL.md

```
When a hook message asks you to send a reminder "exactly as written", send that text verbatim and nothing else.
```
