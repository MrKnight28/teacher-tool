<!-- objectives: 5.1,5.3,5.4,5.5,5.6 -->
<!-- pack-lesson: 16 -->
# Governance and Compliance

## Retrieval (5 min)

### Retrieval
Quick check on earlier material.

```say
? Before we start, have you come across any data protection laws, and what do they make organisations do?
expect: For example GDPR, which makes organisations protect personal data and report breaches.
? What do you think a company policy is for?
expect: To set out rules everyone in the organisation must follow.
```

## Intro (5 min)

### Rules, contracts, audits and people
- Governance sets direction; compliance proves you meet outside rules
- Today: document hierarchy, laws and standards, supplier agreements, audits, awareness
- Heavy on vocabulary: the exam tests precise definitions
Example: A UK retailer that takes card payments and holds customer data answers to GDPR, PCI DSS and its own policies at once.

```say
This is the most business-flavoured part of the exam. Very little of it is technical, but the wording is precise, and the questions often hinge on a single word like mandatory, voluntary or certifiable.
We will go from the top, how an organisation decides its rules, out to suppliers and auditors, and finish with the people who have to follow it all.
? Why might an organisation that is fully compliant still be insecure?
expect: Compliance only meets the minimum outside requirements; real threats can go beyond what the rules cover.
```

## Teaching (15 min)

### Governance and the document hierarchy
- Governance: policies, processes and structures aligning security with business goals
- Compliance: meeting EXTERNAL laws, regulations and standards. The FLOOR, not the ceiling
- Policy: WHAT must be done. Mandatory
- Standard: the specific requirements. Mandatory. Procedure: step-by-step HOW. Mandatory
- Guideline: recommended. OPTIONAL
Example: Policy: all laptops are encrypted. Standard: AES-256 full-disk encryption. Procedure: the steps IT follow to enable it. Guideline: tips for choosing a strong recovery passphrase.
Common mix-up: A policy tells staff exactly which buttons to press. A policy states what must happen; the step-by-step how belongs in a procedure.

```say
Governance is about steering. Leadership decides what the organisation cares about and writes that down so security serves the business, not the other way round.
Read the documents from the top down. The policy states the intent, the standard pins down exactly what counts, and the procedure walks someone through doing it. Those three are all compulsory.
Only the last one gives you a choice. If a question asks which document is merely advice, it is the guideline.
Here is a common mistake. A policy tells staff exactly which buttons to press. That is not right. A policy states what must happen; the step-by-step how belongs in a procedure.
? Which document would contain step-by-step instructions for resetting a user's password?
expect: A procedure, because it describes how to do something step by step.
```

### Laws, standards and voluntary guidance
- NIST CSF: voluntary. Identify, Protect, Detect, Respond, Recover. CSF 2.0 adds a sixth function, Govern
- ISO 27001: international ISMS standard. Independently CERTIFIABLE
- GDPR: law. EU and UK personal data, 72-hour breach notification, fines up to 4% or €20m
- HIPAA: law. US health data, 60-day notification, covers business associates
- PCI DSS: industry standard, NOT a law. Contractually mandatory for card payments
Example: A London shop loses card data. PCI DSS applies through its card contracts, and GDPR applies because the data is personal.
Common mix-up: PCI DSS is a law, so the government fines you for breaking it. PCI DSS is an industry standard enforced through contracts with the card companies, not by legislation.

```say
Sort these into three buckets. Some are laws, where breaking them brings fines from a regulator. Some are voluntary guidance you choose to adopt. And one is a certifiable standard an outside body can audit you against.
The NIST framework started with five functions. Version two, published in 2024, added Govern as a sixth, sitting over the other five and setting direction and accountability.
The card industry standard trips people up. It is not legislation at all, yet it is still compulsory, because the card companies make it a condition of the contract.
For the General Data Protection Regulation, GDPR, remember seventy-two hours to tell the regulator. For HIPAA, the American health privacy law, remember sixty days.
Here is a common mistake. PCI DSS is a law, so the government fines you for breaking it. That is not right. PCI DSS is an industry standard enforced through contracts with the card companies, not by legislation.
? Which of these can a company be independently certified against: the NIST Cybersecurity Framework or ISO 27001?
expect: ISO 27001.
? A hospital in the United States suffers a data breach. Which law applies, and how long does it have to notify people?
expect: HIPAA, with sixty days to notify.
```

