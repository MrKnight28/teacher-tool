// Browser checks for the classroom screen: the lesson header, the tutor's status, the "Your turn" panel, the exam
// question, progress, and the voice states, driven by lesson events rather than Next clicks.
// Runs in installed Edge (or the Chromium named in BROWSER_PATH) with every server route mocked, so no model, voice
// or network is needed. Run from apps/api/tests/browser: node classroom.test.mjs
//
// Two ways in:
//   /?mock=1&autoplay=0   the page's mock engine loads a lesson and plays nothing; the checks feed events by hand
//                         with Classroom.dispatch(...) and read what the page sent back from Classroom.sent.
//   /?mock=1              the mock engine plays a whole short lesson by itself.
//   /                     today's lesson file (the in-page driver), with /api/lesson mocked.
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

// Today's lesson file as /api/lesson returns it: Markdown, stage names, and the quiz without answer keys.
const LESSON = {
  day: '2026-10-07', title: 'Incident response basics', exam_date: '2027-06-30',
  domains: [{ id: '4', title: 'Security Operations' }], stage_minutes: {}, scripts: {},
  stages: [{ name: 'Stage 1: Retrieval', minutes: 5 }, { name: 'Stage 2: Teaching', minutes: 10 }],
  markdown: '<!-- objectives: 4.8 -->\n<!-- sample: practice lesson, answers are not recorded as progress -->\n# Incident response basics\n' +
    '## Stage 1: Retrieval (5 min)\n### Warm-up\n- What does CIA stand for?\n' +
    '## Stage 2: Teaching (10 min)\n### The lifecycle\nPreparation, detection, containment, eradication, recovery, lessons learned.\n\n' +
    'Exam tip: Containment comes before eradication.\n',
  quiz: [
    { id: 0, objective: '4.8', type: 'multiple_choice', q: 'Ransomware is confirmed on one workstation. What comes next?',
      options: ['Eradication', 'Containment', 'Recovery', 'Lessons learned'] },
    { id: 1, objective: '4.8', type: 'free_text', q: 'Why take a forensic image before wiping a machine?', options: [] },
  ],
};
const ANSWER = ['Good question.', 'A firewall filters traffic between networks.'];

