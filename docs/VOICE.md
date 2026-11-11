# Voice

Speech stays on your machine unless you turn on an optional cloud voice.

- **Listening.** faster-whisper, local. The browser sends the recording to the tutor; the text comes back.
- **Speaking.** Kokoro by default, Piper if Kokoro is unavailable, and the browser's own voice as a last resort. Slide audio is built after a lesson is written and served from a cache.
- **Optional cloud speech.** A Gemini key enables Gemini speech. It is off unless you add the key. Setup can also store an OpenAI key.
- **Spend cap.** Every paid model call goes through one gateway. The monthly cap is a number you set in setup or on the admin page. Local speech does not add to it. When the cap is reached, paid calls stop.

The microphone needs `http://127.0.0.1` or HTTPS. On a phone, use the Tailscale link.

Timings and the speech-engine comparison are in [VOICE-DEBUG.md](VOICE-DEBUG.md). Licences for the voice files are in [LICENSES.md](../LICENSES.md).
