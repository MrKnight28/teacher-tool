<!-- objectives: 2.2 -->
<!-- pack-lesson: 6 -->
# Threat Vectors and Attack Surfaces

## Retrieval (5 min)

### Retrieval
Quick check on earlier material.

```say
? What clues do you look for in an email to decide whether it might be a scam?
expect: Any sensible clues, such as urgency, an odd sender address, spelling mistakes, unexpected links or requests for credentials.
? Have you ever been told not to plug in a memory stick you found? Why do you think that advice exists?
expect: It could carry malware that runs once plugged in, getting past network protections.
```

## Intro (5 min)

### Vectors and surfaces
- Threat vector: the PATH or method an attacker uses to get in
- Attack surface: the TOTAL of all possible entry points
- Every port, service, user and interface adds to the surface. Reduce it by removing things
Example: An email with a malicious link is one way in. The company's hundred staff inboxes, open ports and web forms together are everything that could be tried.

```say
Today is objective 2.2, how attackers actually get in. The exam names a long list of routes, and most questions give you a short story and ask which route it describes.
Keep the two terms apart. A vector is one road in. The surface is the whole map of roads, and the simplest way to shrink it is to switch off and remove what you do not need.
? A company shuts down three old servers nobody uses any more. Has it changed a threat vector or its attack surface, and why?
expect: Its attack surface, because it removed possible entry points; the vector is the method an attacker would use.
```

## Teaching (15 min)

### The phishing family
- Phishing: mass generic emails, like a fake bank email sent to millions
- Spear-phishing: aimed at one person, personalised, mentions your real projects
- Whaling: spear-phishing aimed at EXECUTIVES such as the CEO or CFO
- Vishing = voice calls. Smishing = SMS texts
- BEC (business email compromise): impersonating an executive by email to demand an urgent wire transfer
Example: A call claiming to be your bank's fraud team is vishing; a text saying your delivery is on hold is smishing
Common mix-up: Whaling means sending phishing emails to a very large number of people. Whaling is about big targets, not big numbers: it is personalised phishing aimed at senior executives.

```say
Think of it as a family tree. Ordinary phishing casts a wide net and hopes someone bites. Aim it at one named person, using details only an insider would know, and it becomes spear-phishing.
When the person being aimed at is a senior executive, the exam calls it whaling. When the attacker pretends to be the executive and asks finance to move money, that is business email compromise.
Vishing and smishing are named after the channel: vishing is phishing by voice call, and smishing is phishing by text message.
Here is a common mistake. Whaling means sending phishing emails to a very large number of people. That is not right. Whaling is about big targets, not big numbers: it is personalised phishing aimed at senior executives.
? What is the difference between whaling and business email compromise?
expect: Whaling targets an executive as the victim; business email compromise impersonates an executive to trick staff, usually into sending money.
? A caller pretending to be from the tax office demands payment over the phone. Which kind of phishing is that?
expect: Vishing, because it uses a voice call.
```

### Social engineering levers
- Urgency: time pressure bypasses rational thinking
- Authority: impersonating a boss, IT or the police
- Intimidation: threatening consequences
- Brand impersonation: real logos and styling of trusted brands
- Typosquatting: look-alike domains such as paypa1.com
Example: An email in the bank's exact branding, from a look-alike domain, warning that the account closes in one hour unless you log in

```say
These are the buttons attackers press to stop you thinking. A deadline rushes you, a senior title makes you obey, and a threat makes you afraid of saying no.
The last two make the message look genuine. Copying a famous brand's logo builds false trust, and a domain with one swapped character, such as the number one instead of a letter l, slips past a quick glance.
Real attacks usually stack several of these together, so in a question look for the one the wording leans on hardest.
? A caller says they are a police officer and you must hand over the account details at once. Which levers are being used?
expect: Authority, because they impersonate the police, and urgency or intimidation from the pressure and implied consequences.
```

### Files, devices and networks
- Image-based: malicious code inside image files, a SEPARATE category from file-based
- File-based: malicious documents, PDFs, macros and archives
- Removable devices: USB drops BYPASS all network defences
- Unsecure networks: open Wi-Fi, Bluetooth at close range, wired taps
- Watering hole: compromise a site the TARGET GROUP visits
Example: USB sticks labelled Salaries left in a company car park
Example: Attackers infect a forum popular with engineers at one defence firm and wait for them to visit

```say
The exam lists image-based and file-based attacks as two different vectors, so do not merge them. A poisoned picture is image-based; a booby-trapped spreadsheet or zip archive is file-based.
A dropped memory stick is powerful because it walks straight past the firewall. Someone plugs it in at their desk and the network defences never see it arrive.
With a watering hole, the attacker does not approach the victims at all. They poison somewhere the victims already trust and let them come.
A watering hole attack is like a predator waiting at the pool where its prey drinks, rather than chasing it. The picture breaks down because the attacker usually wants only certain visitors, and real attacks often check who is visiting before striking.
? Why is a dropped memory stick so effective against a company with strong firewalls?
expect: It is plugged in directly inside the organisation, so it bypasses network defences entirely.
```

### Weak spots and supply chains
- Unsupported systems: end-of-life software, permanently unpatchable
- Open service ports: every unneeded port is attack surface. Telnet on port 23!
- Default credentials such as admin and admin, never changed. Attackers keep lists
- Supply chain attacks are INDIRECT: MSPs (one breach reaches all clients), software vendors (poisoned updates), hardware suppliers (factory backdoors)
Example: In the SolarWinds attack, attackers poisoned a software update, and thousands of customers installed it themselves

