<!-- objectives: 2.3 -->
<!-- pack-lesson: 7 -->
# Vulnerabilities

## Retrieval (5 min)

### Retrieval
Quick check on earlier material.

```say
? From what you already know, what tends to make a computer easy to attack?
expect: Anything sensible: missing updates, unchanged factory passwords, old unsupported software, risky downloads.
? What do you think the phrase zero-day refers to?
expect: A flaw the vendor does not know about yet, so the vendor has had zero days to fix it.
```

## Intro (5 min)

### Weak spots before attacks
- Vulnerability: a weakness a threat could exploit
- Comes from software bugs, hardware flaws or human misconfiguration
- Today: application, platform, supply chain and misconfiguration weaknesses
Example: A login form that trusts whatever is typed into it

```say
Today is about the weak spots themselves, before anyone attacks them. A threat is the person or thing that might cause harm. The weakness is the gap it would use to do it.
The exam loves a short story followed by the question of which kind of weakness it shows. So the skill we are building is naming the category quickly and with confidence.
? In your own words, what is the difference between a threat and a weakness?
expect: The threat is who or what could cause harm; the weakness is the flaw it could use to do so.
```

## Teaching (15 min)

### Application weaknesses
- SQL injection: malicious SQL typed into an input field
- Reflected XSS: script in a link, hits ONLY the user who clicks
- Stored XSS: script saved in the database, hits EVERY visitor
- Buffer overflow and memory injection: attacker code lands in memory
- Race condition (TOC/TOU): abuses the gap between CHECK and USE
Example: ' OR '1'='1 typed into a login box makes the password test always true
Common mix-up: A race condition means two attackers racing each other to break in first. It is the timing gap between when a system checks a resource and when it uses it, and the attacker changes the resource inside that gap.

```say
Injection works because the application pastes your typed text straight into its own database command, so carefully crafted text changes what the command means.
Cross-site scripting comes in two flavours. The reflected kind travels in a link and only harms whoever clicks it. The stored kind sits on the site and runs for everyone who loads the page, which makes it the more dangerous one.
A buffer overflow happens when a program accepts more data than the space set aside for it. The extra spills into neighbouring memory and can end up running the attacker's code. Memory injection gets there more directly, by planting code inside a program that is already running.
A race condition, time of check to time of use, is all about timing. The system checks that something is safe, uses it a moment later, and the attacker swaps it in between.
Here is a common mistake. A race condition means two attackers racing each other to break in first. That is not right. It is the timing gap between when a system checks a resource and when it uses it, and the attacker changes the resource inside that gap.
? Reflected or stored cross-site scripting: which one hurts more people, and why?
expect: Stored, because the script is saved on the site and runs for every visitor, while reflected only hits the person who clicks the link.
```

### Zero-day versus end-of-life
- Zero-day: UNKNOWN to the vendor, no patch yet
- Zero-day is the most dangerous type
- End-of-life (EOL): known or discoverable, support has ended
- EOL flaws will NEVER be patched
Example: Attackers find a flaw in a popular browser before its developers do
Example: An old router model the maker no longer supports
Common mix-up: If a product is end of life, its flaws must be unknown zero-days. End-of-life flaws are usually known or easy to find; the problem is that the vendor will never fix them.

```say
A zero-day is a flaw the maker has never heard of, so there is nothing to install. A fix may well arrive, but until it does you are leaning on your other defences.
End of life is the opposite problem. The flaw may be common knowledge, but the vendor has stopped supporting the product, so no fix is ever coming.
A zero-day is a secret passage the builders do not know about, while end of life is a broken lock the locksmith has retired from fixing. The picture breaks down in one place: builders can discover the passage and seal it, but the retired locksmith never comes back.
Here is a common mistake. If a product is end of life, its flaws must be unknown zero-days. That is not right. End-of-life flaws are usually known or easy to find; the problem is that the vendor will never fix them.
? Why is a zero-day often more dangerous than a well-known flaw in current software?
expect: The vendor does not know about it, so no patch or signature exists and defenders cannot simply update.
```

### Platform weaknesses
- Virtualisation: VM escape, resource reuse
- Cloud: misconfiguration, insecure APIs, IAM gaps, public storage
- Mobile: jailbreak or root, side loading of unvetted apps
- Hardware: firmware flaws, end-of-life kit
Example: Escape one VM, own the hypervisor, own ALL the VMs on it
Example: Firmware malware survives a full OS reinstall
Common mix-up: Reinstalling the operating system will clean any infection. Firmware sits below the operating system, so a firmware compromise survives a reinstall.

```say
Virtualisation's nightmare is escape. If an attacker breaks out of one virtual machine into the hypervisor underneath, every guest on that host is theirs. Resource reuse is the quieter risk, where memory or storage handed to a new machine still holds the old one's data.
In the cloud, the usual culprits are the customer's own settings: storage left public, application interfaces without proper checks, and identity permissions with gaps. Confusion over who secures what under shared responsibility is a weakness in its own right.
On phones, jailbreaking or rooting strips out the built-in protections, and side loading installs apps that no store has checked.
Hardware flaws often live in firmware, underneath the operating system, so wiping and reinstalling the system does not clear them. Old kit past end of life never gets firmware fixes at all.
Here is a common mistake. Reinstalling the operating system will clean any infection. That is not right. Firmware sits below the operating system, so a firmware compromise survives a reinstall.
? Why is breaking out of a single virtual machine so serious?
expect: The attacker reaches the hypervisor, which controls every virtual machine on that host.
? Someone installs a game from a website onto a rooted phone. Which two protections have they given up?
expect: Rooting removed the built-in operating system security, and side loading skipped the app store's vetting.
```