### Third parties: agreements, SOC 2 and the supply chain
- NDA: sign BEFORE sharing anything confidential. MOU: informal intent, usually not binding. MOA: more formal
- MSA: master contract for the whole relationship. SOW: one project's scope and deliverables
- SLA: service levels such as uptime and response times. ISA: network interconnection security. BPA: partnership responsibilities and liability
- SOC 2 Type 1: controls EXIST at one point in time. Type 2 (stronger): controls WORK over a period, typically 3 to 12 months
- SBOM: the software's ingredient list. Tier 1, 2, 3: your vendor, their vendor, deeper. Risk flows up the chain
Example: When Log4Shell broke, firms with an SBOM found every affected app in minutes.
Example: Vendor offboarding: revoke access, retrieve data, get a certificate of destruction.
Common mix-up: An MOU legally binds both organisations. An MOU records informal intent and is usually not binding; an MOA is the more formal commitment.

```say
The agreements form a ladder. A memorandum of understanding is a handshake on paper, a memorandum of agreement firms that up, and the master services agreement is the umbrella contract, with a statement of work for each individual job underneath it.
A service level agreement is all about measurable promises: how often the service is up and how fast they respond. An interconnection agreement covers the security of linking two networks.
Your suppliers have suppliers. A weakness three tiers down can still reach you, which is why a software bill of materials matters.
A Type 1 report is like a photo of a tidy kitchen, while Type 2 is the restaurant's inspection history over months. Where it breaks down: a Type 2 auditor does not watch every day, they test samples of evidence from across the period.
Here is a common mistake. An MOU legally binds both organisations. That is not right. An MOU records informal intent and is usually not binding; an MOA is the more formal commitment.
? Which agreement would set out the uptime and response times a cloud provider promises?
expect: A service level agreement.
? When ending a relationship with a supplier, what three things should happen to protect your data?
expect: Revoke their access, retrieve your data, and get a certificate of destruction.
```

### Audits and pen testing
- Black box (unknown environment): no knowledge, most realistic. Grey box (partially known): simulates an insider. White box (known): full knowledge, most thorough
- Vulnerability assessment FINDS weaknesses. A pen test FINDS and EXPLOITS them to prove impact
- Passive recon: OSINT, no contact, hard to detect. Active recon: scanning and probing, detectable
- Rules of engagement: signed authorisation in writing comes first, or it is illegal
- Internal audit must be INDEPENDENT of what it audits. Audits test samples, not everything
Example: A tester reads staff profiles on LinkedIn (passive), then runs a port scan against the mail server (active).
Common mix-up: A clean audit proves every control is working. Audits test samples rather than everything, so a problem can still be missed; that is a built-in limitation.

```say
The box colours describe how much the tester is told up front. Nothing at all is closest to a real outsider, everything lets them be the most thorough, and the middle option imitates someone with insider knowledge.
The current exam objectives use plainer names for the same three: unknown, partially known and known environment. Expect to see either set of words in a question, and match them up by how much the tester was told.
Finding a weakness and proving it can be exploited are two different jobs. Only the pen test goes the extra step.
Without permission on paper, a pen test is just an attack. And an auditor checking their own team's work is not independent, so the result means little.
Here is a common mistake. A clean audit proves every control is working. That is not right. Audits test samples rather than everything, so a problem can still be missed; that is a built-in limitation.
? A tester gathers information from public websites without ever touching the target's systems. Is that passive or active reconnaissance?
expect: Passive, because there is no contact with the target and it is hard to detect.
```

### Security awareness and culture
- Phishing simulations are TRAINING tools, never punitive. Follow up with education
- Report rate matters as much as click rate: you WANT reporters
- Role-based training: developers get secure coding, executives get whaling, finance gets BEC
- Blame-free culture: fear of punishment kills reporting, so incidents go unseen
- Culture starts at the top: if executives bypass controls, everyone will
Example: A finance clerk gets a fake urgent email from the chief executive asking for a payment. Training on business email compromise teaches them to verify by phone.
Common mix-up: Punishing staff who click on phishing simulations makes them more careful. Punishment makes people hide mistakes, so real incidents go unreported; simulations should lead to education instead.

```say
The point of a fake phishing email is to teach, not to catch people out. If someone clicks, the right response is a short lesson, not a telling-off.
Watch the people who report the email, not just the ones who click. A workforce that reports quickly is your early warning system.
Tailor the training to the job. A developer, a director and someone in accounts face very different attacks.
Here is a common mistake. Punishing staff who click on phishing simulations makes them more careful. That is not right. Punishment makes people hide mistakes, so real incidents go unreported; simulations should lead to education instead.
? Why does it matter if senior managers ignore security controls?
expect: Staff copy leadership, so if executives bypass controls everyone else will too.
```

## Guided practice (10 min)

### Advising a growing company
- Identify which documents are compulsory and which are advice
- Decide which outside rules apply
- Spot the culture problem and how to fix it
Example: Card payments plus personal data: think contract obligations and data protection law together.

