<!-- objectives: 1.3 -->
<!-- pack-lesson: 3 -->
# Change Management

## Retrieval (5 min)

### Retrieval
Quick check on earlier material.

```say
? Think of a software update that went wrong on a phone or computer you have used. What would have made it easier to recover?
expect: A way to roll back or undo the update, a backup, or testing before release.
? Why do organisations usually schedule big IT work for nights or weekends?
expect: Fewer users are affected if something goes wrong or a restart is needed.
```

## Intro (5 min)

### Why change management matters
- Change management: formal control over every update to IT systems
- Core rule: uncontrolled change means uncontrolled risk
- The exam tests the process order, the change types and the paperwork
Example: A firewall rule edited on a Friday afternoon with no record, and nobody knows why the website broke on Monday

```say
Many security incidents are not caused by attackers at all. They come from someone making a well meant tweak to a live system without telling anyone, and something quietly breaks or a hole opens up.
Today is about the discipline that stops that happening. On the exam you will need the steps in order, the different kinds of change, and the key terms, so we will take each in turn.
? Why could an unrecorded tweak to a live server be a security problem, even if it was made with good intentions?
expect: Nobody else knows about it, so it can break things, open a weakness or move the system away from its secure baseline without anyone noticing.
```

## Teaching (15 min)

### The Change Advisory Board
- CAB: Change Advisory Board
- A cross-department group that reviews and signs off changes
- Nobody approves their own
Example: A database upgrade is looked at by IT, security, finance and the business owner before anyone touches it
Common mix-up: A senior administrator can sign off their own work because they know the system best. No one can sign off their own request; the board gives an independent check no matter how senior the requester is.

```say
The Change Advisory Board is a group drawn from different parts of the organisation. Having several departments in the room means someone will spot the knock-on effect that the person asking for the work never thought about.
The golden rule is separation. The person who wants something done can never be the one who gives it the go-ahead, however senior or experienced they are.
Here is a common mistake. A senior administrator can sign off their own work because they know the system best. That is not right. No one can sign off their own request; the board gives an independent check no matter how senior the requester is.
? Why does it matter that the board includes people from several departments, not just IT?
expect: Different departments spot different impacts and dependencies, so the review is wider and more independent.
```

### The process, in order
- Request, then review and impact analysis
- Test in a non-production environment
- Approve: the CAB signs off with the evidence
- Implement in the maintenance window
- Verify with a post-change review, then document
Example: A patch is requested, reviewed for impact, tried on a test server, signed off, rolled out at 2am on Sunday, checked on Monday, and recorded

```say
Learn the usual flow as a story. Someone asks, the change is reviewed and its impact weighed up, it is tried somewhere safe, the board says yes, it goes live in a quiet period, it is checked, and finally it is written up.
Organisations vary the details, so treat this as the typical shape rather than a law. The key idea is that testing comes before approval, so the board signs off with real evidence in front of it.
Notice there are two reviews. The first happens before any work, to weigh up the impact and decide whether it should go ahead. The second happens afterwards, to verify it worked and caused no side effects.
Planned surgery has a similar shape. The operation is requested, assessed, tests are run, consent and sign-off follow, the surgeon operates, there is a post-operative check, and it goes into the patient notes. It breaks down because a surgeon cannot rehearse on a copy of the patient, whereas in IT you can and should test the change itself first.
? Why does testing usually come before the board gives its approval?
expect: So the board approves with evidence from the test results that the change works and what it affects, rather than approving blind.
? What is the difference between the review before the work and the review after it?
expect: The first weighs up impact and decides whether the work should go ahead; the second verifies that it worked and caused no problems.
```

### Three types of change
- Standard: pre-approved, low risk, routine, with no individual CAB review
- Emergency: urgent, skips the normal timeline, still documented retrospectively
- Unauthorised: made without approval, always a failure whatever the intent
Example: Standard: the monthly patch run
Example: Emergency: a zero-day fix pushed out tonight, written up tomorrow
Common mix-up: Emergency changes are just unauthorised changes that happened to be urgent. Emergency changes still have approval through a faster route and are documented afterwards, while unauthorised ones have no approval at all.

```say
Not every change goes through the full board. Routine, low risk work that happens the same way every time is signed off once in advance, so it does not clog up the meeting.
When something is genuinely urgent, the timeline is shortened, but the paperwork is not skipped. It is completed after the event, so there is still a full record.
The unauthorised kind is the one the exam loves. Even if the engineer was trying to help, and even if it worked, doing it without approval is a failure of the process.
Here is a common mistake. Emergency changes are just unauthorised changes that happened to be urgent. That is not right. Emergency changes still have approval through a faster route and are documented afterwards, while unauthorised ones have no approval at all.
? An engineer notices a misconfiguration at midnight and fixes it on the spot without telling anyone. The fix works. How should this be classed?
expect: As unauthorised, and therefore a failure, because it had no approval, even though it worked.
```

### The three buckets
- Business processes: approval, ownership, stakeholders, impact analysis, test results, backout plan, maintenance window
- Technical implications: allow and deny lists, downtime, service and application restarts, legacy applications
- Documentation: update diagrams, policies and procedures, version control
Example: Moving a web server to a new address means updating the firewall allow list, the network diagram and the build procedure

