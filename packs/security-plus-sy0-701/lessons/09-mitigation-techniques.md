<!-- objectives: 2.5 -->
<!-- pack-lesson: 9 -->
# Mitigation Techniques

## Retrieval (5 min)

### Retrieval
Quick check on earlier material.

```say
? If one computer in an office picked up a virus, what would you do first?
expect: Disconnect it from the network so it cannot spread, then investigate and clean or rebuild it.
? Why do software updates matter for security?
expect: They fix known flaws that attackers could otherwise exploit.
```

## Intro (5 min)

### The response toolkit
- Mitigation: action that reduces the likelihood or impact of a threat
- Compensating control: an alternative when the ideal control is impossible
- A stopgap, not the permanent fix
Example: Can't patch an old machine yet? Wall it off and watch it closely

```say
Knowing the weaknesses and attacks only helps if you can respond to them. Today is the response toolkit: what you actually do to make an attack less likely, or less damaging if it lands.
Pay special attention to compensating controls. When the ideal fix is impossible, you put something else in its place to cover the gap, and you keep working towards the real fix.
? Why would anyone use a compensating control instead of the proper one?
expect: Because the ideal control is impossible or not possible yet, so an alternative reduces the risk in the meantime.
```

## Teaching (15 min)

### Segmentation versus isolation
- Segmentation: split the network into zones, PROACTIVE
- Limits lateral movement
- Isolation: disconnect ONE device, REACTIVE
- Quarantine the infected machine NOW
Example: Card payment systems kept in their own zone, away from ordinary office PCs
Common mix-up: Segmentation and isolation are just two names for the same thing. Segmentation is a proactive design that divides the network into zones, while isolation is a reactive step that cuts off one specific device.

```say
Segmentation is planned in advance. You split the estate into zones so that one compromised machine cannot wander freely to the rest. You are building the walls before anything goes wrong.
Isolation is what you do in the moment. One device is infected, so you cut it off right away to stop the spread, and then you investigate.
Segmentation is like a hospital split into wards, so an outbreak on one ward stays there, while isolation is moving one infectious patient into a side room straight away. The comparison breaks down because network zones still need controlled paths between them, and those paths are exactly where intruders try to cross.
Here is a common mistake. Segmentation and isolation are just two names for the same thing. That is not right. Segmentation is a proactive design that divides the network into zones, while isolation is a reactive step that cuts off one specific device.
? Ransomware has just been spotted on one laptop. Is this a job for segmentation or for isolating the device, and why?
expect: Isolation, because it is the reactive step that cuts that one device off immediately; segmentation is the planned layout.
```

### Allow listing and patching
- Application allow listing: only approved apps run, default DENY
- Unknown malware simply cannot execute
- Patching: apply vendor fixes for KNOWN vulnerabilities
- Useless against zero-days: compensate instead
Example: A finance PC allowed to run only its accounting package and a browser
Common mix-up: If every patch is installed, the system is fully protected. Patches only cover known flaws, so a zero-day can still get through and needs other controls around it.

```say
Allow listing flips the usual approach. Instead of trying to spot everything bad, you name the handful of things that are allowed and block the rest. Brand new malware has never been approved, so it never gets to run.
Patching fixes the holes the vendor already knows about. It is essential, but it does nothing for a zero-day, because there is no fix to apply yet. That is exactly when compensating controls earn their keep.
Here is a common mistake. If every patch is installed, the system is fully protected. That is not right. Patches only cover known flaws, so a zero-day can still get through and needs other controls around it.
? Why does allow listing stop malware that no antivirus has ever seen before?
expect: Only approved programs may run, so anything new or unknown is blocked by default.
```

### Encryption and monitoring
- Encryption: stolen data becomes worthless
- At rest, in transit, in use
- Monitoring: DETECTIVE, watches for indicators
- Tools: SIEM, EDR, IDS, NetFlow
Example: A stolen laptop with full-disk encryption gives the thief nothing readable
Common mix-up: Encryption stops data from being stolen. Encryption does not prevent the theft; it makes the stolen data unreadable without the key.

```say
Encryption does not stop the theft. It makes whatever was taken useless. Protect data in three states: sitting on disk, moving across a network, and being processed in memory.
Monitoring is the detective control in this set. It will not block an attack, but it spots the indicators so you can respond. Expect to see security information and event management, endpoint detection and response, intrusion detection, and flow records from routers.
Here is a common mistake. Encryption stops data from being stolen. That is not right. Encryption does not prevent the theft; it makes the stolen data unreadable without the key.
? Encryption or monitoring: which one is the detective control, and why is detecting still worth having?
expect: Monitoring; it lets you spot and respond to an attack that got past the preventive controls.
```

### Hardening checklist
- Change default credentials: removes the easiest attack vector
- Disable unused services; close unused ports (Telnet 23)
- Remove unnecessary software: fewer vulnerabilities
- Host-based firewall and HIPS: device-level blocking
- Enforce secure baselines (SELinux, Group Policy) to prevent drift
Example: Telnet on port 23 sends everything, passwords included, in clear text
Common mix-up: Hardening is done once, when a system is first built. Settings drift over time, so a baseline enforced by tools such as Group Policy keeps the hardening in place.

