# Node base so the Claude Code CLI is available (for the "Claude subscription" provider); Python runs the tutor.
# Pinned (image digest, Claude Code version, voice libraries in pyproject.toml) so a rebuild gets what was tested, not whatever is
# newest that day. To update on purpose: see docs/SECURITY.md.
FROM node:22-bookworm-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @anthropic-ai/claude-code@2.1.291 && npm cache clean --force
WORKDIR /app
COPY pyproject.toml .
COPY tutor ./tutor
RUN pip3 install --no-cache-dir --break-system-packages ".[voice]"
ENV DISABLE_AUTOUPDATER=1
# The speech model downloads once, on the first voice question, into the data folder (the container's root is read-only).
ENV WHISPER_MODEL_DIR=/data/models WHISPER_MODEL=base.en TRANSCRIBE=local \
    HF_HOME=/data/hf XDG_CACHE_HOME=/data/cache HOME=/tmp \
    TMPDIR=/data/tmp
USER 1000:1000
CMD ["python3", "-m", "tutor", "serve"]
