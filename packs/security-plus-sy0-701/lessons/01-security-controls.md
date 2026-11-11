<!-- objectives: 1.1 -->
<!-- pack-lesson: 1 -->
# Security Controls

## Retrieval (5 min)

### Retrieval
Quick check on earlier material.

```say
? From what you have seen at work or at home, what kinds of things do organisations use to protect their systems and buildings?
expect: Any sensible mix, for example passwords, firewalls, locks, guards, policies or cameras.
? What do the three letters in the CIA triad stand for?
expect: Confidentiality, integrity and availability.
```

## Intro (5 min)

### What a security control is
- A security control is any safeguard or countermeasure
- It protects the confidentiality, integrity and availability of systems and data
- Every control has a category and a type
Example: A locked server room door protects the hardware inside, so it counts as a control

```say
Today is about the language CompTIA uses to describe defences. Most questions on this objective hand you a control and ask you to name it, so we want those names to come out quickly and accurately.
There are two questions you can ask of any control. Who or what enforces it? That gives you the category. What job does it do? That gives you the type. Keep those two questions apart and most of the traps fall away.
? In your own words, what is the difference between asking who enforces a control and asking what it does?
expect: Who enforces it gives the category, such as technical or physical; what it does gives the type, such as preventive or detective.
```

## Teaching (15 min)

### The four categories
- Technical: a machine or system enforces it
- Managerial: a document says it must happen
- Operational: a person carries it out
- Physical: you can touch it
Example: Technical: firewall, encryption, multi-factor authentication. Managerial: policies, risk assessments
Example: Operational: delivering training, security guards. Physical: locks, fences, CCTV, bollards
Common mix-up: A camera records digitally, so it must be a technical control. For this exam, cameras and closed-circuit television count as physical controls, because they are equipment on site that you can touch.

```say
The category is really about where the control lives. If software or hardware applies it automatically, with nobody needing to remember, it is technical. If it exists as a written rule or a decision recorded on paper, it is managerial.
If a human being has to actually do something, like a guard walking the floor, it is operational. And if you could walk up and knock on it, a fence or a bollard, it is physical.
A classic trap pairs a written rule with the act of carrying it out. The paperwork sits in one category and the people doing the work sit in another, so always ask which of the two you are looking at.
Here is a common mistake. A camera records digitally, so it must be a technical control. That is not right. For this exam, cameras and closed-circuit television count as physical controls, because they are equipment on site that you can touch.
? A rule in the staff handbook says laptops must be encrypted, and software on each laptop then encrypts the disk. Which category is the handbook rule, and which is the disk encryption?
expect: The handbook rule is managerial; the encryption software is technical.
```

### Types that act before an attack
- Deterrent: discourages the attacker psychologically
- Preventive: actually stops the attack
- Directive: tells people what to do
- All three do their work before an attack succeeds
Example: Deterrent: warning signs, visible cameras
Example: Preventive: firewall, locked doors. Directive: acceptable use policy, signage, procedures
Common mix-up: A warning sign keeps intruders out, so it is a preventive control. A sign only discourages or instructs; nothing about it blocks a determined person, so it is deterrent or directive rather than preventive.

```say
Now the types, starting with the ones that work before anything has gone wrong. A deterrent works on the attacker's mind. It makes them think twice, but it cannot stop someone who is determined.
A preventive control genuinely blocks the attempt. Your notes say it physically stops it, but read that as really stops it: a firewall rule is just as preventive as a locked door.
Directive controls guide behaviour by telling people what is expected, such as an acceptable use policy or a sign saying staff only. They rely on people choosing to follow them.
Here is a common mistake. A warning sign keeps intruders out, so it is a preventive control. That is not right. A sign only discourages or instructs; nothing about it blocks a determined person, so it is deterrent or directive rather than preventive.
? Why is a locked door preventive, while a sign saying keep out is not?
expect: The lock physically blocks entry; the sign only discourages or instructs and cannot stop anyone.
```

### Types that act during and after
- Detective: identifies an attack as it happens
- Corrective: fixes the damage afterwards
- Compensating: fills a gap when the ideal control is not possible, often temporarily
Example: Detective: intrusion detection alerts, logs, CCTV footage. Corrective: restore a backup, reimage a machine
Example: Compensating: an old system with no fix available is put on its own network segment and watched closely
Common mix-up: Compensating means the same as corrective, because both deal with problems. Corrective repairs damage after an incident, while compensating covers a gap where the ideal control cannot be used.

