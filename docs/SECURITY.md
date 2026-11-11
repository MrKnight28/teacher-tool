# Security notes

Reviewed on 7 Oct 2026 (code reading, tests against the running server, `bandit`, `pip-audit`, and OpenClaw's own
`security audit` against the config setup writes). One user on one PC; the tutor listens on `127.0.0.1` (and your tailnet if you
turned Tailscale on) and everything but the two pages needs `TUTOR_TOKEN`.

## What is in place
- **Access:** one random token (43 characters, made by setup; anything shorter than 16 is refused at start), compared in constant
  time without ever raising. Pages and API answers carry `Cache-Control: no-store`, `X-Frame-Options: DENY`, `Referrer-Policy`
  and a CSP with `frame-ancestors 'none'`. A client that stalls is dropped after 60 s; a bad `Content-Length` is a 400; an
  unexpected error is a plain 500 and the log has only the error's type.
- **WhatsApp:** only `WHATSAPP_TO` gets an answer, over a route that only `TUTOR_WA_TOKEN` opens (and that token opens nothing
  else). OpenClaw runs on the messaging tool profile with shell, elevated tools and the browser explicitly off, group chats off,
  no ClawHub skills. Its config, `.env` and backups are owner-only (600) on Linux and macOS.
- **Prompts:** student answers, chat, summaries, materials and model-written lesson text sit inside `<data>` tags, and
  `untrusted.neutralise()` stops any of them from closing the tag. Quiz answer keys and `expect:` lines never leave the server.
- **Browser setup form** (optional): needs the one-time `?k=` key printed in the setup window and a local Host/Origin, or it
  refuses; otherwise any web page you had open could rewrite `.env` while it ran.
- **Supply chain:** the base image (digest), Claude Code (version) and the Python libraries (exact versions) are pinned; voice
  files are checksummed; the OpenClaw image is a pinned tag.

## To update the pins on purpose
Do it when you choose to, then run the tests and a lesson. `docker buildx imagetools inspect node:22-bookworm-slim` shows the
new digest; `npm view @anthropic-ai/claude-code version`; `pip index versions faster-whisper` (and so on); then
`docker compose build --no-cache api`. A pinned image does not get Debian security fixes by itself, so do this every month or two.

## Things to do yourself
- **Tailscale:** after the first successful login you can delete `TS_AUTHKEY` from `.env`; the login is kept in `tailscale/state`.
- **Backups** are plain zips of `data/` (progress, chat, transcripts, your recordings). Keep the folder private.
- **ntfy:** the topic in `NTFY_URL` is the only secret; make it long and random. Reminder text goes to the ntfy server.
- **Free OpenRouter models** may log what they are sent. Only reminder text (times, objective numbers, lesson titles) goes to the
  WhatsApp messenger model; lessons and chat use your Claude subscription.
- Keep keys in `.env` only. This tree does not contain them.

## Known and not changed
- **OpenClaw gateway and CLI containers are not `read_only`.** Making them so needs tmpfs mounts for the places OpenClaw and npm
  write (`~/.npm`, `~/.cache`, `/tmp/openclaw`) and I could not test that without Docker; a wrong guess breaks the WhatsApp install.
  They keep `cap_drop: ALL` and `no-new-privileges`. Try it on a spare copy first.
- **Every service reads all of `.env`** (including `TS_AUTHKEY` and the Gemini/OpenAI keys). Splitting it per service means moving
  keys to separate files and touching setup, tests and compose.
- **The `setup` and `wizard` containers mount the whole repo read-write** (they write `.env`, `data/`, `openclaw/`). They only run
  during setup, and only our code.
- **`progress.db` is shared by `api` and `scheduler` through a Windows folder.** SQLite locking on such folders is unreliable (it broke
  OpenClaw's own database); the store now waits up to 30 s for a lock and nightly backups limit the damage. Moving it to a Docker
  volume is the real fix and changes how backups and the admin page find it.
- **The Whisper speech model is not pinned to a revision** (Parakeet and the voice files are).
- **Exam answers are shown after any attempt** (by design, it is practice); the first attempt per question is what counts.
