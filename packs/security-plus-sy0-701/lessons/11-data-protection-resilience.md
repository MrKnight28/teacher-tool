<!-- objectives: 3.3,3.4 -->
<!-- pack-lesson: 11 -->
# Data Protection and Resilience

## Retrieval (5 min)

### Retrieval
Quick check on earlier material.

```say
? What do you already know about why organisations keep backups in more than one place?
expect: So one fire, flood, theft or attack cannot destroy both the live data and its copies.
? What does encryption protect against if a device is lost?
expect: Anyone finding it cannot read the data without the key.
```

## Intro (5 min)

### Protect the data, survive the disaster
- Three data states and how to guard each
- Getting rid of data safely
- Recovery targets, sites and backups
- Power, continuity plans and testing them
Example: A ransomware attack tests every topic today at once: encryption, backups, recovery time

```say
Today has two halves. First, how to protect information wherever it is, including when you finally get rid of it. Second, resilience: how an organisation keeps going, and gets back up, when something goes badly wrong.
This area is full of lists that look alike, so the exam tests whether you can pick the right one from a short scenario. We will focus on the clues that point to each answer.
? In one sentence, what does resilience mean for an organisation?
expect: The ability to keep operating through a disruption and recover quickly afterwards.
```

## Teaching (15 min)

### Data states and data loss prevention
- At rest: stored on disk, database or tape
- In transit: moving across a network
- In use: in RAM or the CPU, the hardest to protect
- Protect with: disk, database or file encryption; TLS, HTTPS, VPN or SSH; secure enclaves
- DLP stops sensitive data leaving, not attackers getting in
Example: A DLP rule blocks an email with 200 card numbers attached from going to a personal Gmail account
Common mix-up: Data loss prevention is another tool for keeping hackers out of the network. It focuses on outbound flows, spotting and blocking sensitive information as it tries to leave, whoever is sending it.

```say
Information is always in one of three places: sitting in storage, travelling across a network, or open in memory while a program works on it. Each needs its own protection.
Picture water. Stored information is water in a sealed bottle. Information on the move is water in pipes. Information open in memory is water in an open glass, which is why it is the hardest to protect.
So stored data gets encrypted on the disk, in the database or per file. Travelling data gets an encrypted tunnel such as transport layer security, a virtual private network or secure shell. Data in memory needs special hardware called a secure enclave.
Data loss prevention looks the other way from most controls. It is not about keeping attackers out; it watches what is going out, and blocks sensitive information from leaving.
Here is a common mistake. Data loss prevention is another tool for keeping hackers out of the network. That is not right. It focuses on outbound flows, spotting and blocking sensitive information as it tries to leave, whoever is sending it.
? A laptop is stolen from a car. Which state is its data in, and what would protect it?
expect: At rest; full disk encryption.
? What is data loss prevention actually trying to stop?
expect: Sensitive data leaving the organisation, whether by accident or on purpose.
```

### Secure data destruction
- Overwriting: random data written several times, for HDDs
- Degaussing: magnets wipe hard drives and tape only
- Secure erase: built-in command, the SSD answer
- Physical destruction: shred, drill or incinerate anything
- Cryptographic erasure: destroy the key, fastest for encrypted data
Example: SSD rule: SSDs are not magnetic, so degaussing does nothing. Use secure erase or shred
Common mix-up: Degaussing will wipe any drive, including a solid state drive. Solid state drives use flash memory rather than magnetic platters, so a degausser leaves their data intact; use secure erase or shred them.

```say
Deleting a file only removes the pointer to it, so the real question is how to make data unrecoverable. The right answer depends on what the data is stored on.
Spinning hard drives and tape store data magnetically, so a powerful magnet scrambles them. Solid state drives store data in flash chips, so a magnet does nothing at all. For those, use the drive's own secure erase command, or destroy it physically.
If the data was encrypted, the quickest option is to destroy the key. Without it the data is unreadable for good, which is very handy in the cloud where you cannot get your hands on the disks.
Here is a common mistake. Degaussing will wipe any drive, including a solid state drive. That is not right. Solid state drives use flash memory rather than magnetic platters, so a degausser leaves their data intact; use secure erase or shred them.
? A company wants to reuse a batch of laptops with solid state drives. How should it wipe them?
expect: Use the SSD's secure erase command, or cryptographic erasure if the drives were encrypted; not degaussing.
```