```say
The objective groups everything into three buckets. The business side is about people and decisions: who owns the work, who is affected, what could go wrong, and when it is allowed to happen.
The technical side is about what the work touches. Will a service need restarting, will there be downtime, will an old application cope, and does a firewall list need editing?
The documentation side keeps records true. If the diagrams and procedures are not updated, the next person works from a picture of a network that no longer exists.
? A planned upgrade will need the payroll service restarted. Which of the three buckets is that, and why?
expect: Technical implications, because it is about what the work touches on the systems themselves.
```

### Key terms
- Backout plan: documented steps to reverse the work if it fails, required before approval
- Maintenance window: a scheduled low-impact period, such as Sunday 2 to 5am
- Impact analysis: what could break, who is affected, security implications, dependencies
- Configuration drift: systems slowly moving away from the secure baseline through untracked edits
- Version control and SOPs: full history of who changed what, and step-by-step procedures
Example: Git shows exactly which line of a config file was edited, when, and by whom
Example: An SOP for adding a user gives the same result whoever follows it
Common mix-up: You only need to think about undoing an update once it has gone wrong. The rollback steps are written and checked before sign-off, so they are ready the moment something fails.

```say
The backout plan is your way home. Before the board will say yes, you need written steps to undo the work if it goes wrong, because hoping it works is not a plan.
Configuration drift is what happens without all this. Lots of small unrecorded edits slowly pull a system away from its secure baseline, until nobody is sure what state it is in.
Version control and a standard operating procedure solve opposite problems. One keeps a complete history of every edit. The other makes sure a task is done the same way, with the same result, whoever carries it out.
Here is a common mistake. You only need to think about undoing an update once it has gone wrong. That is not right. The rollback steps are written and checked before sign-off, so they are ready the moment something fails.
? Over a year, small undocumented tweaks leave two identical servers configured differently. What is this called?
expect: Configuration drift.
```

## Guided practice (10 min)

### Run the process
- Put the steps in order
- Decide which type of change it is
- List what each bucket needs
Example: Weekly antivirus signature update: standard, already signed off

```say
In a moment you will plan a real piece of work from start to finish. As a warm-up, think about how routine work differs from a one-off.
? Why is a weekly signature update treated as standard rather than going to the board each time?
expect: Because it is routine and low risk and done the same way every time, so it is pre-approved.
```

### Scenario: Run the process
A retailer wants to replace the software on its card payment servers before Christmas. The new version needs the payment service restarted and a new port opened on the firewall. The servers also run an old stock application that nobody is sure will work with the update.

```say
Look at the scenario on the screen.
? Walk through the steps this work should follow, say which type it is, and name two things from the technical bucket and one thing that must be ready before the board signs off.
expect: Request, review and impact analysis, test in non-production, approval by the board, implement in a maintenance window, verify with a post-change review, document. It is a normal change, not standard. Technical items: service restart, firewall allow list, legacy application, downtime. Before sign-off: a backout plan, plus impact analysis and test results.
```

## Review (5 min)

### Key distinctions and traps
- Request, review, test, approve, implement, verify, document
- Standard is pre-approved; emergency is fast but recorded; unauthorised always fails
- No backout plan, no sign-off
- Nobody approves their own
Example: Surgery order: request, assessment, tests, sign-off, operate, post-op check, notes

```say
Keep the surgery picture in mind for the usual order: request, assessment, tests, sign-off, the operation, the check-up, then the notes. It fits the steps well, with one difference: in IT you can rehearse the change itself on a copy first.
The traps are about the types. Urgent work is not the same as unapproved work, good intentions never rescue an unapproved one, and routine work is approved once in advance rather than skipped.
? Recite the usual seven steps of the process in order.
expect: Request, review and impact analysis, test, approve, implement, verify, document.
```

```quiz
[
 {
  "objective": "1.3",
  "type": "multiple_choice",
  "q": "Which statement about an emergency change is correct?",
  "options": [
   "It is automatically unauthorised",
   "It bypasses all documentation",
   "It uses an expedited process and is documented retrospectively",
   "It never needs a backout plan"
  ],
  "answer": "It uses an expedited process and is documented retrospectively",
  "why": "Emergency changes go through a faster approval route and are written up after the event, so they are neither unauthorised nor undocumented.",
  "source": "exam"
 },
 {
  "objective": "1.3",
  "type": "multiple_choice",
  "q": "Who reviews and approves normal changes in the change process?",
  "options": [
   "The person implementing the change alone",
   "The end user",
   "The backup operator",
   "The CAB"
  ],
  "answer": "The CAB",
  "why": "The Change Advisory Board reviews and approves changes, and nobody approves their own work.",
  "source": "exam"
 },
 {
  "objective": "1.3",
  "type": "multiple_choice",
  "q": "What must every approved change have?",
  "options": [
   "A backout plan",
   "A public announcement",
   "A new vendor",
   "A penetration test"
  ],
  "answer": "A backout plan",
  "why": "A backout plan, the documented steps to reverse the change if it fails, is required before approval.",
  "source": "exam"
 }
]
```
