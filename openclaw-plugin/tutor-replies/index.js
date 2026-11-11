// Tutor replies: an OpenClaw plugin for the Security+ tutor (Teacher Tool).
//
// It claims every WhatsApp direct message before the OpenClaw agent sees it (the before_dispatch hook), posts the text
// to the tutor's /api/wa/inbound with its own token, and sends back the tutor's answer. The agent never runs on an
// inbound message, so a message can't instruct it, and replies cost nothing. Group messages and other channels are
// left alone. Settings come from the gateway's environment (openclaw/openclaw.env, written by setup):
//   TUTOR_URL       the tutor inside the Compose network (default http://api:8080)
//   TUTOR_WA_TOKEN  a token that opens only /api/wa/inbound
// No dependencies, no file access, one HTTP call per message.

const TIMEOUT_MS = 15000;
const DOWN = "The tutor isn't answering right now. Is the PC on? Try again in a minute.";

export function isWhatsAppDm(event, ctx) {
  const channel = String(event?.channel || ctx?.channelId || "").toLowerCase();
  return channel.includes("whatsapp") && !event?.isGroup;
}

export function makeHandler({ fetchImpl = globalThis.fetch, env = process.env, log = console } = {}) {
  const url = (env.TUTOR_URL || "http://api:8080").replace(/\/+$/, "") + "/api/wa/inbound";
  const token = env.TUTOR_WA_TOKEN || "";
  return async function beforeDispatch(event, ctx) {
    if (!isWhatsAppDm(event, ctx)) return undefined;          // not ours: the normal path runs
    if (!token) {
      log.warn?.("tutor-replies: TUTOR_WA_TOKEN is not set; WhatsApp replies are off");
      return { handled: true, text: DOWN };                     // still claimed: the agent never answers inbound
    }
    const text = String(event?.content ?? event?.body ?? "").slice(0, 2000);
    const sender = String(event?.senderId || ctx?.senderId || "");
    const ac = new AbortController();
    const timer = setTimeout(() => ac.abort(), TIMEOUT_MS);
    try {
      const r = await fetchImpl(url, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ text, sender }),
        signal: ac.signal,
      });
      if (r.status === 403) return { handled: true };            // not the student's number: say nothing
      if (!r.ok) return { handled: true, text: DOWN };
      const j = await r.json();
      return { handled: true, text: String(j?.reply || DOWN).slice(0, 3000) };
    } catch (e) {
      log.warn?.(`tutor-replies: tutor unreachable (${e?.name || "error"})`);
      return { handled: true, text: DOWN };
    } finally {
      clearTimeout(timer);
    }
  };
}

export default {
  id: "tutor-replies",
  name: "Tutor replies",
  description: "Answers WhatsApp messages from the Security+ tutor's own data, without an agent turn.",
  configSchema: { type: "object", additionalProperties: false },
  register(api) {
    api.on("before_dispatch", makeHandler({ log: api.logger || console }), { priority: 100 });
  },
};