```say
Treat this like a short consultancy job. Work through it in order: documents, outside rules, then people.
There is more than one problem in this scenario, so do not stop at the first one you spot.
? If the company wanted outside proof that its controls have actually worked over time, what kind of report would it ask an auditor for?
expect: A SOC 2 Type 2 report, which covers controls operating over a period.
```

### Scenario: Advising a growing company
A UK online shop takes card payments and stores customer addresses. Its only security document is a page of password tips that staff may ignore. After a phishing test, the manager publicly named the three staff who clicked, and since then nobody has reported a suspicious email. The managing director also shares his login with his assistant.

```say
Look at the scenario on the screen.
? Give me three problems in this scenario and what you would do about each one.
expect: The password tips are only a guideline, so it needs mandatory policies, standards and procedures; PCI DSS and UK GDPR apply; naming clickers is punitive and has killed reporting, so make simulations blame-free with follow-up education; the director sharing a login undermines culture from the top.
```

## Review (5 min)

### Key distinctions and traps
- Policy, standard, procedure: mandatory. Guideline: optional
- Compliance is the floor, not the ceiling
- PCI DSS: not a law but contractually mandatory. ISO 27001: certifiable
- SOC 2 Type 1 = snapshot. Type 2 = over time, stronger
- MOU informal, MOA formal. Phishing sims teach, never punish
Example: GDPR 72 hours. HIPAA 60 days.

```say
The traps here are mostly about one word. Mandatory or optional, law or contract, exists or works.
And on the people side, anything that makes staff afraid to speak up is the wrong answer, because hidden incidents are the most dangerous kind.
? Which standard is compulsory for card payments even though it is not a law, and what makes it compulsory?
expect: PCI DSS, made compulsory through contracts with the card companies.
```

```quiz
[
 {
  "objective": "5.1",
  "type": "multiple_choice",
  "q": "What is the key difference between a framework and a regulation?",
  "options": [
   "They are always identical",
   "Frameworks are criminal laws",
   "A framework is generally guidance; a regulation is a legal requirement",
   "Regulations are optional"
  ],
  "answer": "A framework is generally guidance; a regulation is a legal requirement",
  "why": "Frameworks such as the NIST CSF are voluntary guidance, while regulations such as GDPR and HIPAA are laws you must follow.",
  "source": "exam"
 },
 {
  "objective": "5.5",
  "type": "multiple_choice",
  "q": "In SOC 2, what does Type 2 demonstrate compared with Type 1?",
  "options": [
   "Only that a policy exists",
   "That no controls exist",
   "That penetration testing is complete",
   "Controls worked over a period rather than only existing at a point in time"
  ],
  "answer": "Controls worked over a period rather than only existing at a point in time",
  "why": "Type 1 is a snapshot showing controls exist; Type 2 tests that they operated effectively over months, which makes it the stronger report.",
  "source": "exam"
 },
 {
  "objective": "5.3",
  "type": "multiple_choice",
  "q": "What is required before a penetration test?",
  "options": [
   "Written authorisation",
   "A public announcement",
   "Deletion of logs",
   "Disabling all controls"
  ],
  "answer": "Written authorisation",
  "why": "Rules of engagement with the tester must be agreed and signed first; testing without permission in writing is illegal.",
  "source": "exam"
 },
 {
  "objective": "5.4",
  "type": "multiple_choice",
  "q": "A UK company discovers that customers' personal data has been breached. Under GDPR, how long does it have to notify the supervisory authority?",
  "options": [
   "60 days",
   "72 hours",
   "30 days",
   "24 hours"
  ],
  "answer": "72 hours",
  "why": "GDPR requires notification to the supervisory authority within 72 hours of becoming aware of a breach; 60 days is the HIPAA deadline for US health data.",
  "source": "exam"
 },
 {
  "objective": "5.1",
  "type": "multiple_choice",
  "q": "The IT team publishes advice on choosing memorable passphrases, which staff may follow at their discretion. Which type of document is this?",
  "options": [
   "Policy",
   "Standard",
   "Guideline",
   "Procedure"
  ],
  "answer": "Guideline",
  "why": "Guidelines are recommendations and are optional, whereas policies, standards and procedures are all mandatory.",
  "source": "exam"
 },
 {
  "objective": "5.6",
  "type": "multiple_choice",
  "q": "An organisation runs monthly phishing simulations. Which result most clearly shows its awareness programme is working?",
  "options": [
   "More staff receive disciplinary warnings each month",
   "The simulations are made easier so fewer people click",
   "Staff are told the date of each simulation in advance",
   "More staff flag the simulated emails to the security team each month"
  ],
  "answer": "More staff flag the simulated emails to the security team each month",
  "why": "A rising report rate shows staff are spotting and escalating phishing; punishment and rigged tests hide the real picture.",
  "source": "exam"
 }
]
```
