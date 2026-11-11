<!-- objectives: 4.8,4.9 -->
<!-- pack-lesson: 14 -->
# Incident Response and Forensics

## Retrieval (5 min)

### Retrieval
Quick check on earlier material.

```say
? If your bank told you your card details had been stolen, what would you want them to tell you, and how quickly?
expect: What was taken, what they are doing about it, and what to do next, as soon as possible.
? What kind of information do you think a computer keeps in memory that it loses when switched off?
expect: Running programs, open network connections, unsaved data and things like encryption keys.
```

## Intro (5 min)

### When something goes wrong
- 4.8: the response process, digital forensics, legal duties
- 4.9: the logs and data sources that power an investigation
- Phase ORDER is heavily tested
Example: Ransomware hits a file server on Friday night: who does what, in which order, and what must be kept?

```say
Today is about the worst day at work: an attack has actually happened. The exam wants you to know the steps a response team follows, in the right order, and how to handle anything that might end up in court.
We will also look at where investigators find the truth, which logs to check early, and the legal clocks that start ticking after a breach.
? If you found ransomware on a work laptop, what would your very first instinct be, and why might that instinct be risky?
expect: Many people would switch it off or wipe it; that can destroy volatile evidence such as memory, so it should be isolated and handled by the process instead.
```

## Teaching (15 min)

### The response lifecycle
- 1 Preparation, 2 Detection, 3 Analysis
- 4 Containment, 5 Eradication, 6 Recovery
- 7 Lessons learned, which feeds back into Preparation
- Memory trick: People Don't Always Contain Every Ransomware Leak
Example: Isolate the infected server from the network (containment), remove the malware (eradication), restore from clean backups (recovery), then hold a review meeting (lessons learned)
Common mix-up: Lessons learned is optional once systems are back up. It is a formal phase that feeds back into preparation, so the same attack does not succeed twice.

```say
Incident response is a structured process, and the order is what gets tested. Preparation comes before anything goes wrong: the plan, the tools, the trained people. Then you spot something, work out what it really is and how far it has spread.
Containment stops the damage spreading, for example by unplugging a host from the network. Eradication removes the cause, recovery brings systems back to normal, and the lessons learned meeting improves the plan for the next time.
A classic trap is jumping to eradication or recovery first. If you wipe and restore before isolating the threat, the attacker may still be inside and simply reinfect the clean systems.
Here is a common mistake. Lessons learned is optional once systems are back up. That is not right. It is a formal phase that feeds back into preparation, so the same attack does not succeed twice.
? Recite the seven phases in order using the memory trick.
expect: Preparation, detection, analysis, containment, eradication, recovery, lessons learned.
? A team rebuilds a server from backup before working out how the attacker got in. Which phases did they skip or rush?
expect: Analysis and containment, and probably eradication, so the attacker could still be present and reinfect it.
```

### Order of volatility
- Collect the most FRAGILE data first
- 1 CPU registers and cache
- 2 Routing table, ARP cache, process table, kernel statistics, memory (RAM)
- 3 Temp files and swap, 4 disk, 5 remote logs and monitoring data
- 6 Physical configuration and network topology, 7 archival media
Example: Capture RAM BEFORE pulling the plug: an encryption key or a fileless malware sample may only exist in memory
Common mix-up: The first thing to do with a compromised machine is switch it off to stop the attack. Switching off destroys memory contents; capture the volatile data first and isolate the machine from the network instead.

```say
Volatility just means how quickly data disappears. Registers and cache change in nanoseconds. Next is everything the running system holds in memory: its routing and address tables, the list of processes, kernel statistics and the memory itself, all gone at power-off.
Below that, temporary files and swap linger a little longer, then the disk survives a reboot, remote logs sit on another system, and backups on a shelf last for years.
So the rule is simple: grab whatever will vanish soonest, then work your way down to the stable stuff. Pulling the power cable straight away throws away everything at the top of the list.
Here is a common mistake. The first thing to do with a compromised machine is switch it off to stop the attack. That is not right. Switching off destroys memory contents; capture the volatile data first and isolate the machine from the network instead.
? You can collect either the contents of memory or a copy of the hard drive first. Which, and why?
expect: Memory first, because it is lost at power-off, while the disk persists.
```