```say
End of life means the vendor has stopped fixing it, so any new flaw stays open for ever. Telnet is the classic open port to spot because it sends everything, passwords included, in plain text.
Factory passwords are published in manuals, so attackers simply try them first.
A supply chain attack goes through someone you already trust. Break into one managed service provider and you reach every client it looks after. Poison one software update and the victims install the attack for you.
? Why is an end-of-life operating system a permanent risk rather than a temporary one?
expect: The vendor no longer releases patches, so newly found vulnerabilities will never be fixed.
? Name the three kinds of supplier an attacker can go through in a supply chain attack.
expect: Managed service providers, software vendors and hardware suppliers.
```

### Human and physical vectors
- Tailgating: following someone through a door, victim UNAWARE
- Piggybacking: the same, but the victim KNOWS and holds the door
- Dumpster diving: recovering information from discarded material
- Shoulder surfing: watching credentials being typed
Example: A visitor carrying boxes asks an employee to hold the secure door, and the employee does
Common mix-up: Tailgating and piggybacking are just two names for the same thing. They differ on consent: in piggybacking the authorised person knowingly lets the intruder in, in tailgating they do not notice.

```say
Tailgating and piggybacking look identical on camera. The only difference is whether the person with the badge realised someone came in behind them and let it happen.
The other two need no technical skill at all. Old printouts in a bin, or a glance over someone's shoulder on a train, can hand over exactly what an attacker needs.
Here is a common mistake. Tailgating and piggybacking are just two names for the same thing. That is not right. They differ on consent: in piggybacking the authorised person knowingly lets the intruder in, in tailgating they do not notice.
? An intruder slips through a secure door just before it closes, and the employee ahead never notices. Is that tailgating or piggybacking?
expect: Tailgating, because the employee was unaware.
```

## Guided practice (10 min)

### Naming the way in
- Ask: what was the route in?
- Ask: who was being aimed at, and through which channel?
Example: A text message with a parcel link: smishing. A call from fake IT support: vishing

```say
In each case, find the single route the attacker used before you think about anything else. Then check who was aimed at and how, because that decides the exact name.
If two answers look right, the more specific one usually wins on the exam.
? A finance clerk gets an email that looks like it is from the managing director, asking for an urgent payment to a new supplier. What would you call this?
expect: Business email compromise, because it impersonates an executive to request a wire transfer.
```

### Scenario: Naming the way in
A small accountancy firm suffers four incidents in a month. An attacker read a manager's password by standing behind her at a cafe. A printer with its factory login still set was used to reach the network. Staff downloaded an infected update from the firm's trusted payroll software vendor. A stranger followed an employee through the office door without him noticing.

```say
Look at the scenario on the screen.
? Name the vector in each of the four incidents, and say which one also shows how the firm's attack surface could have been reduced.
expect: Shoulder surfing; default credentials; supply chain attack through a software vendor; tailgating. Changing the default login, or removing unneeded services, reduces the attack surface.
```

## Review (5 min)

### Traps to remember
- Whaling = execs are the VICTIM. BEC = exec is IMPERSONATED
- Vishing = voice. Smishing = SMS
- Image-based and file-based are SEPARATE vectors
- Tailgating = unaware. Piggybacking = knowingly holds the door
- Watering hole = poison where the target group goes
Example: paypa1.com is typosquatting, not brand impersonation, because the trick is in the domain name

```say
Most mistakes in this area come from near-twins. Check who is the victim and who is being pretended to be, whether the door was held knowingly, and whether the file was a picture or a document.
And remember the bigger picture: every unneeded service or port you leave running makes the surface larger, and turning it off makes it smaller.
? What single detail separates typosquatting from brand impersonation?
expect: Typosquatting uses a look-alike domain name; brand impersonation copies the logos and styling of a trusted brand.
```

```quiz
[
 {
  "objective": "2.2",
  "type": "multiple_choice",
  "q": "A targeted phishing message is sent to one specific engineer. What phishing subtype best fits?",
  "options": [
   "Vishing",
   "Smishing",
   "Watering-hole",
   "Spear phishing"
  ],
  "answer": "Spear phishing",
  "why": "Spear phishing is personalised phishing aimed at a particular person. Vishing uses voice calls, smishing uses text messages, and a watering hole compromises a website the victims visit.",
  "source": "exam"
 },
 {
  "objective": "2.2",
  "type": "multiple_choice",
  "q": "An attacker manipulates a supplier so the supplier becomes the route into the target. What vector is this?",
  "options": [
   "Supply-chain compromise",
   "Tailgating",
   "Shoulder surfing",
   "Dumpster diving"
  ],
  "answer": "Supply-chain compromise",
  "why": "A supply chain attack is indirect: the attacker breaches a trusted MSP, software vendor or hardware supplier and reaches the real victim through it.",
  "source": "exam"
 },
 {
  "objective": "2.2",
  "type": "multiple_choice",
  "q": "Which social-engineering lever uses time pressure to rush a victim into acting?",
  "options": [
   "Least privilege",
   "Urgency",
   "Encryption",
   "Segmentation"
  ],
  "answer": "Urgency",
  "why": "Urgency creates a deadline so the victim acts before thinking. Least privilege, encryption and segmentation are defences, not social engineering levers.",
  "source": "exam"
 }
]
```
