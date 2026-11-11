<!-- objectives: 2.1 -->
<!-- pack-lesson: 5 -->
# Threat Actors

## Retrieval (5 min)

### Retrieval
Quick check on earlier material.

```say
? Think of a cyber attack you have heard about in the news. Who do you think was behind it, and what did they want?
expect: Any reasonable example naming an attacker type and a motive, such as a ransomware gang wanting money.
? Why might an employee be just as dangerous to a company as an outside hacker?
expect: They already have access inside, so they do not need to break through external defences.
```

## Intro (5 min)

### What makes a threat actor
- Threat actor: any person or group that poses a threat
- Four attributes: internal or external, funding, sophistication, motivation
- Six actors to know: nation-state, organised crime, hacktivist, insider, unskilled attacker, shadow IT
Example: A disgruntled ex-employee and a government spy agency are both threat actors, but they score completely differently on all four attributes.

```say
Today is objective 2.1, the people behind attacks. The exam rarely asks you to define an attacker; it describes one and expects you to recognise who it is.
The trick is to profile them with four questions. Are they inside or outside the organisation? How much money do they have? How skilled are they? And what do they want?
Learn the pattern of answers for each group and most questions in this area become straightforward.
? Name the four attributes you can use to describe any attacker.
expect: Internal or external, resources or funding, sophistication or skill, and motivation.
```

## Teaching (15 min)

### Nation-states and organised crime
- Nation-state: government-backed, unlimited funding, very high skill
- Nation-state goals: espionage and war. Months of hidden access
- APT = advanced PERSISTENT threat. Long dwell time is the signature, usually a nation-state
- Organised crime: external, well funded, high skill, money is the only goal
- Ransomware run as a business
Example: SolarWinds, a nation-state campaign that sat hidden inside networks for months
Example: REvil, a ransomware gang run like a company, with affiliates and profit shares
Common mix-up: Any attack that uses ransomware must be the work of organised crime. Ransomware is a strong hint of organised crime, but the tool alone does not prove who is behind it; look at the motive and the other clues.

```say
Both groups are outsiders with deep pockets and real skill, so the way to separate them is what they want. A government wants secrets or the ability to disrupt another country. A criminal gang wants to be paid.
The word persistent is the giveaway for an advanced persistent threat. If a question describes attackers quietly staying inside a network for months, think nation-state.
Pinning an attack on a particular group or country is rarely certain. Skilled groups reuse each other's tools and sometimes plant false clues to point investigators at someone else.
Here is a common mistake. Any attack that uses ransomware must be the work of organised crime. That is not right. Ransomware is a strong hint of organised crime, but the tool alone does not prove who is behind it; look at the motive and the other clues.
? Both a nation-state and an organised crime group are external, rich and skilled. What is the clearest way to tell them apart in a question?
expect: Their motivation: nation-states want espionage or disruption, organised crime wants money.
? What does the word persistent tell you about an advanced persistent threat?
expect: The attacker stays hidden inside the network for a long time, a long dwell time.
```

### Hacktivists and unskilled attackers
- Hacktivist: variable skill, ideological, acts for a CAUSE
- Hacktivist methods: defacement, DDoS, leaks
- Unskilled attacker (script kiddie): low skill, uses pre-built tools
- Unskilled attacker motive: notoriety or curiosity. Still dangerous
Example: Anonymous defacing a government website to protest a policy
Example: A teenager running a downloaded attack tool against a school network to see what happens
Common mix-up: A script kiddie has no real skill, so they are not a genuine threat. Their skill is low but the tools they borrow are effective, so they can still cause serious harm.

```say
Hacktivists want attention for their beliefs, so their attacks are loud. Defacing a website, knocking it offline with a flood of traffic, or leaking embarrassing documents all send a public message.
An unskilled attacker borrows tools other people wrote. Do not dismiss them on the exam. Pre-built tools can be very powerful, and running them carelessly can still cause real damage.
Here is a common mistake. A script kiddie has no real skill, so they are not a genuine threat. That is not right. Their skill is low but the tools they borrow are effective, so they can still cause serious harm.
? A group leaks a company's internal emails to embarrass it over its environmental record, and asks for nothing. Which kind of attacker does that suggest?
expect: A hacktivist, because the motive is a cause or belief, not money.
```

### Insiders and shadow IT
- Insider threat: has AUTHORISED access, so bypasses the perimeter
- Insiders can be malicious or accidental. Motives: revenge or money
- Shadow IT: unauthorised tools used for convenience
- Shadow IT is internal, usually NOT malicious, but an unmanaged risk
Example: A sacked administrator deletes backups on their last day
Example: A team shares client files through a personal cloud storage account because the approved system is slow

```say
The insider is dangerous for one reason: they are already inside. Firewalls and perimeter defences are built to keep outsiders out, so they do little against someone with a valid login.
Not every insider means harm. Someone who clicks the wrong thing or emails the wrong file is still an insider threat.
Shadow IT is the odd one out on the list. Nobody is trying to attack anything; staff are simply getting work done with tools the security team cannot see or manage.
? Why can perimeter defences such as a firewall do so little against an insider?
expect: The insider already has authorised access inside the network, so they never need to cross the perimeter.
? If shadow IT is not malicious, why is it still counted as a threat?
expect: The tools are unmanaged and unknown to security, so data in them is unprotected and unmonitored.
```

