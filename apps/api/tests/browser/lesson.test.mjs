// Browser checks for the event-driven lesson: teaching advances by itself, a question waits, the answer is judged
// (correct, wrong, partial), exam questions are asked, marked, explained, and the lesson completes with no Next click.
// Runs in installed Edge with the server routes mocked. Run from apps/api/tests/browser: node lesson.test.mjs
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

const QUESTION = 'Kyle, what does a fuse do?';
const LESSON = {
  day: '2026-10-06', title: 'Fuses', exam_date: '2027-06-30', domains: [],
  stages: [{ name: 'Basics', minutes: 5 }], stage_minutes: {},
  markdown: '## Basics\n### Fuses\nA fuse is a safety part.\n',
  scripts: {
    '1': [
      { text: 'Kyle, a fuse protects a circuit.', question: false },
      { text: QUESTION, question: true },
      { text: 'Good. Keep going.', question: false },
    ],
  },
  quiz: [
    { id: 0, objective: '2.4', type: 'multiple_choice', q: 'Which part cuts the power when current is too high?',
      options: ['Firewall', 'Fuse', 'Router', 'Proxy'] },
    { id: 1, objective: '2.4', type: 'multiple_choice', q: 'Which part is a safety part?', options: ['Alpha', 'Beta', 'Gamma', 'Delta'] },
  ],
};
const REPLY = {
  correct: "Yes, that's right.",
  partial: 'Part of that is right. A fuse also protects the circuit.',
  wrong: 'Not quite. A fuse is a safety part that breaks the circuit.',
};
const CORRECT_ANSWERS = ['Fuse', 'Beta'];

async function waitFor(fn, ms = 25000) {
  const end = Date.now() + ms;
  while (Date.now() < end) { if (await fn()) return true; await sleep(100) }
  return false;
}

