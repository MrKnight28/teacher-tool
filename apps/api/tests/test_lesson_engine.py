"""The lesson engine: what happens next. The engine is pure JavaScript in ui.html, run here under Node.
The browser checks (tests/browser/lesson.test.mjs) cover the same flows with the speech controller and the server."""
import json, shutil, subprocess
from pathlib import Path
import pytest

UI = Path(__file__).resolve().parents[1] / "tutor" / "ui.html"


def _node(script: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    html = UI.read_text()
    core = html.split("/* @@voice-core */")[1].split("/* @@end-voice-core */")[0]
    engine = html.split("/* @@lesson-engine */")[1].split("/* @@end-lesson-engine */")[0]
    p = subprocess.run([node, "-e", core + "\n" + engine + "\n" + script], capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


PRELUDE = r"""
const S = (text, extra = {}) => ({ kind: 'say', slide: 0, qi: -1, text, ...extra });
const C = (text, extra = {}) => ({ kind: 'check', slide: 0, qi: 1, text, ...extra });
const X = (q, options, id = 0) => ({ kind: 'exam', slide: -1, qi: -1, id, objective: '4.8', text: q, options });
// Feed events one at a time. Events that answer an effect take the engine's current seq, as the page does.
function run(steps, plan, eng = lessonInit()){
  const effects = []; let e = eng;
  for(const p of plan){
    const ev = typeof p === 'function' ? p(e) : p;
    const r = lessonStep(e, steps, ev); e = r.eng; effects.push(...r.effects);
  }
  return { eng: e, effects, last: effects[effects.length - 1] };
}
const seq = e => e.seq;
const says = effects => effects.filter(f => f.do === 'speak').map(f => f.text);
"""


def scenario(body: str) -> dict:
    return _node(PRELUDE + body + "\nconsole.log(JSON.stringify(out));")


def test_teaching_steps_advance_on_their_own():
    out = scenario(r"""
    const out = {}; const steps = [S('one'), S('two')];
    const r = run(steps, [{ type: 'start', i: 0 }, seq2 => ({ type: 'spoken', seq: seq2.seq })]);
    out.first_line_spoken = says(r.effects)[0] === 'one';
    const r2 = run(steps, [{ type: 'start', i: 0 }, e => ({ type: 'spoken', seq: e.seq }), e => ({ type: 'spoken', seq: e.seq })]);
    out.second_line_follows_speech = says(r2.effects).slice(0, 2).join('|') === 'one|two';
    out.no_button_needed = !r2.effects.some(f => f.do === 'wait');
    out.then_the_closing_line = r2.eng.state === 'COMPLETED' && r2.last.text === CLOSING;
""")
    assert all(out.values()), out


def test_a_question_waits_for_the_student_and_an_answer_is_evaluated():
    out = scenario(r"""
    const out = {}; const steps = [C('Q?'), S('after')];
    const r = run(steps, [{ type: 'start', i: 0 }, e => ({ type: 'spoken', seq: e.seq })]);
    out.waits = r.eng.state === 'WAITING_FOR_STUDENT' && r.last.do === 'wait';
    const r2 = run(steps, [{ type: 'start', i: 0 }, e => ({ type: 'spoken', seq: e.seq }), e => ({ type: 'spoken', seq: e.seq }),
                           e => ({ type: 'answer', text: 'it breaks', seq: e.seq })]);
    out.answer_triggers_evaluation = r2.last.do === 'evaluate' && r2.last.answer === 'it breaks' && r2.last.qi === 1 && r2.last.slide === 0;
    out.evaluating = r2.eng.state === 'EVALUATING';
""")
    assert all(out.values()), out


def test_a_correct_answer_advances_without_re_asking():
    out = scenario(r"""
    const out = {}; const steps = [C('Q?'), S('after')];
    const r = run(steps, [{ type: 'start', i: 0 }, e => ({ type: 'spoken', seq: e.seq }), e => ({ type: 'spoken', seq: e.seq }),
                          e => ({ type: 'answer', text: 'yes', seq: e.seq }), e => ({ type: 'verdict', verdict: 'correct', seq: e.seq }),
                          e => ({ type: 'spoken', seq: e.seq })]);
    out.moves_on = r.eng.state === 'TEACHING' && r.last.text === 'after';
    out.no_re_ask = says(r.effects).filter(t => t.startsWith("Let's try")).length === 0;
""")
    assert all(out.values()), out


def test_partial_or_wrong_is_remediated_and_asked_again_then_moves_on():
    out = scenario(r"""
    const out = {}; const steps = [C('Q?'), S('after')];
    const answer = v => [e => ({ type: 'answer', text: 'guess', seq: e.seq }), e => ({ type: 'verdict', verdict: v, seq: e.seq }),
                         e => ({ type: 'spoken', seq: e.seq })];
    const base = [{ type: 'start', i: 0 }, e => ({ type: 'spoken', seq: e.seq }), e => ({ type: 'spoken', seq: e.seq })];
    for(const v of ['wrong', 'partial']){
      const r = run(steps, [...base, ...answer(v)]);
      out[v + '_reteaches_and_reasks'] = r.eng.state === 'REMEDIATING' || r.eng.state === 'WAITING_FOR_STUDENT';
      out[v + '_follow_up_text'] = says(r.effects).some(t => t === "Let's try that once more. Q?");
      const again = run(steps, [...base, ...answer(v), e => ({ type: 'spoken', seq: e.seq }),
                                e => ({ type: 'answer', text: 'guess again', seq: e.seq }), e => ({ type: 'verdict', verdict: v, seq: e.seq }),
                                e => ({ type: 'spoken', seq: e.seq })]);
      out[v + '_second_miss_moves_on'] = again.eng.state === 'TEACHING' && again.last.text === 'after';
    }
    const none = run(steps, [...base, ...answer(null)]);
    out.no_verdict_moves_on = none.last.text === 'after' || none.eng.state === 'TEACHING';
""")
    assert all(out.values()), out


def test_an_exam_question_waits_for_the_answer_then_is_marked_and_explained():
    out = scenario(r"""
    const out = {}; const steps = [X('Which control?', ['Alpha', 'Beta', 'Gamma', 'Delta'])];
    const r = run(steps, [{ type: 'start', i: 0 }, e => ({ type: 'spoken', seq: e.seq })]);
    out.shows_card = r.effects.some(f => f.do === 'exam' && f.i === 0);
    out.speaks_options = says(r.effects)[0].includes('A, Alpha. B, Beta. C, Gamma. D, Delta.');
    out.waits = r.eng.state === 'WAITING_FOR_STUDENT';
    const r2 = run(steps, [{ type: 'start', i: 0 }, e => ({ type: 'spoken', seq: e.seq }), e => ({ type: 'answer', text: 'Beta', seq: e.seq })]);
    out.exact_text_marked = r2.last.do === 'mark' && r2.last.answer === 'Beta' && r2.last.id === 0;
    const r3 = run(steps, [{ type: 'start', i: 0 }, e => ({ type: 'spoken', seq: e.seq }), e => ({ type: 'answer', text: 'Beta', seq: e.seq }),
                           e => ({ type: 'marked', seq: e.seq, feedback: 'Correct. Beta is right.' }), e => ({ type: 'spoken', seq: e.seq })]);
    out.feedback_spoken = says(r3.effects).includes('Correct. Beta is right.');
    out.continues_after_feedback = r3.eng.state === 'COMPLETED' && r3.last.text === CLOSING;
""")
    assert all(out.values()), out


def test_spoken_letters_and_words_match_an_option():
    out = scenario(r"""
    const out = {};
    const opts = ['Alpha', 'Beta', 'Gamma', 'Delta'];
    out.letter = matchOption('b', opts) === 1;
    out.option_letter = matchOption('Option C.', opts) === 2;
    out.its_letter = matchOption("It's D", opts) === 3;   // normalises to "it s d"
    out.exact = matchOption('beta', opts) === 1;
    out.words_inside = matchOption('the gamma one', opts) === 2;
    out.nothing_clear = matchOption('banana', opts) === -1;
    out.empty = matchOption('', opts) === -1;
    out.article_is_not_a_letter = matchOption('a firewall', ['A firewall', 'A router', 'A proxy', 'A modem']) === 0;
""")
    assert all(out.values()), out


def test_an_unclear_exam_answer_is_asked_again_then_moves_on():
    out = scenario(r"""
    const out = {}; const steps = [X('Which?', ['Alpha', 'Beta', 'Gamma', 'Delta']), S('after')];
    const base = [{ type: 'start', i: 0 }, e => ({ type: 'spoken', seq: e.seq }), e => ({ type: 'answer', text: 'banana', seq: e.seq })];
    const r = run(steps, base);
    out.asks_again = r.eng.state === 'EXAM_QUESTION' && r.last.text.startsWith('I did not catch that');
    const r2 = run(steps, [...base, e => ({ type: 'spoken', seq: e.seq }), e => ({ type: 'answer', text: 'pizza', seq: e.seq })]);
    out.second_miss_moves_on = r2.eng.state === 'TEACHING' && r2.last.text === 'after' && !r2.effects.some(f => f.do === 'mark');
""")
    assert all(out.values()), out


def test_skip_moves_on_without_an_answer():
    out = scenario(r"""
    const out = {}; const steps = [C('Q?'), S('after')];
    const r = run(steps, [{ type: 'start', i: 0 }, e => ({ type: 'spoken', seq: e.seq }), e => ({ type: 'spoken', seq: e.seq }),
                          { type: 'skip' }]);
    out.skip_continues = r.eng.state === 'TEACHING' && r.last.text === 'after';
    out.no_evaluation = !r.effects.some(f => f.do === 'evaluate');
""")
    assert all(out.values()), out


def test_stale_and_repeated_events_change_nothing():
    out = scenario(r"""
    const out = {}; const steps = [S('one'), S('two')];
    const r = run(steps, [{ type: 'start', i: 0 }]);
    const before = r.eng.seq;
    const stale = lessonStep(r.eng, steps, { type: 'spoken', seq: before - 1 });
    out.stale_spoken_ignored = stale.effects.length === 0 && stale.eng.i === 0;
    const once = lessonStep(r.eng, steps, { type: 'spoken', seq: before });
    const twice = lessonStep(once.eng, steps, { type: 'spoken', seq: before });
    out.repeat_spoken_ignored = twice.effects.length === 0 && twice.eng.i === 1;
    const answer = run(steps, [{ type: 'start', i: 0 }]);
    out.answer_outside_a_question_ignored = lessonStep(answer.eng, steps, { type: 'answer', text: 'x', seq: answer.eng.seq }).effects.length === 0;
""")
    assert all(out.values()), out


def test_stop_pauses_and_a_late_speech_end_cannot_move_on():
    out = scenario(r"""
    const out = {}; const steps = [S('one'), S('two')];
    const r = run(steps, [{ type: 'start', i: 0 }]);
    const paused = lessonStep(r.eng, steps, { type: 'pause' });
    out.paused = paused.eng.state === 'PAUSED' && paused.effects.length === 0;
    const late = lessonStep(paused.eng, steps, { type: 'spoken', seq: r.eng.seq });
    out.late_speech_end_ignored = late.effects.length === 0 && late.eng.i === 0;
    const resumed = lessonStep(paused.eng, steps, { type: 'start', i: paused.eng.i });
    out.resume_speaks_the_same_line = resumed.effects[resumed.effects.length - 1].text === 'one';
""")
    assert all(out.values()), out


def test_a_replaced_question_cannot_be_answered_by_the_old_one():
    out = scenario(r"""
    const out = {}; const steps = [C('Q?'), S('after')];
    const r = run(steps, [{ type: 'start', i: 0 }, e => ({ type: 'spoken', seq: e.seq }), e => ({ type: 'spoken', seq: e.seq })]);
    const old = r.eng.seq;
    const paused = lessonStep(r.eng, steps, { type: 'pause' });
    const restarted = lessonStep(paused.eng, steps, { type: 'start', i: 0 });
    out.old_answer_ignored = lessonStep(restarted.eng, steps, { type: 'answer', text: 'late', seq: old }).effects.length === 0;
""")
    assert all(out.values()), out


def test_steps_follow_the_script_then_the_slide_text_then_the_exam():
    out = scenario(r"""
    const out = {};
    const slides = [{ stage: 0, title: 'Basics', lines: [] }, { stage: 0, title: 'Fuses', lines: ['A fuse is a safety part.'] }];
    const slides3 = [...slides, { stage: 0, title: 'Other', lines: ['A fuse is a safety part.'] }];
    const scripts = { '1': [{ text: 'Kyle, a fuse protects.', question: false }, { text: 'Kyle, what does a fuse do?', question: true }] };
    const steps = buildSteps(slides3, scripts, [{ id: 0, objective: '2.4', q: 'Which?', options: ['a', 'b', 'c', 'd'] }]);
    out.slide_zero_is_its_title = steps[0].kind === 'say' && steps[0].text === 'Basics';
    out.script_lines_are_say_or_check = steps[1].kind === 'say' && steps[2].kind === 'check' && steps[2].qi === 1;
    out.no_script_means_slide_sentences = steps[3].text === 'Other.' && steps[4].text === 'A fuse is a safety part.';
    out.exam_comes_last = steps[steps.length - 1].kind === 'exam' && steps[steps.length - 1].options.length === 4;
    out.next_skips_to_next_slide = slideStartAfter(steps, 1) === 3;
    out.next_from_last_goes_to_exam = slideStartAfter(steps, 4) === steps.length - 1;
""")
    assert all(out.values()), out
