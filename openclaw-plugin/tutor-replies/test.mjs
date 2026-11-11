// node test.mjs : checks the handler with a fake tutor. No OpenClaw needed.
import assert from "node:assert/strict";
import plugin, { makeHandler, isWhatsAppDm } from "./index.js";

const calls = [];
const fake = (status, body) => async (url, init) => { calls.push({ url, init }); return { status, ok: status < 300, json: async () => body }; };
const env = { TUTOR_URL: "http://api:8080/", TUTOR_WA_TOKEN: "wa-token" };
const quiet = { warn() {} };

// a WhatsApp DM goes to the tutor and the tutor's reply comes back; the agent is skipped (handled: true)
let h = makeHandler({ fetchImpl: fake(200, { reply: "Streak: 3" }), env, log: quiet });
let r = await h({ channel: "whatsapp", content: "status", senderId: "+447700900123" }, {});
assert.deepEqual(r, { handled: true, text: "Streak: 3" });
assert.equal(calls[0].url, "http://api:8080/api/wa/inbound");
assert.equal(calls[0].init.headers.Authorization, "Bearer wa-token");
assert.deepEqual(JSON.parse(calls[0].init.body), { text: "status", sender: "+447700900123" });

// groups and other channels are not touched
assert.equal(await h({ channel: "whatsapp", isGroup: true, content: "hi" }, {}), undefined);
assert.equal(await h({ channel: "telegram", content: "hi" }, {}), undefined);
assert.equal(isWhatsAppDm({}, { channelId: "whatsapp" }), true);

// someone else's number: claimed and silent; tutor down or erroring: claimed with a short notice
h = makeHandler({ fetchImpl: fake(403, {}), env, log: quiet });
assert.deepEqual(await h({ channel: "whatsapp", content: "hi", senderId: "x" }, {}), { handled: true });
h = makeHandler({ fetchImpl: fake(500, {}), env, log: quiet });
assert.match((await h({ channel: "whatsapp", content: "hi" }, {})).text, /isn't answering/);
h = makeHandler({ fetchImpl: async () => { throw new TypeError("fetch failed"); }, env, log: quiet });
assert.match((await h({ channel: "whatsapp", content: "hi" }, {})).text, /isn't answering/);

// no token configured: still claimed, so the agent never answers an inbound message
h = makeHandler({ fetchImpl: fake(200, { reply: "x" }), env: {}, log: quiet });
assert.match((await h({ channel: "whatsapp", content: "hi" }, {})).text, /isn't answering/);

// the plugin registers exactly one before_dispatch hook
const seen = [];
plugin.register({ on: (name, fn, opts) => seen.push([name, typeof fn, opts]), logger: quiet });
assert.deepEqual(seen, [["before_dispatch", "function", { priority: 100 }]]);
console.log("tutor-replies: all checks passed");
