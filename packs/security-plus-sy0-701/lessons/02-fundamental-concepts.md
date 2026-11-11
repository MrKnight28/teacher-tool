<!-- objectives: 1.2 -->
<!-- pack-lesson: 2 -->
# Fundamental Concepts

## Retrieval (5 min)

### Retrieval
Quick check on earlier material.

```say
? When you log in to a website with a password, what is the site actually trying to find out?
expect: That you are who you claim to be: your identity.
? Why might a business use several layers of protection instead of relying on one really good firewall?
expect: Because any single defence can fail, so other layers still protect it.
```

## Intro (5 min)

### The building blocks of security
- The CIA triad and its opposite, DAD
- Non-repudiation and the AAA framework
- Zero Trust and its planes
- Deception, planning and design principles
Example: Almost every Security+ scenario can be traced back to one corner of the CIA triad

```say
Today covers the vocabulary that the rest of Security+ is built on. These ideas turn up everywhere in the exam, often hidden inside a longer scenario, so you need to spot them instantly.
We will start with what security is trying to protect, then how systems decide who gets in, then the Zero Trust model, and finish with a handful of short concepts that are easy marks if you know the exact wording.
? Before we start, why do you think an exam would care so much about a shared vocabulary for security?
expect: So that everyone describes threats and defences the same way, and questions can test precise ideas rather than vague ones.
```

## Teaching (15 min)

### The CIA triad and DAD
- Confidentiality: only authorised eyes
- Integrity: not tampered with
- Availability: accessible when needed
- DAD is the evil twin: Disclosure, Alteration, Destruction
- Non-repudiation: irrefutable proof of who did something, via digital signatures
Example: Disclosure attacks confidentiality; alteration attacks integrity; destruction attacks availability
Example: A signed email means the sender cannot later claim they never sent it
Common mix-up: If an attacker changes a record but nobody outside sees it, no harm is done to security. Unauthorised change is an attack on integrity, even when nothing is disclosed.

```say
The CIA triad is the three things security protects, and every attack goes after at least one of them. Confidentiality is about who can see the information. Integrity is about whether it can be trusted to be unchanged. Availability is about whether people can reach it when they need it.
The handy twist is the evil twin, DAD. Each attacker goal lines up with one pillar: leaking information breaks confidentiality, changing it breaks integrity, and wiping it out or knocking it offline breaks availability.
Non-repudiation sits alongside the triad. It means someone cannot deny an action they took, and the tool that gives you that proof is a digital signature.
Here is a common mistake. If an attacker changes a record but nobody outside sees it, no harm is done to security. That is not right. Unauthorised change is an attack on integrity, even when nothing is disclosed.
? An attacker quietly changes the prices in an online shop's database. Which pillar of the triad is hit, and which letter of DAD describes it?
expect: Integrity, through alteration.
? What does non-repudiation stop a person from doing, and what technology provides it?
expect: It stops them denying they performed an action; digital signatures provide it.
```

### The AAA framework
- Authentication: prove WHO you are
- Authorisation: what you CAN access
- Accounting: log what you DID
- Always in this order
Example: Hotel: show ID at the desk (AuthN), the key opens only your room (AuthZ), every door swipe is logged (accounting)
Common mix-up: Logging in with a password also decides which files I can open. The password only proves identity; deciding what you may open is a separate step called authorisation.

```say
The AAA framework describes how a system handles anyone who wants to use it, and the order matters. First you prove your identity, then the system works out what you are allowed to touch, and finally it keeps a trail of what you actually did.
The two that get muddled are authentication and authorisation, because they sound alike. One is about identity, the other is about permissions, and you cannot be given permissions until your identity has been proven.
Checking into a hotel follows the same order. You show your identification at the desk, your key card opens your room and no other, and the hotel keeps a log of every swipe. Where it breaks down is that a hotel checks your identity once, while a well run network keeps checking every time you ask for something.
Here is a common mistake. Logging in with a password also decides which files I can open. That is not right. The password only proves identity; deciding what you may open is a separate step called authorisation.
? A user enters a correct password but is refused access to the finance share. Which step of the framework refused them?
expect: Authorisation, because authentication succeeded but they lack permission.
```

### Zero Trust
- Zero Trust: never trust, always verify
- Control plane: makes and communicates decisions
- PE, the Policy Engine, is the judge: it makes the call
- PA, the Policy Administrator, is the clerk: it passes the call on
- Data plane: PEP, the Policy Enforcement Point, is the bouncer that allows or blocks
Example: A laptop asks for the payroll app: the PE decides yes, the PA tells the gateway, and the PEP lets the traffic through
Common mix-up: In Zero Trust, the policy administrator is the part that makes the access decision. The policy engine makes the decision; the policy administrator only communicates it to the policy enforcement point.

```say
Zero Trust throws away the old idea that anything inside the company network is safe. Every request is checked, every time, no matter where it comes from.
To do that, the model splits the work into two layers. The control plane is the thinking side, where a verdict is reached and handed on. The policy engine is the judge who reaches it, and the policy administrator is the clerk who passes it along.
The other layer is where traffic actually flows. Here the policy enforcement point stands at the door like a bouncer, letting the request through or turning it away based on what the judge decided.
Here is a common mistake. In Zero Trust, the policy administrator is the part that makes the access decision. That is not right. The policy engine makes the decision; the policy administrator only communicates it to the policy enforcement point.
? Using the judge, clerk and bouncer picture, explain the role of the policy engine and the policy administrator.
expect: The policy engine is the judge that makes the decision; the policy administrator is the clerk that communicates it to the policy enforcement point.
```