```say
Hardening means stripping a system back to what it genuinely needs. Anything that is not running cannot be exploited, and every program you remove is one less thing to keep patched.
Factory passwords go first, because they are the easiest way in. Then shut the doors you are not using, add a firewall and intrusion prevention on the device itself, and lock the result into a baseline so settings cannot quietly drift back.
Here is a common mistake. Hardening is done once, when a system is first built. That is not right. Settings drift over time, so a baseline enforced by tools such as Group Policy keeps the hardening in place.
? What does a secure baseline give you that a one-off clean-up does not?
expect: It enforces the hardened settings over time, so systems do not drift back to insecure configurations.
```

### Matching the fix to the problem
- Legacy system, can't patch: SEGMENT + MONITOR
- Critical web flaw, patch in 2 weeks: WAF as a virtual patch + monitoring
- Old server still running unused: DECOMMISSION, wipe data, revoke creds
- Junior dev with domain admin: LEAST PRIVILEGE, remove excess rights
Example: A web application firewall blocks the exploit pattern while developers finish the real fix

```say
This map is exam gold. When a system cannot be patched, you surround it: put it in its own zone and watch it closely. Those are compensating controls doing their job.
A web application firewall in front of a vulnerable site is often called a virtual patch. It filters out the attack before it reaches the flaw, buying time until the proper fix is ready.
Forgotten servers are a gift to intruders, so retire them properly: wipe the data and revoke any credentials they held. And when someone holds far more rights than their job calls for, trim them back to the minimum.
? Why is a web application firewall only a stopgap for a flaw in the site's own code?
expect: It filters attacks in front of the flaw, but the flaw is still there; the real fix is patching the code.
```

## Guided practice (10 min)

### Pick the mitigation
- Is it happening now, or are you planning ahead?
- Can the real fix be applied right now?
Example: Stolen hard drive, nothing readable: encryption at rest did its job

```say
When a question describes a situation and asks for the best mitigation, first decide whether the trouble is live or something you are preparing for. Live trouble usually calls for isolation. A problem you cannot fix properly calls for a compensating control.
? A company is worried about brand new malware that no scanner recognises. Which mitigation fits best?
expect: Application allow listing, because only approved programs can run.
```

### Scenario: Pick the mitigation
A small clinic finds ransomware on a reception PC. It also runs an old X-ray workstation that cannot be patched because the vendor has gone out of business, and an intern turns out to have full domain admin rights.

```say
Look at the scenario on the screen.
? What would you do about each of the three problems, and in what order?
expect: Isolate the infected PC immediately and restore from a clean backup; segment and monitor the unpatchable workstation as compensating controls; remove the intern's excess rights. Isolation first, because that problem is live.
```

## Review (5 min)

### Remember the map
- Segmentation = proactive zones; isolation = reactive quarantine
- Patching covers KNOWN flaws only; zero-days need compensating controls
- Allow listing = default deny
- Monitoring is DETECTIVE
- Compensating controls are temporary
Example: Can't patch? Segment and monitor

```say
Two words separate the most confused pair. Segmentation is proactive, decided before trouble. Isolation is reactive, done in the moment.
And whenever a question says the proper fix is impossible, look for the answer that wraps a compensating control around the problem, not one that pretends the problem is solved.
? Name one mitigation that would make a stolen laptop useless to a thief.
expect: Full-disk encryption, which is encryption at rest.
```

```quiz
[
 {
  "objective": "2.5",
  "type": "multiple_choice",
  "q": "Which mitigation reduces attack surface by disabling unnecessary services?",
  "options": [
   "Hardening",
   "Risk acceptance",
   "Attribution",
   "Non-repudiation"
  ],
  "answer": "Hardening",
  "why": "Hardening strips a system back to what it needs, removing defaults, unused services and open ports so there is less to attack.",
  "source": "exam"
 },
 {
  "objective": "2.5",
  "type": "multiple_choice",
  "q": "Which technique limits an attacker’s ability to move between network segments?",
  "options": [
   "Network load balancing",
   "Network segmentation",
   "Network encryption",
   "Network time synchronisation"
  ],
  "answer": "Network segmentation",
  "why": "Dividing the network into zones with controls between them stops an intruder moving freely from one area to the next.",
  "source": "exam"
 },
 {
  "objective": "2.5",
  "type": "multiple_choice",
  "q": "What is the purpose of the principle of least privilege when assigning permissions?",
  "options": [
   "Give users every permission",
   "Remove authentication",
   "Give only the access needed for the job",
   "Make all systems public"
  ],
  "answer": "Give only the access needed for the job",
  "why": "Least privilege means each person or process gets only the minimum rights their role requires, which limits the damage if an account is misused.",
  "source": "exam"
 }
]
```
