<!-- objectives: 4.6 -->
<!-- pack-lesson: 12 -->
# Identity and Access Management

## Retrieval (5 min)

### Retrieval
Quick check on earlier material.

```say
? When you use a bank app that sends a code to your phone after your password, what is that extra step trying to prove?
expect: That you also physically hold your phone, a second kind of proof beyond the password.
? Why do you think companies don't just give everyone admin rights to save time?
expect: Because a stolen or misused admin account can do far more damage; people should only have the access they need.
```

## Intro (5 min)

### Who are you, and what can you do?
- Proving identity, granting permissions, keeping records
- Factors, protocols, access control models, admin account controls
- Domain 4.6: heavily scenario-based on the exam
Example: A nurse logs in with a smart card and PIN, opens patient records, and every view is logged

```say
Today is all about identity: how a system decides you are really you, what you are then allowed to touch, and how it keeps a record of what you did.
Expect the exam to hand you a short story, say a login method or a network sign-in, and ask you to name the right term. Precise vocabulary wins those marks.
? Think about logging into your own laptop. What does the computer actually check before it lets you in?
expect: It checks that you can prove who you claim to be, for example a password, PIN or fingerprint matching the account.
```

## Teaching (15 min)

### AAA and the identity flow
- Authentication: PROVING you are who you claim
- Authorisation: what you are PERMITTED to do, after proving it
- Accounting: RECORDING what you did, the audit trail
- Flow, always in order: identify, authenticate, authorise, account
Example: Type a username (identify), enter the password (authenticate), get read-only access to a share (authorise), the file opens are logged (account)
Common mix-up: Typing in my username is the authentication step. A username is only a claim of identity, which is identification; authentication is the proof that follows, such as the password.

```say
Three words that sound alike and get swapped on the exam. Authentication is the proof step. Authorisation only happens once the proof has succeeded, and it decides your permissions. Accounting is the paper trail left behind.
Notice the flow starts one step earlier, with identification. Typing a username is just a claim; anyone can type a name. It becomes trustworthy only when you back it up with proof.
Here is a common mistake. Typing in my username is the authentication step. That is not right. A username is only a claim of identity, which is identification; authentication is the proof that follows, such as the password.
? A log shows that a contractor opened the payroll folder at 2am. Which of the three A's produced that record?
expect: Accounting, because it records what the user did and builds the audit trail.
? Why can authorisation never happen before authentication?
expect: Permissions belong to an identity, so the system must first prove who you are before deciding what you may do.
```

### Authentication factors, MFA and biometric errors
- Know (knowledge): password, PIN, security question
- Have (possession): smart card, hardware token, phone
- Are (inherence): fingerprint, retina, face, voice. Somewhere you are (location): GPS, IP range. Something you do (behaviour): typing pattern, gait
- MFA rule: factors from DIFFERENT categories. Password plus PIN is still ONE factor
- FAR: wrong person ACCEPTED, a security risk. FRR: right person REJECTED, a usability problem. Lower CER is better
Example: Password plus a code from a phone app is MFA; password plus a security question is not
Example: Turning a fingerprint reader's sensitivity up makes it reject more genuine staff but let fewer impostors in
Common mix-up: Two passwords make a login multi-factor because there are two steps. Both are knowledge, the same category, so it is still single-factor no matter how many steps there are.

```say
There are five families of proof: what you know, what you hold, what your body is, where you are, and how you behave. Multi-factor authentication only counts when the proofs come from different families.
That is the classic trap. A password and a PIN are both memorised, so stacking them gives you two of the same kind, which is still single-factor.
Biometrics make two kinds of mistake. The false acceptance rate is impostors getting in, which hurts security. The false rejection rate is genuine people locked out, which hurts usability. Tightening sensitivity trades one for the other.
Where the two rates meet is the crossover error rate, also called the equal error rate. When comparing biometric products, pick the one whose crossover point is lowest.
Here is a common mistake. Two passwords make a login multi-factor because there are two steps. That is not right. Both are knowledge, the same category, so it is still single-factor no matter how many steps there are.
? A bank lets you in from a recognised home IP address plus your password. Is that genuinely multi-factor, and why?
expect: Yes, because location and knowledge are different categories.
? Which biometric error worries a security team most, and which one annoys the users?
expect: False acceptance worries security because impostors get in; false rejection annoys users because genuine people are refused.
```