### Deception technology
- Honeypot: a fake system that attracts attackers
- Honeynet: a whole network of fakes
- Honeytoken or honeyfile: a fake credential or file
- Nobody legitimate should ever touch them, so any access raises an alert
Example: A file called passwords.xlsx that no real staff member uses; opening it triggers an alert to the security team

```say
Deception turns the attacker's curiosity against them. You plant something that looks valuable but has no real purpose, so the only people who go near it are the ones who should not be there.
The difference is size. A honeypot is one decoy machine and a honeynet is a network of them, while a honeytoken or honeyfile is a single fake password, account or document hidden among real ones.
? Why is a single login with a honeytoken credential treated as a serious alert, rather than just noise?
expect: Because no legitimate user should ever use it, so any use means someone is snooping or an attacker has stolen data.
```

### Planning and design principles
- Gap analysis: current state against desired state, giving a list of missing controls
- Data sovereignty: data follows the laws of the country where it physically resides
- Least privilege: the minimum access needed for the job, nothing more
- Defence in depth: multiple overlapping layers, so if one fails others remain
Example: Customer records stored on servers in Germany fall under German and European law, wherever the company is based
Example: Firewall, then endpoint protection, then encryption: an attacker must beat all three
Common mix-up: A British company's data is always covered only by British law. Data is subject to the laws of the country where it is physically stored, so data on servers abroad falls under that country's rules.

```say
These four are short definitions that the exam tests by their exact meaning. Gap analysis compares where you are with where you want to be, and what comes out is a list of the controls you are missing.
Data sovereignty is about geography. What matters is the physical location of the servers, not where the company has its head office.
Least privilege and defence in depth both limit damage. One gives each person only the access their job needs, the other stacks several protections so that a single failure does not open everything.
Here is a common mistake. A British company's data is always covered only by British law. That is not right. Data is subject to the laws of the country where it is physically stored, so data on servers abroad falls under that country's rules.
? A new starter in marketing is given full administrator rights so they can install software. Which principle does that break?
expect: Least privilege, because they have far more access than their job needs.
```

## Guided practice (10 min)

### Spot the concept
- Match each event to a pillar and a DAD letter
- Name the AAA step that is working
- Look for the principle being used
Example: Backups deleted by an attacker: availability, destruction

```say
In a moment you will see a scenario where several of today's ideas appear at once. As a warm-up, pair up the attacker goals with what they damage.
? Which pillar of the triad does each letter of DAD attack?
expect: Disclosure attacks confidentiality, alteration attacks integrity, destruction attacks availability.
```

### Scenario: Spot the concept
A hospital checks staff identity with a smart card, then lets nurses open patient notes but not payroll. Every record viewed is logged. An attacker who got in planted fake patient details and also leaked real notes online. The security team spotted the attacker after they opened a decoy file called admin-passwords.

```say
Look at the scenario on the screen.
? Name the AAA steps in the hospital's setup, the two pillars of the triad that the attacker hit, and the deception technique that caught them.
expect: Smart card is authentication, nurse permissions are authorisation, logging views is accounting. Fake details hit integrity through alteration, leaked notes hit confidentiality through disclosure. The decoy file is a honeyfile.
```

## Review (5 min)

### Key distinctions and traps
- CIA is what you protect; DAD is how it is attacked
- AAA order: authentication, authorisation, accounting
- PE judges, PA passes it on, PEP is the bouncer
- Honeytokens should never be touched: any access is an alert
Example: Show ID, open your own room, swipes logged: the three A's in order

```say
Three distinctions catch people out. Authentication is identity and authorisation is permission. The policy engine decides while the policy administrator only relays. And data sovereignty follows the server's location, not the head office.
If a question describes an attack, ask which pillar it damages. If it describes access, ask which of the three A's is doing the work. Most answers on this objective fall out of those two questions.
? Give the three parts of the AAA framework in the right order, with a few words on what each does.
expect: Authentication proves who you are, authorisation decides what you can access, accounting logs what you did.
```

```quiz
[
 {
  "objective": "1.2",
  "type": "multiple_choice",
  "q": "Ransomware encrypts a company’s files. Which CIA property is directly attacked?",
  "options": [
   "Confidentiality of the files",
   "Integrity of the files",
   "Non-repudiation of the files",
   "Availability of the files"
  ],
  "answer": "Availability of the files",
  "why": "Ransomware locks the owners out of their own data until a ransom is paid, so the property it directly attacks is availability.",
  "source": "exam"
 },
 {
  "objective": "1.2",
  "type": "multiple_choice",
  "q": "In AAA, which function records what a user did?",
  "options": [
   "Accounting",
   "Authentication",
   "Authorisation",
   "Attestation"
  ],
  "answer": "Accounting",
  "why": "Accounting keeps the log of what someone did once they were authenticated and authorised.",
  "source": "exam"
 },
 {
  "objective": "1.2",
  "type": "multiple_choice",
  "q": "In Zero Trust, which component is in the data plane and enforces the decision?",
  "options": [
   "PE",
   "PEP",
   "PA",
   "Risk register"
  ],
  "answer": "PEP",
  "why": "The Policy Enforcement Point sits in the data plane and allows or blocks the request. The Policy Engine and Policy Administrator are in the control plane.",
  "source": "exam"
 }
]
```
