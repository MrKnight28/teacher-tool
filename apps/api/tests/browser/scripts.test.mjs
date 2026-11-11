// Browser checks for teacher scripts: the lesson runs by itself, asks a question, waits, takes the answer, and carries on.
// Runs in installed Edge with the server routes mocked. Run from apps/api/tests/browser: node scripts.test.mjs
import { readFile } from 'node:fs/promises';
import { strict as assert } from 'node:assert';
import { launch } from './launch.mjs';

const UI = new URL('../../tutor/ui.html', import.meta.url);
const sleep = ms => new Promise(r => setTimeout(r, ms));

function wav(seconds = 0.8, rate = 22050) {
  const n = Math.floor(seconds * rate), data = Buffer.alloc(n * 2), h = Buffer.alloc(44);
  h.write('RIFF', 0); h.writeUInt32LE(36 + data.length, 4); h.write('WAVE', 8); h.write('fmt ', 12);
  h.writeUInt32LE(16, 16); h.writeUInt16LE(1, 20); h.writeUInt16LE(1, 22); h.writeUInt32LE(rate, 24);
  h.writeUInt32LE(rate * 2, 28); h.writeUInt16LE(2, 32); h.writeUInt16LE(16, 34); h.write('data', 36);
  h.writeUInt32LE(data.length, 40);
  return Buffer.concat([h, data]);
}
const WAV = wav();
const sse = events => events.map(e => `data: ${JSON.stringify(e)}\n\n`).join('');

// Slide index 1 is "Fuses" (index 0 is the "## Basics" stage). Its script has a question with a hidden expect line,
// which the server strips, so the page only ever gets text and a question flag.
const LESSON = {
  day: '2026-10-06', title: 'Fuses', exam_date: '2027-06-30', domains: [], quiz: [],
  stages: [{ name: 'Basics', minutes: 5 }], stage_minutes: {},
  markdown: '## Basics\n### Fuses\nA fuse is a safety part.\n',
  scripts: {
    '1': [
      { text: 'Kyle, a fuse protects a circuit.', question: false },
      { text: 'Kyle, what does a fuse do?', question: true },
      { text: 'Good. Keep going.', question: false },
    ],
  },
};

async function waitFor(fn, ms = 20000) {
  const end = Date.now() + ms;
  while (Date.now() < end) { if (await fn()) return true; await sleep(100) }
  return false;
}

async function open(browser, { clock = false } = {}) {
  const context = await browser.newContext();
  const page = await context.newPage();
  const calls = { tts: [], checkin: [] };
  if (clock) await page.clock.install();
  await page.addInitScript(() => {
    window.__audioActive = new Set();
    const play = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function () {
      window.__audioActive.add(this);
      const done = () => window.__audioActive.delete(this);
      this.addEventListener('ended', done); this.addEventListener('pause', done);
      const p = play.call(this); if (p && p.catch) p.catch(done); return p;
    };
  });
  const html = await readFile(UI, 'utf8');
  await page.route('**/*', async route => {
    const req = route.request(), url = new URL(req.url());
    const json = body => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
    if (url.pathname === '/') return route.fulfill({ contentType: 'text/html; charset=utf-8', body: html });
    if (url.pathname === '/api/voice/status') return json({ transcribe: 'local', speak: true, model_ready: true,
      whisper_model: 'base.en', lesson_voice: 'kokoro', tts_fallback: 'piper', gemini_billing: 'free',
      auto_advance: 'off', name: 'Kyle', pronounce: [] });
    if (url.pathname === '/api/lesson') return json(LESSON);
    if (url.pathname === '/api/notes') return json({ notes: [] });
    if (url.pathname === '/api/chat/history') return json({ messages: [] });
    if (url.pathname === '/api/voice/timings') return json({ ok: true });
    if (url.pathname === '/api/voice/transcribe') return json({ text: 'It breaks the circuit' });
    if (url.pathname === '/api/voice/tts') {
      calls.tts.push(req.postDataJSON().text);
      await sleep(150);
      return route.fulfill({ contentType: 'audio/wav', body: WAV });
    }
    if (url.pathname === '/api/checkin') {
      calls.checkin.push(req.postDataJSON());
      return route.fulfill({ contentType: 'text/event-stream', body: sse([
        { type: 'delta', text: "Yes, that's right." },
        { type: 'sentence', text: "Yes, that's right." },
        { type: 'done', reply: "Yes, that's right." }]) });
    }
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{"error":"not mocked"}' });
  });
  await page.goto('http://127.0.0.1:8080/');
  await page.waitForSelector('#stepper .step');
  return { context, page, calls };
}