### Recovery targets, sites and power
- RPO: how much data you can afford to lose
- RTO: how long you have to get systems back
- Hot site: minutes to hours, very expensive
- Warm site: hours to days, medium cost; cold site: days to weeks, cheap
- UPS gives instant battery cover; the generator takes over for long outages
Example: Backups run at midnight, the server dies at 6pm: up to 18 hours of data is lost, which must fit the RPO
Common mix-up: The recovery point objective is how quickly we need to get back up and running. That is the recovery time objective; the recovery point is about how much data, measured back in time from the incident, you can afford to lose.

```say
Picture a timeline with the disaster in the middle. Look backwards to your last good backup: that gap is the recovery point objective, the data you are prepared to lose. Look forwards to when systems are working again: that gap is the recovery time objective.
A quick way to keep them apart: point looks back at data, time looks forward to recovery.
Recovery sites trade cost against speed. A hot site is ready to run almost at once and costs the most. A cold site is little more than space and power, so it is cheap but takes a long time to bring up.
For power, the battery unit and the generator work as a team. The battery cuts in instantly so nothing switches off, and it holds on just long enough for the generator to start and carry the load.
Here is a common mistake. The recovery point objective is how quickly we need to get back up and running. That is not right. That is the recovery time objective; the recovery point is about how much data, measured back in time from the incident, you can afford to lose.
? A hospital says it cannot lose more than five minutes of patient records. Is that a recovery time or recovery point target?
expect: Recovery point objective, because it is about how much data can be lost.
? Why is a generator on its own not enough to protect servers in a power cut?
expect: It takes time to start, so servers would lose power in the gap; a UPS bridges that gap instantly.
```

### Backup types
- Full: everything; slowest to make, fastest to restore
- Incremental: only what changed after the previous backup of any kind; quick to make, slow to restore
- Differential: everything changed after the most recent full; restore needs the full plus the latest differential
- Snapshot is a point-in-time copy; mirror is a continuous real-time copy
- Air-gapped: disconnected, so ransomware cannot reach it
Example: Full on Sunday, failure on Thursday: incremental restore needs Sunday plus Monday, Tuesday and Wednesday; a differential restore needs Sunday plus Wednesday
Common mix-up: An incremental only stores what changed since the last full, the same as a differential. An incremental holds what changed since the previous backup of whatever kind, which is why a restore needs the whole chain of them.

```say
Every backup scheme is a trade between time spent making copies and time spent restoring. A complete copy every night is simple to restore but slow and bulky to make.
Incrementals are small and quick because each one only holds what changed since the one before. The price comes at restore time, when you need the full copy and then every incremental in order.
A differential keeps growing through the week, because it holds everything since the last complete copy. That makes it slower to take than an incremental, but a restore only ever needs two sets.
Ransomware tries to encrypt backups too. A copy that is physically disconnected from the network cannot be reached, which is why the air gap is the classic exam answer.
Here is a common mistake. An incremental only stores what changed since the last full, the same as a differential. That is not right. An incremental holds what changed since the previous backup of whatever kind, which is why a restore needs the whole chain of them.
? Which backup approach gives the quickest nightly backups, and what is the downside?
expect: Incremental; restoring needs the full backup plus every incremental since, so it is slow.
? What makes an air-gapped backup safe from ransomware?
expect: It is disconnected from the network, so malware on the network cannot reach or encrypt it.
```

### Continuity planning and testing
- BIA first: what is critical and the impact of losing it
- BCP: keep the business running
- DRP: recover the IT, a subset of the BCP
- Tests, least to most disruptive: tabletop, simulation, parallel, failover, full interruption
Example: Tabletop: managers talk through a ransomware scenario in a meeting room; full interruption: the primary data centre is shut down for real
Common mix-up: The disaster recovery plan and the business continuity plan are the same document. Disaster recovery is the narrower IT recovery piece that sits inside the wider continuity plan for the whole business.