### Forensics essentials
- Chain of custody: who handled it, when, and what they did. Broken chain = inadmissible
- Forensic copy: bit-for-bit image. ALWAYS analyse the copy, never the original
- Write blocker: hardware or software that stops any writes to the source drive
- Legal hold: litigation expected, so suspend deletion policies IMMEDIATELY
Example: A seized laptop drive is connected through a write blocker, imaged, and the log notes each person who signed it out and back in
Common mix-up: Looking around the original drive is fine as long as nothing is deleted. Even opening files can change timestamps and metadata, so all analysis is done on a verified copy.

```say
Treat every item as if a court will look at it. The custody log is a paper trail of every hand it passed through; one unexplained gap and the other side can argue it was tampered with.
You never investigate the original drive. You take an exact bit-level image, through a device that physically stops anything being written, and confirm the copy matches the original using a hash.
A legal hold comes from the lawyers. The moment a lawsuit is expected, routine deletion such as email retention clean-ups must stop, or the company could be accused of destroying evidence.
Here is a common mistake. Looking around the original drive is fine as long as nothing is deleted. That is not right. Even opening files can change timestamps and metadata, so all analysis is done on a verified copy.
? Why use a write blocker when imaging a suspect's drive?
expect: So nothing on the original is altered during copying, keeping it intact and admissible.
? A company expects to be sued over a data leak. What must happen to its automatic email deletion policy?
expect: It must be suspended immediately under a legal hold so relevant data is kept.
```

### Investigation data sources
- DNS logs: malware must resolve its C2 domains. Check EARLY
- CloudTrail: the AWS API call log, the cloud investigation goldmine
- Timestomping: attacker fakes file timestamps. Corroborate from MULTIPLE sources
Example: A file claims to be from 2019, but DNS and firewall logs show the host first contacted the attacker's domain last Tuesday
Common mix-up: A file's created date tells you exactly when the attacker dropped it. Timestamps can be forged by timestomping, so they must be checked against independent logs.

```say
Malware almost always has to look up the name of its command and control server before it can phone home, so name lookup logs quickly reveal which machines are infected and where they were calling.
In Amazon Web Services, every action taken through the management interface or its programming interface is recorded by CloudTrail: who created that user, who opened that storage bucket, and from which address.
Attackers know investigators love timestamps, so they fake them. Never trust one clock. Line up the file times with logs from other systems, and if they disagree, the outside logs usually win.
Here is a common mistake. A file's created date tells you exactly when the attacker dropped it. That is not right. Timestamps can be forged by timestomping, so they must be checked against independent logs.
? Why are name lookup logs so useful when you are hunting for infected machines?
expect: Because malware has to resolve its command and control domain, so the logs show which hosts asked for it.
? Someone deleted a storage bucket in your company's Amazon cloud. Which log tells you who did it?
expect: CloudTrail, which records API calls with the identity and source.
```

### Deadlines and team colours
- GDPR: 72 HOURS to notify the supervisory authority, e.g. the ICO. Fines up to EUR 20m or 4% of global turnover
- HIPAA: 60 DAYS to notify affected individuals; breaches of 500+ also reported to the regulator and media. Applies to business associates too
- Red: offensive. Blue: detect and respond
- Purple: both sides share findings
Example: A UK retailer discovers a customer data breach on Monday 9am: the ICO must hear by Thursday 9am
Common mix-up: Under GDPR you have 72 days to report a breach. It is 72 hours, not days; the sixty-day deadline belongs to HIPAA, and that one is for telling the patients.

```say
Two numbers to memorise. Under the General Data Protection Regulation, GDPR, you have seventy-two hours from becoming aware to tell the regulator, which in the UK is the Information Commissioner's Office. HIPAA, the American health privacy law, gives sixty days to tell the patients affected.
HIPAA also reaches beyond hospitals to their business associates, such as a billing company handling patient data.
Red teams play the attacker and blue teams defend. On their own, the red side writes a report and leaves. When they sit with the defenders, share techniques live, and tune detections together, you get the purple approach.
Here is a common mistake. Under GDPR you have 72 days to report a breach. That is not right. It is 72 hours, not days; the sixty-day deadline belongs to HIPAA, and that one is for telling the patients.
? Which deadline is measured in hours and which in days, and who is notified in each case?
expect: GDPR is 72 hours to the supervisory authority; HIPAA is 60 days to the affected individuals.
```

