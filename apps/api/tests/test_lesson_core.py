"""The lesson page's pure core (reducer, teacher status, block conversion), run under Node against the shipped ui.html."""
import json, shutil, subprocess
from pathlib import Path
import pytest

UI = Path(__file__).resolve().parents[1] / "tutor" / "ui.html"


def _node(script: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    core = UI.read_text().split("/* @@lesson-core */")[1].split("/* @@end-lesson-core */")[0]
    p = subprocess.run([node, "-e", core + "\n" + script], capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def test_events_walk_the_phases_and_unknown_events_are_ignored():
    out = _node(r"""
    let s = initialLesson(); const r = {};
    const run = ev => { s = reduceLesson(s, ev); return s.phase };
    r.q = run({ type: 'question', id: 'a', text: 'Why?' });
    r.w = run({ type: 'waiting_for_student', id: 'a' });
    r.ev = run({ type: 'evaluating', id: 'a' });
    r.rem = run({ type: 'remediating', id: 'a', text: 'Close.' });
    r.t = run({ type: 'teaching', blocks: [{ type: 'text', text: 'Hi' }] });
    r.unknown = run({ type: 'something_new' });
    r.junk = reduceLesson(s, null) === s;
    r.blocks = s.teaching.blocks.length;
    console.log(JSON.stringify(r));""")
    assert out == {"q": "asking", "w": "waiting", "ev": "evaluating", "rem": "remediating", "t": "teaching",
                   "unknown": "teaching", "junk": True, "blocks": 1}


def test_exam_question_selection_and_result():
    out = _node(r"""
    let s = initialLesson(); const r = {};
    s = reduceLesson(s, { type: 'exam_question', id: 'e1', stem: 'Pick', options: [{ key: 'A', text: 'x' }, { key: 'B', text: 'y' }, { key: 'C', text: 'z' }, { key: 'D', text: 'w' }] });
    r.phase = s.phase; r.keys = s.exam.options.map(o => o.key); r.kind = s.exam.kind;
    s = reduceLesson(s, { type: 'ui_select', key: 'B' }); r.sel = s.exam.selected;
    s = reduceLesson(s, { type: 'answer_result', id: 'e1', correct: false, correct_key: 'C', explanation: 'Because' });
    r.after = JSON.stringify(s.exam.result);
    console.log(JSON.stringify(r));""")
    assert out["phase"] == "exam" and out["keys"] == ["A", "B", "C", "D"] and out["kind"] == "choice" and out["sel"] == "B"
    assert "C" in out["after"] and "Because" in out["after"]


def test_progress_is_clamped_and_teacher_status_follows_voice():
    out = _node(r"""
    let s = initialLesson(); const r = {};
    s = reduceLesson(s, { type: 'section_started', index: 0, name: 'A', progress: { pct: 250 } }); r.hi = s.progress.pct;
    s = reduceLesson(s, { type: 'section_started', index: 1, name: 'B', progress: { pct: -5 } }); r.lo = s.progress.pct;
    r.listen = teacherStatus('teaching', 'recording', 'read');
    r.think = teacherStatus('teaching', 'transcribing', 'read');
    r.asking = teacherStatus('asking', 'speaking', 'read');
    r.ready = teacherStatus('idle', 'idle', null);
    console.log(JSON.stringify(r));""")
    assert out["hi"] == 100 and out["lo"] == 0
    assert (out["listen"], out["think"], out["asking"], out["ready"]) == ("Listening", "Thinking", "Asking", "Ready")


def test_markdown_becomes_blocks_and_nothing_is_html():
    out = _node(r"""
    const b = blocksFromLines(['Exam tip: Two passwords are not MFA.', 'Example: a badge and a PIN.', 'Definition: MFA - two or more factors.', '- one', '- two', '<img src=x onerror=1>']);
    console.log(JSON.stringify({ types: b.map(x => x.type), meta: lessonMeta('<!-- objectives: 4.6, 4.8 -->\n<!-- sample -->') }));""")
    assert out["types"][:3] == ["exam_tip", "example", "definition"] and "list" in out["types"]
    assert out["meta"] == {"objectives": ["4.6", "4.8"], "practice": True}