// Blocks in the structured format the engine will send (docs/CLASSROOM-EVENTS.md).
const TEACHING = {
  type: 'teaching', title: 'Authentication factors', objective: { id: '4.6', title: 'Implement and maintain identity and access management' },
  progress: { pct: 40 },
  blocks: [
    { type: 'text', text: 'Authentication proves who you are.' },
    { type: 'definition', term: 'Multifactor authentication (MFA)', text: 'Two or more different types of factor.' },
    { type: 'terms', items: [{ term: 'Something you know', text: 'password' }, { term: 'Something you have', text: 'phone' }, { term: 'Something you are', text: 'fingerprint' }] },
    { type: 'diagram', svg: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 20"><rect width="40" height="20" fill="#fff"/></svg>', alt: 'Factors' },
    { type: 'example', text: 'A password, then a prompt on your phone.' },
    { type: 'exam_tip', text: 'Two passwords are not MFA.' },
    { type: 'text', text: '<img src=x onerror="window.__hacked=1">' },
  ],
};
const EXAM = { type: 'exam_question', id: 'x1', objective: '4.6', kind: 'multiple_choice', number: 1, total: 2,
  stem: 'A user enters a password and then approves a push notification. Which factors are used?',
  options: ['Something you know and something you have', 'Something you are and something you know', 'Something you have and somewhere you are', 'Something you know only'] };

async function waitFor(fn, ms = 20000) {
  const end = Date.now() + ms;
  while (Date.now() < end) { if (await fn()) return true; await sleep(100) }
  return false;
}

// query: '' for today's lesson file, 'mock=1&autoplay=0' to feed events by hand, 'mock=1' for the mock engine's own lesson.
async function open(browser, { query = '', transcribeMs = 0 } = {}) {
  const context = await browser.newContext();
  const page = await context.newPage();
  const calls = { tts: [], answer: [], finish: [], chat: 0 };
  await page.addInitScript(() => {
    window.__audioActive = new Set(); window.__maxAudio = 0;
    const play = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function () {
      window.__audioActive.add(this); window.__maxAudio = Math.max(window.__maxAudio, window.__audioActive.size);
      const done = () => window.__audioActive.delete(this);
      this.addEventListener('ended', done); this.addEventListener('pause', done); this.addEventListener('error', done);
      const p = play.call(this); if (p && p.catch) p.catch(done); return p;
    };
  });
  const html = await readFile(UI, 'utf8');
  await page.route('**/*', async route => {
    const req = route.request(), url = new URL(req.url());
    const json = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (url.pathname === '/') return route.fulfill({ contentType: 'text/html; charset=utf-8', body: html });
    if (url.pathname === '/api/voice/status') return json({ transcribe: 'local', speak: true, model_ready: true, whisper_model: 'base.en',
      lesson_voice: 'kokoro', tts_fallback: 'piper', gemini_billing: 'free', auto_advance: 'off', name: 'Kyle', pronounce: [] });
    if (url.pathname === '/api/lesson') return json(LESSON);
    if (url.pathname === '/api/progress') return json({ objectives: [{ id: '4.8', title: 'Incident response', domain: 4, status: 'not_started' }] });
    if (url.pathname === '/api/notes') return json({ notes: [] });
    if (url.pathname === '/api/chat/history') return json({ messages: [] });
    if (url.pathname === '/api/voice/timings') return json({ ok: true });
    if (url.pathname === '/api/voice/transcribe') { await sleep(transcribeMs); return json({ text: 'What is a firewall?' }) }
    if (url.pathname === '/api/voice/tts') {
      calls.tts.push(req.postDataJSON().text);
      await sleep(150);
      return route.fulfill({ contentType: 'audio/wav', body: WAV });
    }
    if (url.pathname === '/api/chat/stream') {
      calls.chat++;
      return route.fulfill({ contentType: 'text/event-stream', body: sse([
        { type: 'delta', text: ANSWER.join(' ') }, ...ANSWER.map(text => ({ type: 'sentence', text })), { type: 'done', reply: ANSWER.join(' ') }]) });
    }
    if (url.pathname === '/api/answer') {
      const body = req.postDataJSON(); calls.answer.push(body);
      return json(body.id === 0 ? { correct: true, feedback: 'Correct. Isolate the host first.' }
        : { correct: false, feedback: 'Not quite. Answer: to preserve evidence. Wiping destroys it.' });
    }
    if (url.pathname === '/api/finish') { calls.finish.push(req.postDataJSON()); return json({ ok: true }) }
    return json({ error: 'not mocked' }, 404);
  });
  await page.goto('http://127.0.0.1:8080/' + (query ? '?' + query : ''));
  await page.waitForSelector(query.includes('mock') ? '#lhTitle:not(:text("Loading"))' : '#stepper .step');
  return { context, page, calls };
}

const text = (page, sel) => page.textContent(sel);
const visible = (page, sel) => page.isVisible(sel);
const dispatch = (page, ev) => page.evaluate(e => window.Classroom.dispatch(e), ev).then(() => sleep(60));
const phase = page => page.evaluate(() => window.Classroom.state.phase);
const sentActions = page => page.evaluate(() => window.Classroom.sent);
const status = page => text(page, '#teacherStatusText');
const lastSent = async page => (await sentActions(page)).at(-1);
const holdMic = page => page.evaluate(() => document.querySelector('#mic').dispatchEvent(new PointerEvent('pointerdown')));
const releaseMic = page => page.evaluate(() => document.querySelector('#mic').dispatchEvent(new PointerEvent('pointerup')));
// Start the lesson, in an engine lesson with nothing playing (hold mode): the intro goes away and nothing else happens.
const begin = async page => { await page.click('#start'); await sleep(100) };

const tests = {
  // 1
  async 'the lesson opens with course, title, section, objective and progress'(browser) {
    const { context, page } = await open(browser);
    assert.equal(await text(page, '#lhCourse'), 'Security+');
    assert((await text(page, '#lhNo')).startsWith(' · '), 'the date shows where a lesson number would be');
    assert.equal(await text(page, '#lhTitle'), 'Incident response basics');
    assert(await visible(page, '#lhPractice'), 'the practice marker in the file shows as a Practice lesson tag');
    assert.equal(await text(page, '#lhSection'), 'Section 1 of 3 · Retrieval');
    assert(await waitFor(async () => (await text(page, '#lhObjective')) === 'Objective 4.8 · Incident response'), 'the objective gets its title from /api/progress');
    assert.equal(await page.getAttribute('#meter', 'aria-valuenow'), '0');
    assert.equal(await page.getAttribute('#meter', 'role'), 'progressbar');
    assert.equal(await status(page), 'Ready', 'nothing has started yet');
    assert(await visible(page, '#intro'), 'the Start screen shows first');
    assert(await visible(page, '#next') && await visible(page, '#prev'), "today's lesson file keeps Back and Next, to skip ahead");
    await context.close();
  },

  // 2
  async 'the teaching state shows definitions, terms, examples, a diagram and an exam tip'(browser) {
    const { context, page } = await open(browser, { query: 'mock=1&autoplay=0' });
    assert.equal(await text(page, '#lhCourse'), 'Security+ SY0-701');
    assert.equal(await text(page, '#lhNo'), ' · Lesson 4');
    assert.equal(await text(page, '#lhTitle'), 'Authentication and Access Control');
    await begin(page);
    await dispatch(page, { type: 'section_started', index: 1 });
    await dispatch(page, TEACHING);
    assert.equal(await status(page), 'Teaching');
    assert.equal(await text(page, '#board h2'), 'Authentication factors');
    assert.equal(await text(page, '#board .kicker'), 'Section 2 · Teaching');
    assert.equal(await text(page, '.blk-def .term'), 'Multifactor authentication (MFA)');
    assert.equal(await page.locator('.blk-terms .tchip').count(), 3);
    assert(await visible(page, '.blk-example'));
    assert.equal(await text(page, '.blk-tip p'), 'Two passwords are not MFA.');
    assert((await page.getAttribute('img.blk-diagram', 'src')).startsWith('data:image/svg+xml'), 'a diagram is only ever an image');
    assert.equal(await text(page, '#lhCurrentName'), 'Authentication factors');
    assert.equal(await text(page, '#lhObjective'), 'Objective 4.6 · Implement and maintain identity and access management');
    assert.equal(await page.evaluate(() => window.__hacked), undefined, 'lesson text is never run as HTML');
    assert(await page.locator('#board img[src="x"]').count() === 0);
    assert(await page.isHidden('#next') && await page.isHidden('#prev'), 'no Next or Back where the engine owns the lesson');
    await context.close();
  },

  // 3 and 4
  async 'a question asks, then waits with "Your turn"'(browser) {
    const { context, page } = await open(browser, { query: 'mock=1&autoplay=0' });
    await begin(page);
    await dispatch(page, TEACHING);
    await dispatch(page, { type: 'question', id: 'q1', text: 'Name the three types of factor.' });
    assert.equal(await status(page), 'Asking');
    assert(await visible(page, '#turn'));
    assert.equal(await text(page, '#turnBadge'), 'Question');
    assert.equal(await text(page, '#turnQ'), 'Name the three types of factor.');
    await dispatch(page, { type: 'waiting_for_student', id: 'q1' });
    assert(await waitFor(async () => (await text(page, '#turnBadge')) === 'Your turn'), 'waiting comes after the question has been spoken');
    assert.equal(await text(page, '#turnBadge'), 'Your turn');
    assert((await text(page, '#turnHint')).includes('Waiting for your answer'));
    assert.equal(await text(page, '#state'), 'Your turn', 'the voice state agrees');
    assert(await page.locator('#mic.pulse').count() === 1, 'the mic pulses while it waits');
    assert(await visible(page, '#skip'));
    assert((await page.getAttribute('#askInput', 'placeholder')).startsWith('Answer Kyle'), 'the box asks for the answer');
    assert.equal(await text(page, '#board h2'), 'Authentication factors', 'the slide stays up while the student answers');
    assert(await page.isHidden('#next'), 'no Next to press');
    await context.close();
  },

  // 4 continued: the answer goes to the engine, and what comes back moves the lesson on without a click
  async 'an answer is sent to the engine and the lesson moves on from its events'(browser) {
    const { context, page } = await open(browser, { query: 'mock=1&autoplay=0' });
    await begin(page);
    await dispatch(page, TEACHING);
    await dispatch(page, { type: 'question', id: 'q1', text: 'Name the three types of factor.' });
    await dispatch(page, { type: 'waiting_for_student', id: 'q1' });
    assert(await waitFor(async () => (await text(page, '#turnBadge')) === 'Your turn'), 'waiting comes after the question has been spoken');
    await page.fill('#askInput', 'know, have and are');
    await page.click('#askBtn');
    assert(await waitFor(async () => (await sentActions(page)).some(a => a.type === 'student_answer')), 'the answer is reported');
    assert.deepEqual(await lastSent(page), { type: 'student_answer', id: 'q1', text: 'know, have and are' });
    assert.equal(await page.inputValue('#askInput'), '');
    await dispatch(page, { type: 'student_answer_received', id: 'q1', text: 'know, have and are' });
    assert.equal(await text(page, '#turnBadge'), 'Your answer');
    assert((await text(page, '#turnA')).includes('know, have and are'));
    await dispatch(page, { type: 'evaluating', id: 'q1' });
    assert.equal(await status(page), 'Thinking');
    assert.equal(await text(page, '#turnBadge'), 'Checking');
    await dispatch(page, { type: 'remediating', id: 'q1', text: 'Close. The third type is something you are.' });
    assert.equal(await status(page), 'Explaining');
    assert.equal(await text(page, '#turnNote'), 'Close. The third type is something you are.');
    await dispatch(page, { type: 'teaching' });
    assert(await waitFor(async () => await page.isHidden('#turn')), 'the panel goes away by itself, once the explanation has been spoken');
    assert.equal(await status(page), 'Teaching');
    assert.equal(await text(page, '#board h2'), 'Authentication factors', 'a teaching event with no blocks keeps the board');
    assert.equal(await text(page, '#state'), 'Ready');
    await context.close();
  },

  // 5
  async 'an exam question shows A to D and looks nothing like a teaching question'(browser) {
    const { context, page } = await open(browser, { query: 'mock=1&autoplay=0' });
    await begin(page);
    await dispatch(page, EXAM);
    assert.equal(await status(page), 'Exam question');
    assert(await page.isHidden('#turn'), 'it is not the Your turn panel');
    assert((await text(page, '.exam-banner')).includes('Exam question'));
    assert((await text(page, '.exam-banner')).includes('Question 1 of 2'));
    assert((await text(page, '.exam-banner')).includes('Objective 4.6'));
    assert.equal(await text(page, '.exam-stem'), EXAM.stem);
    const keys = await page.locator('.opt .key').allTextContents();
    assert.deepEqual(keys, ['A', 'B', 'C', 'D']);
    assert.equal((await page.locator('.opt .otext').first().textContent()).trim(), 'Something you know and something you have');
    assert.equal(await page.locator('.exam fieldset legend').count(), 1, 'a labelled group of radio buttons');
    assert.equal(await page.locator('.exam input[type=radio]').count(), 4);
    assert(await page.isDisabled('#examSubmit'), 'nothing chosen, nothing to submit');
    assert.equal(await page.locator('#board .blk').count(), 0, 'the lesson text is not on the screen');
    await context.close();
  },

  // 6
  async 'choosing an answer works by click and by key, and submitting sends it'(browser) {
    const { context, page } = await open(browser, { query: 'mock=1&autoplay=0' });
    await begin(page);
    await dispatch(page, EXAM);
    await page.click('.opt[data-key="B"]');
    assert.equal(await page.locator('.opt.sel').count(), 1);
    assert.equal(await page.getAttribute('.opt.sel', 'data-key'), 'B');
    assert(await page.isChecked('.opt[data-key="B"] input'));
    assert(await page.isEnabled('#examSubmit'));
    await page.keyboard.press('c');
    assert.equal(await page.getAttribute('.opt.sel', 'data-key'), 'C', 'a key chooses too');
    assert.equal(await page.locator('.opt.sel').count(), 1);
    await page.keyboard.press('Enter');
    assert(await waitFor(async () => (await sentActions(page)).some(a => a.type === 'exam_answer')));
    assert.deepEqual(await lastSent(page), { type: 'exam_answer', id: 'x1', key: 'C', text: 'Something you have and somewhere you are' });
    assert.equal(await text(page, '#examSubmit'), 'Checking…');
    assert(await page.isDisabled('.opt[data-key="A"] input'), 'the choices lock while it is marked');
    await context.close();
  },

  // 7
  async 'a wrong answer shows the right one, a right answer says Correct, Continue goes back to the engine'(browser) {
    const { context, page } = await open(browser, { query: 'mock=1&autoplay=0' });
    await begin(page);
    await dispatch(page, EXAM);
    await page.click('.opt[data-key="C"]'); await page.click('#examSubmit');
    await dispatch(page, { type: 'answer_result', id: 'x1', selected: 'C', correct: false, correct_key: 'A', explanation: 'The password is something you know; the phone is something you have.' });
    assert.equal(await status(page), 'Reviewing');
    assert(await page.locator('.opt.wrong[data-key="C"]').count() === 1, 'the chosen answer is marked wrong');
    assert(await page.locator('.opt.right[data-key="A"]').count() === 1, 'the right answer is shown');
    assert((await text(page, '.opt.wrong .tagline')).includes('Your answer'));
    assert((await text(page, '.opt.right .tagline')).includes('Correct answer'));
    assert(await visible(page, '#examResult'));
    assert((await text(page, '#examResult .verdict')).includes('Not quite'));
    assert(await page.locator('#examResult.bad').count() === 1);
    assert.equal(await text(page, '#examResult p'), 'The password is something you know; the phone is something you have.');
    assert(await page.evaluate(() => document.activeElement.id === 'examContinue'), 'focus moves to Continue');
    await page.click('#examContinue');
    assert.deepEqual(await lastSent(page), { type: 'continue', id: 'x1' });
    // the next question is a new card, and a right answer reads Correct
    await dispatch(page, { ...EXAM, id: 'x2', number: 2, stem: 'Which model assigns permissions by job function?', options: ['DAC', 'MAC', 'RBAC', 'ABAC'] });
    assert.equal(await text(page, '.exam-stem'), 'Which model assigns permissions by job function?');
    assert(await page.isHidden('#examResult'));
    await page.keyboard.press('3'); await page.keyboard.press('Enter');
    assert.equal((await lastSent(page)).key, 'C', 'the number keys choose too');
    await dispatch(page, { type: 'answer_result', id: 'x2', selected: 'C', correct: true, correct_key: 'C', explanation: 'RBAC grants permissions to roles.' });
    assert(await page.locator('#examResult.ok').count() === 1);
    assert((await text(page, '#examResult .verdict')).includes('Correct'));
    assert((await text(page, '.opt.right .tagline')).includes('correct'));
    assert.equal(await page.locator('.opt.wrong').count(), 0);
    await context.close();
  },

  // 8
  async 'lesson progress and the section strip follow the events'(browser) {
    const { context, page } = await open(browser, { query: 'mock=1&autoplay=0' });
    await begin(page);
    assert.equal(await text(page, '#lhPct'), '0%');
    await dispatch(page, { type: 'section_started', index: 0, progress: { pct: 10 } });
    assert.equal(await text(page, '#lhPct'), '10%');
    assert.equal(await text(page, '#lhPName'), 'Retrieval');
    assert.equal(await text(page, '#lhSection'), 'Section 1 of 3 · Retrieval');
    await dispatch(page, TEACHING);   // 40
    assert.equal(await text(page, '#lhPct'), '40%');
    assert.equal(await page.getAttribute('#meter', 'aria-valuenow'), '40');
    assert((await page.getAttribute('#meter', 'aria-valuetext')).includes('40 percent'));
    assert.equal(await page.evaluate(() => document.querySelector('#meterFill').style.width), '40%');
    await dispatch(page, { type: 'section_started', index: 2, progress: { pct: 70 } });
    assert.equal(await text(page, '#lhSection'), 'Section 3 of 3 · Exam practice');
    assert.equal(await page.locator('#stepper .step').count(), 3);
    assert.equal(await page.locator('#stepper .step.done').count(), 2);
    assert.equal(await page.getAttribute('#stepper .step.active', 'aria-current'), 'step');
    await dispatch(page, { type: 'lesson_completed' });
    assert.equal(await text(page, '#lhPct'), '100%');
    assert.equal(await status(page), 'Lesson complete');
    assert(await visible(page, '.done-card'));
    await context.close();
  },

  // 9
  async 'the voice states show on the tutor status: listening, thinking, explaining'(browser) {
    const { context, page } = await open(browser, { transcribeMs: 1500 });
    await page.click('#start');
    await page.waitForFunction(() => document.querySelector('#state').textContent === 'Ready', null, { timeout: 30000 });
    assert.equal(await status(page), 'Teaching');
    await holdMic(page);
    assert(await waitFor(async () => (await text(page, '#state')) === 'Listening'));
    assert.equal(await status(page), 'Listening');
    await sleep(900); await releaseMic(page);
    assert(await waitFor(async () => (await text(page, '#state')) === 'Writing that down'));
    assert.equal(await status(page), 'Thinking');
    assert(await waitFor(async () => (await text(page, '#state')) === 'Speaking', 30000), 'the answer is spoken');
    assert.equal(await status(page), 'Explaining', "an answer to the student's own question reads as Explaining");
    assert(await waitFor(async () => (await text(page, '#state')) === 'Ready', 30000));
    assert.equal(await status(page), 'Teaching');
    assert.equal(await page.evaluate(() => window.__maxAudio), 1);
    await context.close();
  },

  // 10
  async 'Stop silences the lesson and holds it, and Resume carries on'(browser) {
    const { context, page, calls } = await open(browser, { query: 'mock=1' });
    await page.click('#start');
    assert(await waitFor(async () => (await text(page, '#state')) === 'Speaking', 30000), 'the tutor starts speaking');
    await page.click('#stop');
    await sleep(300);
    const ttsBefore = calls.tts.length, phaseBefore = await phase(page);
    await sleep(2500);
    assert.equal(await text(page, '#state'), 'Ready');
    assert.equal(await page.evaluate(() => window.__audioActive.size), 0, 'nothing is playing');
    assert.equal(calls.tts.length, ttsBefore, 'nothing new is requested');
    assert.equal(await phase(page), phaseBefore, 'the lesson holds where it was');
    assert((await sentActions(page)).some(a => a.type === 'stop'), 'the engine is told');
    assert.equal(await text(page, '#pause'), '▶ Resume');
    await page.click('#pause');
    assert((await sentActions(page)).some(a => a.type === 'resume'));
    assert(await waitFor(async () => (await phase(page)) === 'waiting', 40000), 'the lesson carries on to the question');
    await context.close();
  },

  // 11
  async 'a whole lesson plays itself, and the student never presses Next'(browser) {
    const { context, page } = await open(browser, { query: 'mock=1' });
    assert.equal(await status(page), 'Ready');
    await page.click('#start');
    assert(await waitFor(async () => (await phase(page)) === 'waiting', 40000), 'the tutor asks and waits by itself');
    assert.equal(await text(page, '#turnBadge'), 'Your turn');
    assert(await page.isHidden('#next'));
    await page.fill('#askInput', 'availability');
    await page.press('#askInput', 'Enter');
    assert(await waitFor(async () => (await phase(page)) === 'exam' || (await page.locator('.blk-def').count()) > 0, 40000), 'the lesson moves on');
    assert(await waitFor(async () => (await phase(page)) === 'exam', 60000), 'the exam question arrives by itself');
    assert((await page.locator('.blk-def').count()) === 0, 'the teaching has gone from the board');
    await page.keyboard.press('a'); await page.keyboard.press('Enter');
    assert(await waitFor(async () => visible(page, '#examResult')));
    assert((await text(page, '#examResult .verdict')).includes('Correct'));
    await page.keyboard.press('Enter');                       // Continue
    assert(await waitFor(async () => (await page.getAttribute('.exam', 'data-id')) === 'x2'), 'the second question');
    await page.click('.opt[data-key="A"]'); await page.click('#examSubmit');
    assert(await waitFor(async () => visible(page, '#examResult')));
    assert(await page.locator('.opt.wrong[data-key="A"]').count() === 1 && await page.locator('.opt.right[data-key="C"]').count() === 1);
    await page.click('#examContinue');
    assert(await waitFor(async () => (await phase(page)) === 'completed'), 'the lesson completes');
    assert.equal(await text(page, '#lhPct'), '100%');
    const types = (await sentActions(page)).map(a => a.type);
    assert.deepEqual(['begin', 'student_answer', 'exam_answer', 'continue', 'exam_answer', 'continue'], types.filter(t => t !== 'speech_done'));
    assert(types.filter(t => t === 'speech_done').length >= 3, 'the page said when it had finished speaking');
    await context.close();
  },

  // 12: today's lesson file is run by the lesson engine in the page, and ends in the same exam card, marked by /api/answer
  async "today's lesson file plays itself, then asks exam questions marked by /api/answer"(browser) {
    const { context, page, calls } = await open(browser);
    await page.click('#start');
    assert(await waitFor(async () => visible(page, '.blk-tip'), 60000), 'an "Exam tip:" paragraph in the file shows as an exam tip while the lesson plays');
    assert(await waitFor(async () => (await phase(page)) === 'exam', 90000), 'the lesson reaches the exam questions with no Next click');
    assert(await waitFor(async () => (await text(page, '#lhPct')) !== '0%'), 'progress moved with the steps');
    assert.equal(await text(page, '#lhSection'), 'Section 3 of 3 · Quiz');
    assert.deepEqual(await page.locator('.opt .key').allTextContents(), ['A', 'B', 'C', 'D']);
    // chosen while the question is still being read: it goes in as soon as the tutor waits
    await page.click('.opt[data-key="B"]'); await page.click('#examSubmit');
    assert(await waitFor(async () => visible(page, '#examResult')));
    assert.deepEqual(calls.answer[0], { date: await page.inputValue('#date'), id: 0, answer: 'Containment' }, 'the option text is what was always sent');
    assert.equal(await text(page, '#examResult p'), 'Isolate the host first.', '"Correct." is the verdict, not part of the explanation');
    assert(await page.locator('.opt.right[data-key="B"]').count() === 1);
    assert(await page.isHidden('#examContinue'), 'a right answer carries on by itself');
    assert(await waitFor(async () => (await page.locator('#examText').count()) === 1, 30000), 'then a written question has a text box');
    assert.equal(await page.locator('.opt').count(), 0);
    await page.fill('#examText', 'to keep evidence'); await page.press('#examText', 'Enter');
    assert(await waitFor(async () => visible(page, '#examResult')));
    assert((await text(page, '#examResult .verdict')).includes('Not quite'));
    assert(await waitFor(async () => visible(page, '#examContinue')), 'a wrong answer waits for Continue so the reason can be read');
    await page.click('#examContinue');
    assert(await waitFor(async () => visible(page, '.done-card'), 30000), 'then the lesson is complete');
    await page.fill('#sum', 'Learned the order'); await page.click('.done-card .btn');
    assert(await waitFor(async () => calls.finish.length === 1));
    assert.equal(calls.finish[0].summary, 'Learned the order');
    await context.close();
  },
  async 'launch screen shows on load, lifts once the lesson is ready, and a key skips it'(browser) {
    let { context, page } = await open(browser, { query: 'mock=1&autoplay=0&launch=1' });
    assert(await page.isVisible('#launch'), 'the launch card is up while the page loads');
    assert.equal(await page.getAttribute('#launch', 'aria-hidden'), 'true');
    assert(await waitFor(async () => !(await page.$('#launch')), 6000), 'it removes itself once the lesson has loaded');
    await context.close();
    ({ context, page } = await open(browser, { query: 'mock=1&autoplay=0&launch=1' }));
    await page.keyboard.press('Escape');
    assert(await waitFor(async () => !(await page.$('#launch')), 1200), 'any key skips it');
    await context.close();
    ({ context, page } = await open(browser, { query: 'mock=1&autoplay=0' }));
    assert.equal(await page.$('#launch'), null, 'automated runs skip it unless asked');
    await context.close();
  },
};

const browser = await launch();
let failed = 0;
try {
  for (const [name, run] of Object.entries(tests)) {
    try { await run(browser); console.log('PASS', name) }
    catch (e) { failed++; console.log('FAIL', name, '\n   ', e.message.split("\n").slice(0,6).join(" | ")) }
  }
} finally {
  await browser.close();
}
console.log(failed ? `${failed} failed` : 'all classroom checks passed');
process.exit(failed ? 1 : 0);