// `mock.verdicts` is the sequence of judgements the marker returns, one per answer.
async function open(browser) {
  const context = await browser.newContext();
  const page = await context.newPage();
  const calls = { tts: [], checkin: [], answer: [], timings: 0 };
  const mock = { verdicts: [], transcript: 'b' };
  await page.addInitScript(() => {
    window.__audioActive = new Set(); window.__maxAudio = 0;
    const play = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function () {
      window.__audioActive.add(this);
      window.__maxAudio = Math.max(window.__maxAudio, window.__audioActive.size);
      const done = () => window.__audioActive.delete(this);
      this.addEventListener('ended', done); this.addEventListener('pause', done); this.addEventListener('error', done);
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
    if (url.pathname === '/api/progress') return json({ objectives: [] });
    if (url.pathname === '/api/voice/timings') { calls.timings++; return json({ ok: true }) }
    if (url.pathname === '/api/voice/transcribe') return json({ text: mock.transcript });
    if (url.pathname === '/api/voice/tts') {
      calls.tts.push(req.postDataJSON().text);
      await sleep(120);
      return route.fulfill({ contentType: 'audio/wav', body: WAV });
    }
    if (url.pathname === '/api/checkin') {
      calls.checkin.push(req.postDataJSON());
      const verdict = mock.verdicts.shift() || 'none';
      const reply = REPLY[verdict] || "Let's keep going.";
      const events = [];
      if (verdict !== 'none') events.push({ type: 'verdict', verdict });
      events.push({ type: 'delta', text: reply }, { type: 'sentence', text: reply }, { type: 'done', reply });
      return route.fulfill({ contentType: 'text/event-stream', body: sse(events) });
    }
    if (url.pathname === '/api/answer') {
      const body = req.postDataJSON();
      calls.answer.push(body);
      const ok = CORRECT_ANSWERS.includes(body.answer);
      return json({ correct: ok, feedback: ok ? 'Correct. That is the answer.' : 'Not quite. Try the other one.' });
    }
    if (url.pathname === '/api/finish') return json({ ok: true });
    if (url.pathname === '/api/chat/stream') {   // a free question (typed or spoken), answered in one sentence
      return route.fulfill({ contentType: 'text/event-stream', body: sse([
        { type: 'delta', text: ANSWER_LINE }, { type: 'sentence', text: ANSWER_LINE }, { type: 'done', reply: ANSWER_LINE }]) });
    }
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{"error":"not mocked"}' });
  });
  await page.goto('http://127.0.0.1:8080/');
  await page.waitForSelector('#stepper .step');
  return { context, page, calls, mock };
}

const chip = page => page.textContent('#state');
const count = (list, text) => list.filter(t => t === text).length;
const startLesson = async page => {
  await page.click('#start');
  assert(await waitFor(async () => (await chip(page)) === 'Your turn'), 'the lesson should reach the question by itself');
};
const answerByTyping = async (page, text) => {
  await page.fill('#askInput', text);
  await page.click('#askBtn');
};

const tests = {
  async 'teaching advances by itself and the question waits for the student'(browser) {
    const { context, page, calls } = await open(browser);
    await startLesson(page);
    const spoken = calls.tts.filter(t => ['Basics', 'Kyle, a fuse protects a circuit.', QUESTION].includes(t));
    assert.deepEqual(spoken, ['Basics', 'Kyle, a fuse protects a circuit.', QUESTION], 'lines should play in order with no click');
    assert.equal(calls.tts[calls.tts.length - 1], QUESTION, 'nothing is spoken after the question');
    await sleep(800);
    assert.equal(calls.checkin.length, 0, 'the lesson does not answer for the student');
    assert.equal(await chip(page), 'Your turn');
    await context.close();
  },

  async 'a correct typed answer is judged and the lesson moves on by itself'(browser) {
    const { context, page, calls, mock } = await open(browser);
    await startLesson(page);
    mock.verdicts.push('correct');
    await answerByTyping(page, 'It cuts the power');
    assert(await waitFor(async () => calls.tts.includes('Good. Keep going.')), 'after a correct answer the lesson continues');
    assert.equal(calls.checkin.length, 1, 'one answer, one judgement');
    assert.equal(calls.checkin[0].question_index, 1);
    assert.equal(calls.checkin[0].slide, 1);
    assert.equal(calls.checkin[0].answer, 'It cuts the power');
    assert(await waitFor(async () => await page.isVisible('.exam input[type=radio]')), 'then the exam question shows');
    await context.close();
  },

  async 'a wrong answer is reteaching, asked again, and then the lesson moves on'(browser) {
    const { context, page, calls, mock } = await open(browser);
    await startLesson(page);
    mock.verdicts.push('wrong', 'wrong');
    await answerByTyping(page, 'a router');
    assert(await waitFor(async () => calls.tts.includes(REPLY.wrong)), 'the reteaching reply is spoken');
    assert(await waitFor(async () => calls.tts.includes(`Let's try that once more. ${QUESTION}`)), 'the question is asked again');
    assert(await waitFor(async () => (await chip(page)) === 'Your turn'), 'and the lesson waits for the second answer');
    await answerByTyping(page, 'still a router');
    assert(await waitFor(async () => calls.tts.includes('Good. Keep going.')), 'after two misses the lesson moves on');
    assert.equal(calls.checkin.length, 2, 'two answers, two judgements');
    assert.equal(count(calls.tts, `Let's try that once more. ${QUESTION}`), 1, 'the question is re-asked only once');
    await context.close();
  },

  async 'a partly right answer gets a targeted reply and one more try'(browser) {
    const { context, page, calls, mock } = await open(browser);
    await startLesson(page);
    mock.verdicts.push('partial');
    await answerByTyping(page, 'it protects');
    assert(await waitFor(async () => calls.tts.includes(REPLY.partial)), 'the targeted reply is spoken');
    assert(await waitFor(async () => calls.tts.includes(`Let's try that once more. ${QUESTION}`)), 'then the question is asked again');
    await context.close();
  },

  async 'an exam question shows A to D, waits, marks the choice and explains it, then continues'(browser) {
    const { context, page, calls, mock } = await open(browser);
    await startLesson(page);
    mock.verdicts.push('correct');
    await answerByTyping(page, 'It cuts the power');
    assert(await waitFor(async () => await page.isVisible('.exam input[type=radio]')), 'the first exam question is on screen');
    assert.equal(await page.locator('.exam input[type=radio]').count(), 4, 'four options');
    assert(await waitFor(async () => calls.tts.join(' ').includes('A, Firewall.') && calls.tts.join(' ').includes('Which is it?')),
      'the question and its options are spoken');
    assert(await waitFor(async () => (await chip(page)) === 'Your turn'), 'the exam question waits for the answer');
    assert.equal(calls.answer.length, 0, 'nothing is marked before the student answers');
    assert(await waitFor(async () => (await chip(page)) === 'Your turn'));
    await page.click('.exam label.opt:has-text(\"Fuse\")');
    await page.click('#examSubmit');
    assert(await waitFor(async () => calls.answer.length === 1), 'the choice is marked on the server');
    assert.equal(calls.answer[0].answer, 'Fuse', 'the answer is the option text');
    assert(await waitFor(async () => calls.tts.includes('Correct. That is the answer.')), 'the explanation is spoken');
    assert(await waitFor(async () => await page.isVisible('text=Question 2 of 2')), 'the next exam question follows by itself');
    await context.close();
  },

  async 'a spoken letter answers an exam question, and the lesson completes with no Next click'(browser) {
    const { context, page, calls, mock } = await open(browser);
    await startLesson(page);
    mock.verdicts.push('correct');
    await answerByTyping(page, 'It cuts the power');
    assert(await waitFor(async () => await page.isVisible('text=Question 1 of 2')));
    assert(await waitFor(async () => (await chip(page)) === 'Your turn'));
    await page.click('.exam label.opt:has-text(\"Fuse\")');
    await page.click('#examSubmit');
    assert(await waitFor(async () => await page.isVisible('text=Question 2 of 2')));
    assert(await waitFor(async () => (await chip(page)) === 'Your turn'));
    mock.transcript = 'option b';
    await page.evaluate(() => document.querySelector('#mic').dispatchEvent(new PointerEvent('pointerdown')));
    await sleep(1200);
    await page.evaluate(() => document.querySelector('#mic').dispatchEvent(new PointerEvent('pointerup')));
    assert(await waitFor(async () => calls.answer.length === 2), 'the spoken answer is marked');
    assert.equal(calls.answer[1].answer, 'Beta', '"option b" means the second option');
    assert(await waitFor(async () => await page.isVisible('#sum'), 30000), 'the finish box appears when the lesson is complete');
    assert(await waitFor(async () => (await chip(page)) === 'Ready', 30000));
    assert.equal(await page.isDisabled('#next'), true, 'the Next button is not needed to finish');
    await context.close();
  },

  async 'every line is spoken once and every answer is judged once'(browser) {
    const { context, page, calls, mock } = await open(browser);
    await startLesson(page);
    mock.verdicts.push('correct');
    await answerByTyping(page, 'It cuts the power');
    assert(await waitFor(async () => await page.isVisible('text=Question 1 of 2')));
    assert(await waitFor(async () => (await chip(page)) === 'Your turn'));
    await page.click('.exam label.opt:has-text(\"Fuse\")');
    await page.click('#examSubmit');
    assert(await waitFor(async () => await page.isVisible('text=Question 2 of 2')));
    assert(await waitFor(async () => (await chip(page)) === 'Your turn'));
    await page.click('.exam label.opt:has-text(\"Beta\")');
    await page.click('#examSubmit');
    assert(await waitFor(async () => await page.isVisible('#sum'), 30000));
    await sleep(500);
    for (const line of ['Kyle, a fuse protects a circuit.', QUESTION, 'Good. Keep going.']) {
      assert.equal(count(calls.tts, line), 1, `"${line}" was spoken ${count(calls.tts, line)} times`);
    }
    assert.equal(calls.checkin.length, 1, 'one check-in answer, one judgement');
    assert.equal(calls.answer.length, 2, 'two exam answers, two marks');
    await context.close();
  },

  async 'Stop pauses the lesson at once and nothing more is requested'(browser) {
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

  async 'a new spoken question cancels the lesson speech and no lesson line follows it'(browser) {
    const { context, page, calls, mock } = await open(browser);
    await page.click('#start'); await sleep(200);
    await page.waitForFunction(() => document.querySelector('#state').textContent === 'Speaking' || calls.tts.length > 0, null, { timeout: 30000 });
    mock.transcript = 'What is a firewall?';
    await page.evaluate(() => document.querySelector('#mic').dispatchEvent(new PointerEvent('pointerdown')));
    await sleep(1200);
    await page.evaluate(() => document.querySelector('#mic').dispatchEvent(new PointerEvent('pointerup')));
    assert(await waitFor(async () => calls.tts.some(t => t.startsWith('Good question') || t === ANSWER_LINE)), 'the answer should be spoken');
    const at = calls.tts.findIndex(t => t === ANSWER_LINE);
    assert(!calls.tts.slice(at).some(t => t === QUESTION || t === 'Kyle, a fuse protects a circuit.'),
      'lesson lines must not be requested after the answer starts');
    assert.equal(await page.evaluate(() => window.__maxAudio), 1, 'two clips played at once');
    await context.close();
  },
};
const ANSWER_LINE = "Yes, that's right.";

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
console.log(failed ? `${failed} failed` : 'all lesson checks passed');
process.exit(failed ? 1 : 0);