```say
Detective controls tell you an attack is happening or has happened: an alert from an intrusion detection system, an entry in a log, or footage you can play back.
Corrective controls put things right, such as restoring from a clean backup or wiping and rebuilding a machine. Spotting a problem and fixing it are separate jobs, and the exam keeps them apart.
Compensating controls are the stand-ins. When the proper protection cannot be put in place, you add something else to bring the risk down until the real fix is possible.
Here is a common mistake. Compensating means the same as corrective, because both deal with problems. That is not right. Corrective repairs damage after an incident, while compensating covers a gap where the ideal control cannot be used.
? Backups are restored after malware wipes a server. Which type of control is the restore, and why is it not detective?
expect: Corrective, because it fixes the damage; detective controls only identify that something happened.
```

### One control, several labels
- One control can have more than one type
- Give the category and the type together
- Label each control by asking both questions
Example: Bank vault lock: preventive and physical. Vault camera: detective, deterrent and physical
Example: Vault guard: operational and detective. The 'no unauthorised entry' sign: directive and deterrent

```say
Real controls rarely do just one thing. Picture a bank vault. The lock on the door blocks entry and you can touch it, so it earns a type and a category at the same time.
The camera is the interesting one. Its footage lets you spot what went on, which is a detective job, but simply being seen also puts people off, which is the deterrent job as well.
So when a question asks which types apply, be ready to pick more than one, and do not let the first obvious label stop you looking for a second.
? A guard walks round the car park at night and reports anything odd. Give a category and a type for that guard.
expect: Operational, because a person carries it out; detective, because the guard spots and reports activity. Deterrent is also fair as a second type.
```

## Guided practice (10 min)

### Classify the controls
- Ask who or what enforces it, for the category
- Ask what job it does, for the type
- Expect more than one type for some controls
Example: Disk encryption on every laptop: technical and preventive

```say
Let us put both questions to work, first on a single control and then on a whole office. Name the category first, then the type, and give a reason for each one.
? Software that locks an account after five wrong passwords. What category and type would you give it, and why?
expect: Technical, because the system enforces it automatically; preventive, because it blocks further guessing.
```

### Scenario: Classify the controls
A small firm writes a rule that visitors must sign in. Reception staff check each visitor's ID at the desk. A fence surrounds the car park, and the network firewall blocks unknown traffic. After a break-in, the IT team rebuilds a damaged laptop from a clean image.

```say
Look at the scenario on the screen.
? Pick any three of those controls and give each one a category and a type, with a reason.
expect: Sign-in rule: managerial, directive. Reception checking ID: operational, preventive or detective. Fence: physical, preventive or deterrent. Firewall: technical, preventive. Rebuilding the laptop: corrective.
```

## Review (5 min)

### Key distinctions and traps
- Tech Managers Operate Physically: Technical, Managerial, Operational, Physical
- Category is who enforces it; type is what it does
- Deterrent discourages; preventive actually blocks
- Detective finds it; corrective fixes it
- Compensating stands in when the ideal control is impossible
Example: The rule requiring something is managerial; the person doing it is operational

```say
Keep the memory trick handy: tech managers operate physically. It gives you the four categories, and if you can recite it you will never forget one under exam pressure.
The traps are pairs that sound alike. Putting someone off is not the same as stopping them, and spotting a problem is not the same as fixing it. Read every option against the job the control really does.
? Recite the four control categories using the memory trick, and give one example of each.
expect: Technical such as a firewall, managerial such as a policy, operational such as a guard, physical such as a fence.
```

```quiz
[
 {
  "objective": "1.1",
  "type": "multiple_choice",
  "q": "A company policy requires annual security training. Which control category is this?",
  "options": [
   "Managerial",
   "Technical",
   "Operational",
   "Physical"
  ],
  "answer": "Managerial",
  "why": "The policy is a written requirement, which makes it managerial. Actually running the training sessions would be operational.",
  "source": "exam"
 },
 {
  "objective": "1.1",
  "type": "multiple_choice",
  "q": "A visible security camera both discourages an intruder and records activity. Which control types apply?",
  "options": [
   "Preventive only",
   "Deterrent and detective",
   "Corrective and directive",
   "Compensating only"
  ],
  "answer": "Deterrent and detective",
  "why": "Being seen puts intruders off, which is deterrent, and recording what happens is detective. A camera does not block anyone, so it is not preventive.",
  "source": "exam"
 },
 {
  "objective": "1.1",
  "type": "multiple_choice",
  "q": "A legacy system cannot be patched. A team segments it and monitors it instead. What type of control is this?",
  "options": [
   "A directive control",
   "A corrective control",
   "A compensating control",
   "A preventive control"
  ],
  "answer": "A compensating control",
  "why": "Segmenting and monitoring stand in for the patch that cannot be applied, filling the gap until a proper fix is possible.",
  "source": "exam"
 }
]
```
