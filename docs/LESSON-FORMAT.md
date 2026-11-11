# Lesson format, plans, and how a lesson runs

## Three ways a lesson is written
0. **Course lessons (first).** Ready-made lessons in `packs/<pack>/lessons/NN-name.md`, built from study
   notes (see "Course lessons" below). From `lessons_from` (pack.yaml, or the `pack_lessons_from` setting), each study
   day gets the next one. When they are all used, the nightly writer takes over.
1. **Plan (default).** The model writes a structured plan as JSON. `apps/api/tutor/lesson_plan.py` checks it and renders
   the lesson Markdown. The plan is saved next to it as `data/lessons/YYYY-MM-DD.plan.json`.
2. **Markdown fallback.** If the plan is refused twice more (three attempts in all), the old Markdown prompt runs. Its
   text is checked for labels and promised behaviour, and any hit is logged as `lesson_text`. It has no plan, so no
   plan-level checks apply to it.

## The plan
```
title
sections[]   stage, title, objectives[]
             content[]        slide bullets: on screen only
             examples[]       slide examples: on screen only
             say[]            1 to 4 sentences the teacher SAYS, in the teacher's own words
             analogy          optional: a concrete comparison and where it breaks down (spoken)
             checks[]         {question, expect, objective}   1 or 2; spoken, then answered
             misconceptions[] {belief, correction}            on screen as "Common mix-up"; belief is a full sentence
             application      {scenario, question, expect, objective}  scenario on screen, question spoken
retrieval[]       {question, expect, objective}   1 to 3; a Retrieval slide at the start
exam_questions[]  {objective, q, options[4], answer = exact option text, why}   at least 3
homework[]        {objective, task}   stored in the plan file only; not used yet
```
Validation (`lesson_plan.problem`) refuses a plan that:
- has a spoken line that repeats a slide bullet, runs over 60 words, or has more than three acronyms;
- puts a presentation label ("Plain meaning:", "Analogy:", "Example:", "Scenario:", "Note:", "Summary:") in text;
- promises behaviour the lesson does not have (homework used later, retrieval next lesson, next session);
- repeats an exam question's wording in teaching (50% of its words) or gives its answer away (80% of answer words, or exact);
- leaves an objective without a teaching section or an exam question;
- has exam questions that are not exactly four distinct options with an answer that is one of them.

Teaching checks and examples may cover the same objective. That is expected. They may not reuse an exam scenario.

## What the student sees and hears
| Slide (on screen) | Teacher (spoken) |
|---|---|
| `content` bullets | `say` lines, then `analogy`, then, for each misconception, "Here is a common mistake. <belief> That is not right. <correction>" |
| `examples` ("Example: …") | not read; the `say` lines carry the example in the teacher's words |
| misconceptions ("Common mix-up: …") | the spoken misconception line above |
| scenario | "Look at the scenario on the screen." then the check |
| — | checks: `? question` with an `expect:` line (server only) |
| — | exam questions: never on a slide and never in a say block; they appear as quiz cards during the lesson |

Stage headings use `STAGE_NAMES` in `lesson_plan.py` (for example `qa` shows as "Q&A"). Stages not in the table are
shown with their words capitalised.

Spoken sentences go through `sentence()`, which ends text with exactly one of `.`, `!`, `?`.

## The Markdown file (what the classroom reads)
`data/lessons/YYYY-MM-DD.md`:

| Part | Syntax | Notes |
|---|---|---|
| Objectives | `<!-- objectives: 4.8,2.4 -->` on line 1 | Real objective ids from `objectives.yaml` |
| Practice marker | `<!-- sample: ... -->` on line 2 | Only in practice lessons |
| Title | `# Title` | Shown in the top bar |
| Stage | `## Name (N min)` | Shown in the stepper |
| Slide | `### Concept title` | Bullets, `Example:` and `Common mix-up:` lines are shown |
| Teacher script | a fenced `say` block after a slide | Spoken; never shown |
| Check-in question | a `say` line starting `? ` | The lesson waits for an answer |
| Expected idea | `expect: ...` on the next line | Server only; never sent to the browser or spoken |
| Quiz | a fenced `quiz` block with a JSON list | Items carry `"source": "exam"` for plan lessons. Answers never reach the browser |
| Diagram | a fenced `svg` block | Plain shapes and text, a `viewBox`, white background. No script, links or `foreignObject` |

## How a lesson runs
The page is an event-driven state machine (`ui.html`, `@@lesson-engine` block). The engine is pure JavaScript and decides
every step. It sends effects to the speech queue and the server, and reads back events.