```say
Order matters here. You cannot plan to protect what you have not identified, so a business impact analysis comes first and works out which processes matter most and what losing them costs.
The continuity plan then covers keeping the whole business going, people, premises and processes. The disaster recovery plan is the IT part inside it, focused on getting systems back.
Plans are worthless until tested. A tabletop is just a discussion. A simulation practises realistically without switching anything over. A parallel test brings recovery systems up alongside the live ones. A failover test actually switches across. A full interruption shuts the primary down completely, which is the most realistic and the most risky.
Here is a common mistake. The disaster recovery plan and the business continuity plan are the same document. That is not right. Disaster recovery is the narrower IT recovery piece that sits inside the wider continuity plan for the whole business.
? Which planning step must happen before you can write a sensible continuity plan, and why?
expect: The business impact analysis, because it identifies what is critical and the impact of losing it.
? A company wants to test its recovery plan with zero disruption to operations. Which test fits?
expect: A tabletop exercise.
```

## Guided practice (10 min)

### Ransomware at the accounts firm
- Spot why the backups failed
- Choose the backup and site
- Check the targets are met
Example: Nightly backups only meet a one-day loss limit if they survive the attack

```say
Let us work through a realistic case together. You will see it on screen in a moment; take each part in turn and tell me your reasoning, not just the term.
Start with what the business can tolerate, then work out which choices meet it.
? Before we start, why is a backup drive that stays plugged into the server a risk?
expect: Ransomware could reach it over the network and encrypt it along with the servers.
```

### Scenario: Ransomware at the accounts firm
An accounts firm takes a full backup on Sunday and incrementals each night to a drive plugged into the server. Ransomware strikes on Friday morning and encrypts the servers and the drive. The partners say they can lose at most one day of work and must be running again within a few hours.

```say
Look at the scenario on the screen.
? What went wrong with the backups, what would you change, and what kind of recovery site matches their time target?
expect: The backups were online so ransomware reached them; keep an air-gapped or offline copy. The one-day RPO is met by nightly backups; a few-hours RTO needs a hot site. Restoring incrementals needs Sunday plus every night since.
```

## Review (5 min)

### Key distinctions and traps
- In use is the hardest state to protect
- Magnets do nothing to SSDs
- Point looks back at data; time looks forward to recovery
- Order: BIA, then BCP, then DRP
- Incremental: fast backup, slow restore
Example: Hot is fast and dear, cold is slow and cheap, warm sits between

```say
The biggest traps are degaussing a solid state drive, swapping the two recovery objectives, and mixing up which backup needs the whole chain to restore.
When a question asks for the least disruptive test, think talking, not switching. When it asks for the most realistic, think pulling the plug on the primary.
And remember data loss prevention faces outwards. If the scenario is about information leaving, that is your answer.
? If a firm's recovery plan says systems must be back within four hours, which objective is that?
expect: The recovery time objective.
? Which protection fits data travelling between a browser and a web server?
expect: Encryption in transit such as TLS or HTTPS.
```

```quiz
[
 {
  "objective": "3.3",
  "type": "multiple_choice",
  "q": "Data being actively processed is which state?",
  "options": [
   "At rest",
   "In transit",
   "In use",
   "Destroyed"
  ],
  "answer": "In use",
  "why": "Data in use is held in memory or the processor while a program works on it; it is the hardest state to protect, which is where secure enclaves help.",
  "source": "exam"
 },
 {
  "objective": "3.4",
  "type": "multiple_choice",
  "q": "Which backup type copies changes since the last full backup?",
  "options": [
   "Full backup",
   "Snapshot only",
   "Archive only",
   "Differential backup"
  ],
  "answer": "Differential backup",
  "why": "A differential holds everything changed since the last full backup, so a restore needs just the full plus the latest differential. An incremental only holds changes since the previous backup of any kind.",
  "source": "exam"
 },
 {
  "objective": "3.3",
  "type": "multiple_choice",
  "q": "Which destruction method is specifically suited to magnetic media?",
  "options": [
   "Degaussing",
   "Secure erase",
   "Crypto erasure",
   "Formatting an SSD"
  ],
  "answer": "Degaussing",
  "why": "Degaussing uses a strong magnetic field to scramble hard drives and tape. It does nothing to SSDs, which need secure erase or physical destruction.",
  "source": "exam"
 }
]
```