### Supply chain and cryptographic weaknesses
- Supply chain: hardware, software and service providers
- Compromised libraries, factory backdoors, malicious updates
- Cryptographic: weak algorithms (MD5, SHA-1), short or badly managed keys
- Downgrade attacks force an older, weaker protocol
Example: SolarWinds, 2020: a poisoned vendor update was installed by thousands of customers
Common mix-up: If we buy from a reputable vendor, supply chain risk is their problem, not ours. A compromised supplier passes its weakness straight into your systems, so you still need to assess and monitor suppliers.

```say
A supply chain weakness means you inherit someone else's problem. You can do everything right and still be hit through a provider, a code library you pulled in, or a device that left the factory with a backdoor.
A malicious update is especially nasty because it arrives through the channel you trust most, signed and expected, so it slips past people who are patching properly.
Cryptographic weaknesses come from tired algorithms such as MD5 and SHA-1, keys that are too short or poorly protected, and downgrade tricks that push a connection back onto an older protocol that can be broken.
Here is a common mistake. If we buy from a reputable vendor, supply chain risk is their problem, not ours. That is not right. A compromised supplier passes its weakness straight into your systems, so you still need to assess and monitor suppliers.
? Why does installing updates quickly fail to protect you from a malicious update?
expect: The malicious code is inside the trusted vendor update itself, so installing it is exactly how it gets in.
```

### Misconfiguration
- Factory usernames and passwords left in place (admin/admin)
- Open storage buckets: public read on cloud storage
- Unnecessary services left running
- Over-permissive access: everyone can read everything
Example: Capital One, 2019: a misconfigured cloud firewall let an attacker reach storage holding over 100 million customer records
Common mix-up: Misconfiguration is minor compared with real hacking techniques. Simple mistakes such as public storage and unchanged factory logins sit behind many of the biggest real breaches.

```say
Misconfiguration is the everyday killer. No clever exploit is needed when the door was simply left unlocked.
Factory logins like admin and admin are printed in manuals that anyone can download. Every service left running that nobody uses is one more thing that can be attacked, for no benefit at all.
Permissions are the other big one. When everyone can read everything, one stolen account exposes the lot.
Here is a common mistake. Misconfiguration is minor compared with real hacking techniques. That is not right. Simple mistakes such as public storage and unchanged factory logins sit behind many of the biggest real breaches.
? A new network printer arrives and is about to be plugged in. What two things should happen first, and why?
expect: Change its factory admin password and turn off services it does not need, because factory logins are published and unused services only add risk.
```

## Guided practice (10 min)

### Name that weakness
- Where does the weakness live: application, platform, supplier or settings?
- Then pick the specific name inside that family
Example: Comment box saves a script that runs for every reader: stored cross-site scripting

```say
Here is a method for the exam. First decide where the weakness lives. Is it in the application, the platform, a supplier, or a setting someone got wrong? Only once you know the family do you reach for the exact term the question wants.
? A hospital still runs an imaging server whose vendor stopped supporting it years ago. Zero-day or end of life?
expect: End of life: its flaws are known or discoverable but will never be patched.
```

### Scenario: Name that weakness
A retailer moves its website to the cloud. An audit finds three things: a storage bucket set to public read, the admin panel still using its factory password, and a search box that throws database errors when you type a single quote mark.

```say
Look at the scenario on the screen.
? Name each weakness, then tell me which one you would fix first and why.
expect: Public bucket is a cloud misconfiguration, the factory password is a misconfiguration, the search box suggests SQL injection. Any reasoned priority, for example the public bucket or the injection first because data could be exposed right now.
```

## Review (5 min)

### Traps to remember
- Reflected XSS = one victim; stored XSS = every visitor
- Zero-day: no patch YET. End-of-life: NEVER patched
- Firmware survives an OS reinstall
- Shared responsibility confusion counts as a cloud weakness
- VM escape = own the hypervisor = own every VM
Example: Secret passage (zero-day) versus retired locksmith (end-of-life)

```say
Let us lock in the traps. When a question says only the person who clicked was affected, think reflected. When every visitor was hit, think stored.
Watch the wording around fixes. A patch that is not available yet points to a zero-day. A patch that is never coming points to end of life.
And in the cloud, simply misunderstanding who is responsible for which setting is a weakness all by itself.
? Which family does a weak hashing algorithm such as MD5 belong to?
expect: Cryptographic weaknesses.
```

```quiz
[
 {
  "objective": "2.3",
  "type": "multiple_choice",
  "q": "A scanner reports a vulnerability that does not actually exist. What is this?",
  "options": [
   "False negative",
   "Zero-day",
   "False positive",
   "Race condition"
  ],
  "answer": "False positive",
  "why": "A false positive is an alert for a problem that is not really there; a false negative is the reverse, a real problem the scanner misses.",
  "source": "exam"
 },
 {
  "objective": "2.3",
  "type": "multiple_choice",
  "q": "A vulnerability exists because an attacker can exploit an unexpected input path. Which broad class does this represent?",
  "options": [
   "Physical control",
   "Governance framework",
   "Backup type",
   "Software vulnerability"
  ],
  "answer": "Software vulnerability",
  "why": "Flaws in how a program handles input, such as injection or overflows, are software weaknesses; the other options are not kinds of vulnerability at all.",
  "source": "exam"
 },
 {
  "objective": "2.3",
  "type": "multiple_choice",
  "q": "Why are default credentials a security concern?",
  "options": [
   "They increase attack surface and can provide an easy entry point",
   "They improve least privilege",
   "They provide non-repudiation",
   "They prevent enumeration"
  ],
  "answer": "They increase attack surface and can provide an easy entry point",
  "why": "Factory logins are published and widely known, so leaving them unchanged gives attackers a simple way in; changing them is a basic hardening step.",
  "source": "exam"
 }
]
```