### Matching motive to actor
- Financial gain or blackmail: organised crime, malicious insiders
- Espionage: nation-states, corporate competitors
- War or disruption of infrastructure: nation-state
- Philosophical or political beliefs: hacktivists
- Revenge: disgruntled current or former employees. Ethical: researchers, bug bounty hunters. Notoriety: unskilled attackers
Example: A rival firm paying someone to copy a competitor's product designs is espionage, even though no government is involved
Common mix-up: Espionage always means a foreign government is involved. Corporate competitors also carry out espionage to steal trade secrets.

```say
When a question gives you a motive, work backwards to the attacker. Money points to criminals or a greedy insider. Beliefs point to hacktivists. Shutting down a power grid points to a government.
Two motives catch people out. Espionage is not only for governments, because businesses spy on rivals too. And ethical hacking is a motive as well: researchers and bug bounty hunters break in to report flaws, not to exploit them.
Here is a common mistake. Espionage always means a foreign government is involved. That is not right. Corporate competitors also carry out espionage to steal trade secrets.
? Which motive on the list belongs to people who are trying to help the organisation they attack?
expect: Ethical, such as security researchers and bug bounty hunters.
```

## Guided practice (10 min)

### Profiling an attacker
- Inside or outside?
- Funding and skill: low, high or very high?
- What do they want?
Example: Inside, low skill, no harm meant, convenience: shadow IT

```say
Use the same four questions every time. Start with inside or outside, because that alone cuts the list roughly in half.
Then let the motive settle it. Skill and funding usually confirm the answer rather than decide it.
? An attacker is outside the company, has huge resources, and wants to disable a country's water treatment plants. Who is it most likely to be?
expect: A nation-state, because the motive is disruption of infrastructure and the resources are very high.
```

### Scenario: Profiling an attacker
A hospital finds three problems in one month. Attackers who had been hiding in the network for eight months were copying research data. A former IT contractor used an old account to wipe a server after being let go. Nurses were found sharing patient lists in a free messaging app because it was quicker than the official system.

```say
Look at the scenario on the screen.
? Profile the attacker behind each of the three problems using the four attributes, and name each one.
expect: Long hidden access copying research: nation-state or APT, external, very high skill and funding, espionage. Wiped server: malicious insider, internal, revenge. Messaging app: shadow IT, internal, low skill, convenience, not malicious.
```

## Review (5 min)

### The attribute matrix
- Nation-state: external, VERY high funding and skill, espionage or war
- Organised crime: external, high funding and skill, FINANCIAL
- Hacktivist: external, low to mid funding, variable skill, IDEOLOGICAL
- Insider: internal, low funding, low to mid skill, revenge or money
- Unskilled attacker: external, very low everything, notoriety. Shadow IT: internal, low, convenience
Example: Long hidden presence = APT. Authorised access = insider. Unapproved app = shadow IT

```say
Notice the pattern. Funding and skill are highest for nation-states and lowest for unskilled attackers and shadow IT, and only two of the six are internal.
The traps are usually the motives. Money means criminals or a greedy insider, a cause means hacktivists, and showing off means an unskilled attacker. Shadow IT is the one with no bad intent at all.
? Which two of the six attackers are internal, and which of those usually means no harm?
expect: Insiders and shadow IT are internal; shadow IT is usually not malicious.
? A group wants to be noticed and boast online, but uses only tools it downloaded. Which attacker fits?
expect: An unskilled attacker, sometimes called a script kiddie, motivated by notoriety.
```

```quiz
[
 {
  "objective": "2.1",
  "type": "multiple_choice",
  "q": "Which actor is primarily motivated by financial gain?",
  "options": [
   "Cybercriminal",
   "Hacktivist",
   "Nation-state",
   "Security researcher"
  ],
  "answer": "Cybercriminal",
  "why": "Cybercriminals, such as organised crime groups running ransomware, attack for money. Hacktivists want a cause, nation-states want espionage or disruption, and researchers are ethical.",
  "source": "exam"
 },
 {
  "objective": "2.1",
  "type": "multiple_choice",
  "q": "Which actor is associated with ideological or social causes?",
  "options": [
   "Insider only",
   "Hacktivist",
   "Script kiddie only",
   "Vendor"
  ],
  "answer": "Hacktivist",
  "why": "Hacktivists act on political or philosophical beliefs, using defacement, DDoS and leaks to promote a cause.",
  "source": "exam"
 },
 {
  "objective": "2.1",
  "type": "multiple_choice",
  "q": "Why is actor attribution difficult?",
  "options": [
   "Every actor uses the same tools",
   "Logs cannot exist",
   "Techniques and infrastructure can overlap or be deliberately misleading",
   "Only nation-states use malware"
  ],
  "answer": "Techniques and infrastructure can overlap or be deliberately misleading",
  "why": "Different groups reuse the same tools and servers, and skilled attackers can plant false clues, so evidence may point to the wrong group.",
  "source": "exam"
 }
]
```