### Identity protocols
- SAML: XML-based web SSO and federation. IdP authenticates, the SP trusts its assertion
- OAuth 2.0: AUTHORISATION only, delegated access without sharing credentials. OIDC: authentication layer ON TOP of OAuth
- Kerberos: Windows Active Directory, TICKETS not passwords. KDC issues a TGT, then service tickets
- LDAPS: encrypted directory queries on port 636. Plain LDAP on 389 is insecure
- RADIUS: network access, combines authentication and authorisation, encrypts the password only. TACACS+: Cisco, SEPARATES all three, encrypts the ENTIRE payload
Example: Sign in with Google on a shopping site is OpenID Connect; letting a printing app read your photos without giving it your password is OAuth
Common mix-up: OAuth logs you in, so it is an authentication protocol. OAuth only grants delegated permissions; the login part comes from OpenID Connect built on top of it.

```say
Security Assertion Markup Language is the older web single sign-on standard. An identity provider checks who you are, then hands the website a signed statement, and the website simply trusts it.
OAuth is the one that catches people out. It hands out permission tokens, so it is about authorisation, not proving identity. OpenID Connect adds the missing identity layer on top.
Kerberos is how Windows domains avoid sending passwords around. You get a ticket-granting ticket once, then swap it for tickets to each service you use.
For network devices, Remote Authentication Dial-In User Service bundles everything together and only hides the password. The Cisco alternative, TACACS plus, keeps the three A's separate and encrypts the whole body of the message, which makes it the better choice for administering routers and switches.
Here is a common mistake. OAuth logs you in, so it is an authentication protocol. That is not right. OAuth only grants delegated permissions; the login part comes from OpenID Connect built on top of it.
? An exam scenario says a protocol uses tickets and a key distribution centre. Which protocol is it?
expect: Kerberos.
? A company wants directory lookups to stop crossing the network in clear text. What should they move to, and on which port?
expect: LDAP secured with TLS, called LDAPS, on port 636 instead of plain LDAP on 389.
```

### Access control models
- DAC (discretionary): the OWNER decides, e.g. Windows file permissions
- MAC (mandatory): the SYSTEM enforces labels, users cannot change them, e.g. military
- RBAC (role-based): access by JOB ROLE, e.g. every nurse gets patient records
- ABAC (attribute-based): MANY attributes at once, such as role, time, location, device
- Rule-based: predefined rules applied to everyone, e.g. firewall ACLs
Example: Finance staff can open the ledger only from a company laptop, in the UK, between 8am and 6pm: several attributes, so ABAC
Common mix-up: Role-based and rule-based are the same thing because both start with the letter R. Role-based grants access by job title, while rule-based applies fixed conditions, such as firewall rules, to everyone.

```say
Ask yourself who makes the decision. If the person who created the file decides, that is discretionary. If the operating system enforces classification labels and nobody can override them, that is mandatory.
Role-based control asks one question: what is your job? Attribute-based control asks many: what is your job, what time is it, where are you, and is this a managed device?
Rule-based control is the odd one out. It does not care who you are at all; a fixed list of rules is checked, top to bottom, like a firewall access control list.
Here is a common mistake. Role-based and rule-based are the same thing because both start with the letter R. That is not right. Role-based grants access by job title, while rule-based applies fixed conditions, such as firewall rules, to everyone.
? Documents are labelled Secret and Top Secret, and a user cannot share a file with a colleague even though they wrote it. Which model is that?
expect: Mandatory access control, because the system enforces labels that users cannot change.
? What is the difference in the questions asked by role-based and attribute-based control?
expect: Role-based asks only about your job role; attribute-based weighs several attributes such as role, time, location and device.
```

### Privileged access management (PAM) and account hygiene
- JIT access: admin rights ONLY when needed, auto-revoked. NO standing privileges
- Password vaulting: admin passwords kept in a vault, users never see them
- Session recording: every admin session recorded for audit
- Deprovisioning: remove access IMMEDIATELY on leaving. Delay means logic bomb risk
- Permission creep: old access never removed, fixed by access reviews. Shared accounts: NEVER
Example: An engineer requests domain admin for a two-hour change window; the vault checks out a password she never sees, records the session, then revokes the rights
Common mix-up: It is fine to disable a leaver's account at the end of the month with the other admin tasks. Access must be removed the moment employment ends, because a disgruntled leaver with live access can cause damage such as a logic bomb.