- **Start** speaks the welcome, then the lesson runs by itself: each line is spoken in turn, then the next.
- **A check** is spoken, then the lesson waits (state "Your turn"). A typed or spoken answer goes to `/api/checkin`.
  The server sends a `verdict` event first: `correct`, `partial`, `wrong` or `none`.
  - `correct` or `none`: the reply is spoken and the lesson moves on.
  - `partial` or `wrong`: the reply is spoken, the question is asked once more, then the lesson moves on.
  - Skip moves on without an answer. After 25 seconds a gentle prompt is spoken, then it waits again.
- **Exam questions** are shown as A to D cards after the slides. The question and options are spoken. The student
  answers by clicking, typing, or saying a letter ("b", "option b") or the option's words. The answer is marked
  with `/api/answer`, the feedback is spoken, and the next question follows. Free-text items the marker cannot
  judge are shown with a guess but not recorded.
- **Completion** speaks a closing line, then shows the summary box and progress.
- **Stop** pauses at the current step. **Next** skips to the next slide. **Read** starts the current slide again.
  Any spoken or typed question pauses the lesson.

## Evidence
Each check-in and exam answer writes:
- a **transcript** line for the student and one for the tutor (raw, for review; kept 90 days, then pruned at finish);
- one **evidence** row (objective, kind, correct, verdict, source, misconception, note). A repeated event with the same
  key writes nothing new.

The misconception on an evidence row is recorded only when the marker names one of the plan's listed beliefs by number.
The marker never writes free text into the record.

At finish, `outcomes.build()` makes the lesson's outcome: demonstrated, developing, weak, not assessed, misconceptions,
assessment, homework and focus. The next lesson's plan prompt reads the last outcome. The planner puts weak objectives
first, then objectives with a misconception from last time, then the rest.

## Course lessons
`packs/security-plus-sy0-701/lessons/` holds 17 Security+ lessons written as plans. Each lesson has two files:
- `NN-name.plan.json`: the plan (the shape above, plus `objectives` and a `source_review` listing facts added beyond
  the notes and every change to the pack's exam questions). This is the file to edit.
- `NN-name.md`: rendered from the plan by `import-pack`, with `<!-- pack-lesson: N -->` on line 2. Never edit by hand;
  a test fails if it drifts from its plan.

The notes came from PDF extraction (merged table columns, lost exam tips), so each lesson was rewritten as a plan and
checked by `lesson_plan.problem()`, the same check the nightly writer's plans pass. The pack's exam questions are kept
(a few reworded, all logged); `import-pack` spreads the right answers evenly over A to D.

**The queue.** On each study day from the start date, the scheduler installs the lowest-numbered course lesson not used
yet. A lesson given on a day marked missed counts as unused, so it comes back. No model is called. When all 17 are used,
the nightly writer writes the rest. The lesson generator switch (`lessons-on`/`lessons-off`) still applies.
- Start date: `lessons_from` in `pack.yaml` (an example; change it). Override with the `pack_lessons_from` setting
  (`""` turns course lessons off).
- See the schedule: `docker compose exec api python3 -m tutor course-lessons`. Rest days and the exam date decide how
  many course lessons fit.

**Editing a lesson.** Edit the `.plan.json`, then from the repo (not the container: `packs/` is mounted read-only there):
`cd apps/api && TUTOR_PACKS_DIR=../../packs PYTHONPATH=. python3 -m tutor import-pack --plans ../../packs/security-plus-sy0-701/lessons`.
It checks every plan first and writes nothing if one fails. Run the tests and commit both files.

**Importing a new source pack.** `tutor.importer.read_pack(path)` parses a pack zip or folder (manifest, notes,
check-ins, exam questions with keys) into structured lessons to write plans from. It reads only the files the
manifest names, in memory, size-limited.

## The practice lesson
A complete, hand-written lesson for testing the classroom, voice and quiz without real lessons:
`packs/security-plus-sy0-701/sample-lesson.md` (incident response and indicators of compromise, objectives 4.8 and 2.4).

```powershell
docker compose exec api python3 -m tutor sample-lesson
docker compose exec api python3 -m tutor sample-lesson --date 2026-10-08
```

Open the tutor, pick that date, press **Start**. It is **practice only**: answers and check-ins are not recorded as
progress, are not used to plan the next lesson, and are not written to Obsidian. It never gets reminders or "missed".
It won't overwrite a real lesson unless you add `--force`.

## Pausing real lessons
Set the **Trip pause** dates in admin, or set **Pause the tutor**. The practice lesson still works while paused.
