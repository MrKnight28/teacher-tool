// Browser checks for the lesson page's speech: one playback queue, Stop clears the queue, a new answer cancels old speech.
// Runs in the installed Edge (channel "msedge") with the server routes mocked, so no model or Claude call is needed.
// Run from apps/api/tests/browser:  npm install  then  node voice.test.mjs
import { readFile } from 'node:fs/promises';
import { strict as assert } from 'node:assert';
import { launch } from './launch.mjs';

const UI = new URL('../../tutor/ui.html', import.meta.url);
const sleep = ms => new Promise(r => setTimeout(r, ms));

// A short silent WAV, so the page has real audio to play.
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
const LESSON = {
  day: '2026-10-06', title: 'Authentication basics', exam_date: '2027-06-30', domains: [], quiz: [],
  stages: [{ name: 'Basics', minutes: 5 }], stage_minutes: {},
  markdown: '## Basics\n### Slide one\nAuthentication checks who you are. It happens before access is granted. ' +
            'Passwords are one factor. Tokens are another factor. Keep both separate.\n',
};
const ANSWER = ['Good question.', 'A firewall filters traffic between networks.'];

async function waitFor(fn, ms = 20000) {
  const end = Date.now() + ms;
  while (Date.now() < end) { if (await fn()) return true; await sleep(100) }
  return false;
}

async function open(browser) {
  const context = await browser.newContext();
  const page = await context.newPage();
  const calls = { tts: [], chat: 0 };
  await page.addInitScript(() => {
    // Count audio elements that are playing at once. The queue must keep this at one.
    window.__audioActive = new Set(); window.__maxAudio = 0; window.__plays = 0;
    const play = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function () {
      window.__plays++;
      window.__audioActive.add(this);
      window.__maxAudio = Math.max(window.__maxAudio, window.__audioActive.size);
      const done = () => window.__audioActive.delete(this);
      this.addEventListener('ended', done); this.addEventListener('pause', done); this.addEventListener('error', done);
      const p = play.call(this);
      if (p && p.catch) p.catch(done);
      return p;
    };
  });
  const html = await readFile(UI, 'utf8');
  await page.route('**/*', async route => {
    const req = route.request(), url = new URL(req.url());
    const json = body => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
    if (url.pathname === '/') return route.fulfill({ contentType: 'text/html; charset=utf-8', body: html });
    if (url.pathname === '/api/voice/status') return json({ transcribe: 'local', speak: true, model_ready: true,
      whisper_model: 'base.en', lesson_voice: 'kokoro', tts_fallback: 'piper', gemini_billing: 'free' });
    if (url.pathname === '/api/lesson') return json(LESSON);
    if (url.pathname === '/api/notes') return json({ notes: [] });
    if (url.pathname === '/api/chat/history') return json({ messages: [] });
    if (url.pathname === '/api/voice/timings') return json({ ok: true });
    if (url.pathname === '/api/voice/transcribe') return json({ text: 'What is a firewall?' });
    if (url.pathname === '/api/voice/tts') {
      calls.tts.push(req.postDataJSON().text);
      await sleep(250);                       // a local voice takes a moment per sentence
      return route.fulfill({ contentType: 'audio/wav', body: WAV });
    }
    if (url.pathname === '/api/chat/stream') {
      calls.chat++;
      return route.fulfill({ contentType: 'text/event-stream', body: sse([
        { type: 'delta', text: ANSWER.join(' ') },
        ...ANSWER.map(text => ({ type: 'sentence', text })),
        { type: 'done', reply: ANSWER.join(' ') }]) });
    }
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{"error":"not mocked"}' });
  });
  await page.goto('http://127.0.0.1:8080/');
  await page.waitForSelector('#stepper .step');
  return { context, page, calls };
}

const state = page => page.textContent('#state');
const maxAudio = page => page.evaluate(() => window.__maxAudio);
const playing = page => page.evaluate(() => window.__audioActive.size);

const tests = {
  async 'one playback queue: sentences play in order, never two at once'(browser) {
    const { context, page, calls } = await open(browser);
    await page.click('#start'); await sleep(300);
    await page.waitForFunction(() => document.querySelector('#state').textContent === 'Ready', null, { timeout: 30000 });
    calls.tts.length = 0;   // the lesson has run by itself to the end; Read starts the slide again
    await page.click('#read');
    assert(await waitFor(async () => calls.tts.length >= 3 && await state(page) === 'Ready', 40000), 'Read should speak all sentences');
    assert.equal(await maxAudio(page), 1, 'two audio clips were playing at once');
    assert(calls.tts[0].startsWith('Slide one'), `first sentence was "${calls.tts[0]}"`);
    await context.close();
  },

  async 'Stop clears the queue and nothing more is requested or played'(browser) {
    const { context, page, calls } = await open(browser);
    await page.click('#start'); await sleep(300);
    await page.waitForFunction(() => document.querySelector('#state').textContent === 'Ready', null, { timeout: 30000 });
    calls.tts.length = 0;
    await page.click('#read');
    assert(await waitFor(async () => await playing(page) === 1), 'first sentence should start playing');
    await page.click('#stop');
    const before = calls.tts.length, plays = await page.evaluate(() => window.__plays);
    await sleep(2500);
    assert.equal(calls.tts.length, before, 'Stop should stop new requests');
    assert.equal(await page.evaluate(() => window.__plays), plays, 'Stop should stop new playback');
    assert.equal(await playing(page), 0, 'Stop should silence the audio that was playing');
    assert.equal(await state(page), 'Ready');
    await context.close();
  },

  async 'a new answer cancels the slide that is being read'(browser) {
    const { context, page, calls } = await open(browser);
    await page.click('#start'); await sleep(300);
    await page.waitForFunction(() => document.querySelector('#state').textContent === 'Ready', null, { timeout: 30000 });
    calls.tts.length = 0;
    await page.click('#read');
    assert(await waitFor(async () => await playing(page) === 1), 'Read should start playing');
    // Hold the mic: it cancels the slide, and the mocked transcript becomes a spoken question.
    await page.evaluate(() => document.querySelector('#mic').dispatchEvent(new PointerEvent('pointerdown')));
    await sleep(1200);
    await page.evaluate(() => document.querySelector('#mic').dispatchEvent(new PointerEvent('pointerup')));
    assert(await waitFor(async () => calls.tts.some(t => t.startsWith('Good question')), 30000), 'the answer should be spoken');
    const answerAt = calls.tts.findIndex(t => t.startsWith('Good question'));
    assert(!calls.tts.slice(answerAt).some(t => t.startsWith('Slide') || t.includes('Passwords') || t.includes('Tokens')),
      'slide sentences must not be requested after the answer starts');
    assert(await waitFor(async () => await state(page) === 'Ready', 30000), 'the page should return to Ready');
    assert.equal(await maxAudio(page), 1, 'the answer and the slide overlapped');
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
console.log(failed ? `${failed} failed` : 'all browser checks passed');
process.exit(failed ? 1 : 0);
