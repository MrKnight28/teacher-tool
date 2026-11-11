<!-- objectives: 4.8,2.4 -->
<!-- sample: practice lesson, answers are not recorded as progress -->
# Sample lesson: Incident response and indicators of compromise

## Stage 1: Retrieval (5 min)

### Warm-up: what do you remember?
- What do the letters C, I and A stand for?
- Name one preventive control and one detective control.
- What is the difference between a threat and a vulnerability?

```say
Hi Kyle, good to see you. How are you doing today?
This is a practice lesson, so nothing you answer here counts towards your progress. Relax and use it to try everything out.
Before we start, a quick warm-up from earlier topics.
? Kyle, what do the letters C, I and A stand for?
expect: confidentiality, integrity and availability
Good. Keep those three in mind, because incident response is all about protecting them when something goes wrong.
```

## Stage 2: Introduction (5 min)

### Today's goal
- Put the incident response phases in the right order
- Spot common indicators of compromise in logs
- Exam focus: objectives 4.8 and 2.4

```say
Today we are looking at what happens after an attack has been spotted.
By the end you should be able to put the incident response phases in order, and pick out the clues in a log that something is wrong.
The exam loves scenario questions here, so we will practise reading a situation and choosing the next step.
```

## Stage 3: Teaching (15 min)

### The incident response lifecycle
Preparation → Detection and analysis → Containment → Eradication → Recovery → Lessons learned

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 200">
  <rect x="0" y="0" width="640" height="200" fill="#ffffff"/>
  <rect x="10" y="70" width="90" height="50" rx="8" fill="#e8f0fe" stroke="#2b59c3"/>
  <text x="55" y="100" font-size="13" text-anchor="middle">Prepare</text>
  <rect x="115" y="70" width="90" height="50" rx="8" fill="#e8f0fe" stroke="#2b59c3"/>
  <text x="160" y="100" font-size="13" text-anchor="middle">Detect</text>
  <rect x="220" y="70" width="90" height="50" rx="8" fill="#fde8e8" stroke="#b3261e"/>
  <text x="265" y="100" font-size="13" text-anchor="middle">Contain</text>
  <rect x="325" y="70" width="90" height="50" rx="8" fill="#fde8e8" stroke="#b3261e"/>
  <text x="370" y="100" font-size="13" text-anchor="middle">Eradicate</text>
  <rect x="430" y="70" width="90" height="50" rx="8" fill="#e6f4ea" stroke="#117a3d"/>
  <text x="475" y="100" font-size="13" text-anchor="middle">Recover</text>
  <rect x="535" y="70" width="95" height="50" rx="8" fill="#fff4e0" stroke="#b06000"/>
  <text x="582" y="100" font-size="13" text-anchor="middle">Lessons</text>
  <text x="320" y="170" font-size="13" text-anchor="middle">Lessons learned feeds back into preparation</text>
</svg>
```

```say
Think of incident response like a fire drill for computers.
First you prepare: you have the plan, the contacts and the tools ready before anything happens.
Then you detect and analyse: an alert fires, and you work out whether it is real and how bad it is.
Next comes containment, which stops it spreading. After that, eradication removes the cause, recovery puts systems back, and lessons learned improves the plan for next time.
? Kyle, which phase stops the damage spreading, before you remove the cause?
expect: containment
```

### Containment comes before eradication
- Containment stops the spread: isolate the host, block the IP address, disable the account
- Eradication removes the cause: delete the malware, close the hole, reset credentials
- Preserve evidence before you change anything

```say
A common exam trap is mixing up containment and eradication.
Containment is like closing the fire doors. The fire is still there, but it cannot reach the next room.
Eradication is putting the fire out properly, so it cannot start again.
And before you wipe anything, take a copy for evidence. Once it is wiped, it is gone for good.
```

### Indicators of compromise
- Many failed logins, then one success
- Logins at impossible times or from impossible places
- Unexpected outbound traffic to unknown domains
- Accounts locked out, or new admin accounts nobody created

```say
Indicators of compromise are the clues that something bad has already happened.
In the exam, a scenario usually hides one clue that points to the answer.
For example, four hundred failed logins across four hundred different accounts from one address is password spraying, not brute force.
? Kyle, in your own words, what is an indicator of compromise?
expect: evidence or a sign that a system has been attacked or breached
```

## Stage 4: Guided practice (10 min)

### Scenario: the 3 a.m. alert
An alert shows PowerShell on a finance laptop downloading a file at 03:12 from a domain registered yesterday. The user is asleep.

```say
Let's work through this one together.
A laptop in finance downloads a file in the middle of the night, from a domain that only appeared yesterday, while its user is asleep.
That pattern of an odd time, a new domain and a scripting tool is a strong indicator of compromise.
? Kyle, what should the first response step be here?
expect: contain it, for example isolate the laptop from the network, while keeping evidence
```

## Stage 5: Independent practice (15 min)

### Your turn
1. A user reports their mouse moving on its own. Which phase are you in?
2. Malware is removed and systems are restored from clean backups. Which phases were those?
3. Name two indicators that would make you suspect an insider rather than an outside attacker.

```say
Now have a go on your own. Write your answers in the notebook on the right.
Take your time. If you get stuck, hold the mic and ask me.
```

## Stage 6: Questions (5 min)

### Anything unclear?
- Ask about anything from today
- Flag tricky points in your notebook for review

```say
That's the main teaching done. What felt unclear?
? Kyle, which part of today would you like me to explain again?
expect: any honest answer; the student names a topic they found hard
```

## Stage 7: Review (5 min)

### Key takeaways
- Order: prepare, detect, contain, eradicate, recover, lessons learned
- Contain before you eradicate, and keep the evidence
- Read scenarios for the one clue that points to the answer

```say
Well done, Kyle. Let's wrap up with the three things to remember.
The order of the phases. Containment before eradication. And always look for the one clue in a scenario.
When you're ready, press Finish to try the quiz.
```

```quiz
[
 {"objective": "4.8", "type": "multiple_choice", "q": "A SOC analyst confirms ransomware on one workstation. Which incident response step should come next?", "options": ["Eradication", "Containment", "Recovery", "Lessons learned"], "answer": "Containment", "why": "Isolate the host first so the infection can't spread, then eradicate."},
 {"objective": "4.8", "type": "free_text", "q": "Why should you take a forensic image before wiping an infected machine?", "options": [], "answer": "to preserve evidence for the investigation", "why": "Wiping destroys the evidence needed to understand the attack."},
 {"objective": "4.8", "type": "multiple_choice", "q": "Which phase updates the incident response plan after an incident?", "options": ["Preparation", "Detection", "Lessons learned", "Recovery"], "answer": "Lessons learned", "why": "Lessons learned reviews what happened and improves the plan."},
 {"objective": "2.4", "type": "acronym_recall", "q": "What does IoC stand for?", "options": [], "answer": "Indicator of Compromise", "why": "An IoC is evidence that a system has been breached."},
 {"objective": "2.4", "type": "pbq_scenario", "q": "Logs show 400 failed logins across 400 different accounts from one IP address in 5 minutes. Which attack is this?", "options": ["Brute force", "Password spraying", "Credential stuffing", "Pass the hash"], "answer": "Password spraying", "why": "One password tried across many accounts avoids lockouts."},
 {"objective": "2.4", "type": "multiple_choice", "q": "Which is the strongest sign of account compromise?", "options": ["A password change after a reminder", "A login from two countries within ten minutes", "A user logging in at 9 a.m.", "A locked screen"], "answer": "A login from two countries within ten minutes", "why": "Impossible travel is a classic indicator of a compromised account."}
]
```
