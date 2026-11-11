# Classroom events

The lesson page (`apps/api/tutor/ui.html`) only **renders state** and **reports what the student did**. Whatever owns
progression (today the lesson file in the page, later the backend) sends **events in** and receives **actions out**.
There is one event path: `dispatch(event)` -> serial queue -> `reduceLesson(state, event)` -> render.
The pure reducer sits between `/* @@lesson-core */` markers and is tested under Node (`tests/test_lesson_core.py`).
The voice state machine (`M`) is unchanged and still owns mic, listening, speaking, Stop and cancellation.

## Events in (engine to page)
| event | fields | page shows |
|---|---|---|
| `lesson_started` | `lesson: {course, number, label, title, practice, objectives[], sections[{id,name,minutes}]}` | header, Start screen |
| `section_started` | `index` or `id`, `name`, `minutes`, `progress: {pct}` | section strip, progress bar, status Teaching |
| `teaching` | `title`, `objective`, `blocks[]`, `say` (string or list) | teaching area; no `blocks` keeps the board |
| `question` | `id`, `text` (also spoken) | "Question" panel, status Asking |
| `waiting_for_student` | `id` | "Your turn", mic pulses, answer box. No Next click |
| `student_answer_received` | `text` | "Your answer" |
| `evaluating` | `id` | "Checking", status Thinking |
| `remediating` | `text` (spoken), optional `blocks`, `title` | explanation note, status Explaining |
| `exam_question` | `id, stem, options[{key,text}], objective, number, total, kind` | exam card A-D, status Exam question |
| `answer_result` | `id, correct, correct_key, explanation, selected, requires_continue` | right/wrong marking, status Reviewing |
| `lesson_completed` | none | done card |

Any event may carry `progress: {pct}` (clamped 0-100). Unknown events are ignored, so the engine can add new ones safely.
A `say` field (or the text of `question`/`remediating`) is spoken, and the queue waits for the speech to finish.
Page-local `ui_*` events (`ui_select`, `ui_submitted`, ...) are not engine events.

## Teaching blocks
`text`, `heading`, `list`, `definition {term, text}`, `example`, `terms`, `exam_tip`, `diagram {svg}`.
All text is written with `textContent`; a diagram is shown only as an `<img>` data URI. Today's Markdown lesson files are
converted by `blocksFromLines`: paragraphs starting `Exam tip:`, `Example:` or `Definition:` become those blocks.

## Actions out (page to engine, `sendAction`)
`begin`, `student_answer {id,text}`, `skip`, `exam_answer {id,key}`, `continue`, `speech_done {ref,id}`, `stop`, `resume`, `finish_summary`.
Answer keys never go to the browser; `answer_result` carries the key only after marking.

## Engines
- **Lesson engine (today's lesson files):** `lessonStep` (between `@@lesson-engine` markers in `ui.html`) is a pure state machine
  (INTRO, TEACHING, ASKING, WAITING_FOR_STUDENT, EVALUATING, REMEDIATING, EXAM_QUESTION, COMPLETED). It returns effects
  (`show`, `speak`, `wait`, `evaluate`, `mark`, `exam`, `complete`); the page carries them out and each effect also sends the
  render events above, so the screen draws from state. Back and Next skip ahead. A right exam answer carries on by itself; a
  wrong one waits for Continue so the reason can be read. `legacyDriver` only reports the exam card's answer and Continue.
- **Mock engine:** `/?mock=1` plays a whole lesson; `/?mock=1&autoplay=0` loads it and waits, so you can feed events from the
  console with `Classroom.dispatch({...})` and read `Classroom.sent`. Lives in `ui.html`, replaced by a backend later.

## Backend still needed
No event stream or endpoint exists yet. `/api/lesson` has no course name, lesson number or practice flag (the page reads
the `<!-- objectives -->` and `<!-- sample -->` comments), `/api/answer` returns no separate `correct_key`/`explanation`, and
there are no per-slide objective titles. Hands-free listening is not available.