const chip = page => page.textContent('#state');
// The lesson runs by itself: Start speaks the welcome, then the slides, and stops at the first question.
const startLesson = async page => {
  await page.click('#start'); await sleep(200);
  await page.waitForFunction(() => document.querySelector('#state').textContent === 'Your turn', null, { timeout: 30000 });
};

const tests = {
  async 'script plays, asks a question, waits, takes the answer and carries on'(browser) {
    const { context, page, calls } = await open(browser);
    await startLesson(page);
    assert(calls.tts.includes('Kyle, a fuse protects a circuit.') && calls.tts.includes('Kyle, what does a fuse do?'),
      `the script should be spoken in order, got ${JSON.stringify(calls.tts)}`);
    assert.equal(calls.tts.indexOf('Kyle, what does a fuse do?'), calls.tts.length - 1, 'nothing after the question yet');
    await page.fill('#askInput', 'It breaks the circuit');
    await page.click('#askBtn');
    assert(await waitFor(async () => calls.checkin.length === 1), 'the answer should go to /api/checkin');
    assert.equal(calls.checkin[0].question_index, 1, 'the question is the second line of this script');
    assert.equal(calls.checkin[0].slide, 1);
    assert(await waitFor(async () => calls.tts.includes('Good. Keep going.')), 'the script should carry on after the reply');
    assert(await waitFor(async () => (await chip(page)) === 'Ready', 30000), 'the lesson should finish on its own');
    await context.close();
  },

  async 'Skip carries on without an answer'(browser) {
    const { context, page, calls } = await open(browser);
    await startLesson(page);
    await page.click('#skip');
    assert(await waitFor(async () => calls.tts.includes('Good. Keep going.')), 'Skip should continue the script');
    assert.equal(calls.checkin.length, 0, 'Skip sends no answer');
    await context.close();
  },

  async 'after 25 seconds of silence there is one gentle nudge, then it waits again'(browser) {
    const { context, page, calls } = await open(browser, { clock: true });
    await startLesson(page);
    await page.clock.fastForward(25500);
    assert(await waitFor(async () => calls.tts.some(t => t.startsWith('Take your time'))), 'the nudge should be spoken');
    assert(await waitFor(async () => (await chip(page)) === 'Your turn'), 'and then it waits again');
    assert.equal(calls.checkin.length, 0);
    await context.close();
  },

  async 'Stop clears the script, the question and the queue'(browser) {
    const { context, page, calls } = await open(browser);
    await startLesson(page);
    await page.click('#stop');
    await sleep(300);
    const before = calls.tts.length;
    await sleep(2000);
    assert.equal(await chip(page), 'Ready');
    assert.equal(calls.tts.length, before, 'Stop should stop new requests');
    assert.equal(await page.evaluate(() => window.__audioActive.size), 0);
    await context.close();
  },
};

const browser = await launch();
let failed = 0;
try {
  for (const [name, run] of Object.entries(tests)) {
    try { await run(browser); console.log('PASS', name) }
    catch (e) { failed++; console.log('FAIL', name, '\n   ', e.message.split('\n')[0]) }
  }
} finally {
  await browser.close();
}
console.log(failed ? `${failed} failed` : 'all script checks passed');
process.exit(failed ? 1 : 0);