## Guided practice (10 min)

### Ransomware on a Friday night
- Put the response steps in order
- Decide what to collect first and how to keep it admissible
Example: Isolate first, capture memory, image the disk through a write blocker

```say
Let's work through a realistic case. Talk me through it as if you were the lead responder, and use the exact phase names the exam uses.
Remember there are two jobs at once here: stopping the damage, and protecting anything the lawyers or police may need.
? The junior admin wants to pull the power cable on the infected server right now. What do you tell them?
expect: Do not power off; isolate it from the network and capture volatile data such as memory first.
```

### Scenario: Ransomware on a Friday night
A UK online shop finds ransomware on its customer database server at 11pm on Friday. The server is still powered on. Customer card details may have been copied out. Management expects legal action from customers. The shop's systems run partly in Amazon Web Services.

```say
Look at the scenario on the screen.
? Walk me through your first actions in phase order, what you collect and in what order, which logs you check, and any legal deadlines.
expect: Contain by isolating the server from the network; capture memory and running state before disk, then image the disk with a write blocker and analyse the copy; record chain of custody; place a legal hold on deletion; check DNS logs for command and control and CloudTrail for cloud activity; notify the ICO within 72 hours; then eradicate, recover and hold lessons learned.
```

## Review (5 min)

### Key distinctions and traps
- People Don't Always Contain Every Ransomware Leak
- Most volatile first: registers and cache, memory and system tables, temp and swap, disk, remote logs, archives
- Analyse the copy, never the original
- GDPR 72 hours, HIPAA 60 days
- Red attacks, blue defends, purple shares
Example: DNS logs early, CloudTrail for AWS, corroborate timestamps

```say
The order questions are free marks if you have the trick fixed in your head, so say it to yourself until it is automatic.
Most wrong answers in this topic come from doing the obvious thing too soon: switching off, wiping, restoring, or looking at the original drive. Slow down, preserve, then act.
And watch for hours versus days on the notification questions.
? Which comes straight after eradication, and which straight before it?
expect: Recovery comes after eradication; containment comes before it.
```

```quiz
[
 {
  "objective": "4.8",
  "type": "multiple_choice",
  "q": "What is the purpose of incident containment?",
  "options": [
   "Erase all evidence immediately",
   "Skip analysis",
   "Approve a new policy",
   "Limit the spread or impact of the incident"
  ],
  "answer": "Limit the spread or impact of the incident",
  "why": "Containment, such as isolating an infected host, stops the damage growing while keeping the systems available for investigation before eradication and recovery.",
  "source": "exam"
 },
 {
  "objective": "4.8",
  "type": "multiple_choice",
  "q": "Why should forensic evidence maintain chain of custody?",
  "options": [
   "To prove how evidence was handled and preserve its evidentiary value",
   "To increase bandwidth",
   "To replace backups",
   "To make passwords stronger"
  ],
  "answer": "To prove how evidence was handled and preserve its evidentiary value",
  "why": "A documented record of who handled the evidence, when and what they did shows it was not tampered with; a broken chain can make it inadmissible in court.",
  "source": "exam"
 },
 {
  "objective": "4.8",
  "type": "multiple_choice",
  "q": "Which team exercise uses defenders and attackers working together to improve security?",
  "options": [
   "Only blue team",
   "Purple team",
   "Only red team",
   "CAB"
  ],
  "answer": "Purple team",
  "why": "A purple team brings the red attackers and blue defenders together to share findings, so detections improve straight away.",
  "source": "exam"
 },
 {
  "objective": "4.9",
  "type": "multiple_choice",
  "q": "An analyst suspects a workstation is infected and wants to see which external command-and-control domains it tried to reach. Which data source should be checked first?",
  "options": [
   "Badge reader logs",
   "Printer audit logs",
   "DNS query logs",
   "HR leaver records"
  ],
  "answer": "DNS query logs",
  "why": "Malware has to resolve its command-and-control domain names before connecting, so DNS logs show which hosts looked them up and when.",
  "source": "exam"
 }
]
```