```say
Privileged access management, or PAM, wraps tight controls around the most powerful accounts in the organisation, the admin and root logins that could wreck everything if stolen.
Just-in-time means nobody carries admin rights around all day. You ask, you get them for a short window, and they vanish automatically. If an attacker steals your account on an ordinary afternoon, there is nothing powerful to steal.
Watch the account lifecycle too. A sacked employee who still has access can plant a logic bomb, and someone who has moved jobs three times may still hold every old permission. Regular access reviews catch that creep.
Shared logins are banned because the log can only say the shared account did it, never which person. That destroys accountability and non-repudiation.
Here is a common mistake. It is fine to disable a leaver's account at the end of the month with the other admin tasks. That is not right. Access must be removed the moment employment ends, because a disgruntled leaver with live access can cause damage such as a logic bomb.
? Why does just-in-time access reduce the damage from a stolen admin account?
expect: Because there are no standing privileges; admin rights exist only briefly when approved, so a stolen account usually has none.
? What is the main security problem with a shared admin login?
expect: You cannot tell which person did what, so accountability and non-repudiation are lost.
```

## Guided practice (10 min)

### Securing a new hospital system
- Pick the factors, the protocol and the access control model
- Name the admin account controls
Example: Smart card plus PIN for clinicians; role-based records access; just-in-time admin rights for IT

```say
Let's put the pieces together. Read the scenario, then talk me through each decision in order: how staff prove who they are, how they get into the web apps, what they are allowed to see, and how IT admins are kept in check.
There is more than one good answer, so justify each choice with the term you would expect to see on the exam.
? Clinicians currently log in with a password and a memorable word. What is wrong with that?
expect: Both are knowledge, so it is single-factor; add a different category such as a smart card or fingerprint.
```

### Scenario: Securing a new hospital system
A hospital is rolling out a web-based records system. Clinicians must sign in once and reach several web apps. Nurses need patient records but not payroll. Two IT admins share one admin login, and a porter who left last month can still badge into the server room.

```say
Look at the scenario on the screen.
? What would you change about sign-in, single sign-on, access to records, and the admin and leaver problems, and which term names each fix?
expect: Use two factors from different categories such as smart card and PIN; SAML or OpenID Connect for web single sign-on; role-based access so nurses get records but not payroll; give each admin a named account with just-in-time rights, vaulting and session recording instead of a shared login; deprovision leavers immediately and run access reviews.
```

## Review (5 min)

### Key distinctions and traps
- Identify, authenticate, authorise, account: in that order
- Same category twice is NOT multi-factor
- OAuth authorises, OIDC authenticates on top of it
- RADIUS encrypts the password only; TACACS+ encrypts everything
- DAC owner, MAC labels, RBAC job, ABAC many attributes, rule-based fixed rules
Example: FAR lets the wrong person in, FRR keeps the right person out, lowest CER wins

```say
If you remember nothing else: proof comes before permission, and permission comes before the log entry.
On factor questions, sort each item into its family first, then see whether the families differ. On protocol questions, look for the giveaway word: tickets, assertion, delegated, port 636, or whole packet encrypted.
And for the most powerful accounts, the answer is almost always no standing admin rights, no shared logins, and immediate removal when someone leaves.
? Give me one word that points straight to Kerberos, and one that points to SAML.
expect: Tickets for Kerberos; assertion, or XML-based web single sign-on, for SAML.
```

```quiz
[
 {
  "objective": "4.6",
  "type": "multiple_choice",
  "q": "Which authentication factor category is something you have?",
  "options": [
   "Knowledge",
   "Possession",
   "Inherence",
   "Location"
  ],
  "answer": "Possession",
  "why": "Possession covers things you physically hold, such as a smart card, hardware token or phone. Knowledge is something you know, inherence is something you are, and location is somewhere you are.",
  "source": "exam"
 },
 {
  "objective": "4.6",
  "type": "multiple_choice",
  "q": "Which access-control model is based on roles assigned to users?",
  "options": [
   "DAC only",
   "Physical access only",
   "RBAC",
   "Accounting"
  ],
  "answer": "RBAC",
  "why": "Role-based access control grants permissions according to a user's job role, so everyone in the same role gets the same access.",
  "source": "exam"
 },
 {
  "objective": "4.6",
  "type": "multiple_choice",
  "q": "What is PAM designed to manage?",
  "options": [
   "Public web pages",
   "Backup media only",
   "Network cabling",
   "Accounts with elevated rights"
  ],
  "answer": "Accounts with elevated rights",
  "why": "Privileged access management protects and monitors administrator and root-level accounts using tools such as just-in-time rights, password vaulting and session recording.",
  "source": "exam"
 }
]
```
