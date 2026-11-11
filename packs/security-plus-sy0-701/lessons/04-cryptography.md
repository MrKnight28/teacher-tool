<!-- objectives: 1.4 -->
<!-- pack-lesson: 4 -->
# Cryptography

## Retrieval (5 min)

### Retrieval
Quick check on earlier material.

```say
? When you see a padlock in your browser's address bar, what do you think it is actually protecting?
expect: The connection is encrypted, protecting confidentiality and integrity in transit, and the site has a certificate that the browser accepts.
? Have you heard of storing passwords as hashes rather than as plain text? Why might that be safer?
expect: A stolen hash cannot simply be reversed to reveal the password.
```

## Intro (5 min)

### Three building blocks of cryptography
- Encryption: unreadable without the key, protects confidentiality
- Hashing: one-way fingerprint, protects integrity
- PKI: certificate authorities, certificates and keys working together
Example: A banking website uses all three at once: an encrypted connection, hashed passwords and a certificate that proves who the site is.

```say
Today is objective 1.4, and it is one of the heaviest on the exam. Almost every question in this area comes back to three ideas, so we will keep returning to them.
Encryption is about secrecy. Hashing is about spotting tampering, and it can never be undone. The public key infrastructure is the framework that lets strangers on the internet decide whether a key genuinely belongs to who it claims.
If you can name which of the three a question is really about, half the work is done.
? In your own words, what is the big difference between encrypting something and hashing it?
expect: Encryption can be reversed with the key and protects confidentiality; hashing is one-way and protects integrity.
```

## Teaching (15 min)

### Symmetric and asymmetric encryption
- Symmetric: ONE shared key encrypts and decrypts. Fast, ideal for bulk data
- Symmetric weakness: how do you share the key safely?
- Asymmetric: TWO keys, public encrypts, private decrypts. Slower
- Asymmetric is used for key exchange and digital signatures
- AES is the current symmetric standard. RSA and ECC are asymmetric. DES and 3DES are outdated
Example: In TLS, asymmetric crypto swaps a session key, then AES encrypts the actual data
Example: ECC gives the same strength as RSA with smaller keys, so it suits phones and IoT devices
Common mix-up: Asymmetric encryption is stronger, so it should be used for everything. Asymmetric encryption is much slower, so it protects the key exchange while symmetric encryption such as AES protects the data itself.

```say
Symmetric encryption is quick, which is why it carries the bulk of the data. Its weakness is getting that single key to the other side without anyone copying it on the way.
Asymmetric encryption solves that problem with a pair of keys. Anyone may hold your public key, but only you hold the private one. The price is speed, so it is rarely used for large amounts of data.
Transport Layer Security uses both. The slow asymmetric step agrees a session key, then fast symmetric encryption does the heavy lifting. If an exam answer offers DES or triple DES for a new system, treat it as the wrong answer.
Symmetric encryption is like a house key you have to copy and post to a friend; asymmetric is like a padlock you hand out open, which anyone can snap shut but only you can unlock. It breaks down because real public keys also verify signatures, which no padlock does.
Here is a common mistake. Asymmetric encryption is stronger, so it should be used for everything. That is not right. Asymmetric encryption is much slower, so it protects the key exchange while symmetric encryption such as AES protects the data itself.
? Why does a secure web connection bother with two kinds of encryption instead of just one?
expect: Asymmetric solves safe key sharing but is slow; symmetric is fast for bulk data, so asymmetric exchanges the session key and symmetric encrypts the data.
? A small sensor device needs public key encryption but has little processing power. Which algorithm fits best, and why?
expect: ECC, because it gives equivalent security to RSA with smaller keys.
```

### Hashing, signatures and passwords
- Hash: one-way, fixed-length output that cannot be reversed
- MD5 and SHA-1 are BROKEN. SHA-256 and SHA-3 are current
- Salting: random value added before hashing, defeats rainbow tables
- Key stretching: hash thousands of times (bcrypt, PBKDF2, Argon2), slows brute force
- Digital signature gives integrity, authentication and non-repudiation
Example: The sender hashes the message, encrypts the hash with their private key and sends message plus signature; the receiver decrypts with the public key and compares hashes. A match means genuine.
Common mix-up: Hashing a password is a form of encryption, so it can be decrypted with the right key. Hashing is one-way and has no key; you can only compare a fresh hash against the stored one.

```say
Whatever size the input, a hash always comes out the same length, and you cannot work backwards from it. Change one letter of the input and the result changes completely, which is exactly how tampering shows up.
For new systems, MD5 and SHA-1 are never the right choice. A rainbow table is a huge precomputed list of hashes, and a random salt makes that list useless. Key stretching deliberately makes each guess slow.
A signature works because only the sender holds the private key. If the public key opens it and the hashes match, you know who sent it, that nothing changed, and the sender cannot later deny it.
Here is a common mistake. Hashing a password is a form of encryption, so it can be decrypted with the right key. That is not right. Hashing is one-way and has no key; you can only compare a fresh hash against the stored one.
? In a digital signature, which key does the sender use, and which key does the receiver use?
expect: The sender uses their own private key; the receiver uses the sender's public key.
? What does adding a salt to each password before hashing actually stop an attacker from doing?
expect: Using precomputed rainbow tables, because identical passwords no longer produce the same hash.
```

### PKI chain of trust and certificates
- Root CA: self-signed, kept OFFLINE
- Intermediate CA: does the day-to-day issuing
- End-entity certificate: your website's certificate
- Certificate (X.509): public key, identity, validity dates, CA signature
- CSR asks a CA to issue a cert. CRL is a downloaded list, NOT real time. OCSP checks in real time
Example: Wildcard *.example.com covers the subdomains. A self-signed cert has no CA vouching for it, so browsers reject it by default
Example: With key escrow, a trusted third party keeps a copy of a key for authorised recovery
Common mix-up: A certificate revocation list tells you instantly when a certificate has been revoked. The list is downloaded periodically, so it can be out of date; OCSP is the real-time check.

```say
Your browser ships with a short list of root authorities it already believes in. The root signs an intermediate, the intermediate signs the website's certificate, and your browser walks up those links until it reaches a root it knows.
The root is kept offline because if it were ever compromised, every certificate beneath it would become worthless. The intermediates take the daily risk instead.
For revocation, remember that a list is only as fresh as the last download, while the online status protocol answers in real time at the cost of extra traffic.
Here is a common mistake. A certificate revocation list tells you instantly when a certificate has been revoked. That is not right. The list is downloaded periodically, so it can be out of date; OCSP is the real-time check.
? Why would an organisation keep its root certificate authority switched off and disconnected most of the time?
expect: If the root were compromised, every certificate under it would be untrusted; intermediates do the daily issuing so the root stays protected.
? What does a certificate actually contain that lets a browser check it?
expect: The subject's public key, identity, validity dates and the issuing authority's signature, in X.509 format.
```

### Obfuscation and crypto hardware
- Steganography hides the EXISTENCE of data
- Tokenisation: random token, NO mathematical link to the original. Real data sits in a vault
- Data masking obscures data but keeps the format
- TPM: chip ON the motherboard, device-level keys, enables BitLocker
- HSM: separate dedicated appliance for enterprise and CA-scale key management
Example: A secret message inside a JPEG; a card number swapped for a token; XXXX-XXXX-XXXX-1234 on a receipt
Example: A laptop's full disk encryption uses its TPM; a certificate authority stores its signing keys in an HSM
Common mix-up: Steganography encrypts the hidden message so nobody can read it. Steganography hides that the message exists at all; it does not scramble it, although it can be combined with encryption.

```say
These techniques hide rather than scramble. Steganography is like invisible ink: nobody even knows a message is there. Masking is the blurred face in a photo, where you still see the shape but not the detail.
Tokenisation is the one people confuse with encryption. A token is random, so there is no maths to reverse it. The only way back is to look it up in the vault.
For hardware, a Trusted Platform Module protects keys for one device, while a hardware security module serves a whole organisation.
Tokenisation works like a coat check ticket: the ticket number tells a thief nothing about your coat, and only the cloakroom can swap it back. The comparison breaks down because a real vault is a database that must itself be heavily protected.
Here is a common mistake. Steganography encrypts the hidden message so nobody can read it. That is not right. Steganography hides that the message exists at all; it does not scramble it, although it can be combined with encryption.
? An online shop wants to stop storing real card numbers but still needs to process refunds. Which technique fits, and why is it not encryption?
expect: Tokenisation; the token is random with no mathematical link, and the real number is kept in a separate vault.
? What is the practical difference between a Trusted Platform Module and a hardware security module?
expect: A TPM is a chip in one device protecting that device's keys; an HSM is a separate appliance managing keys at enterprise or CA scale.
```

### Key exchange, PFS and blockchain
- Diffie-Hellman: two parties agree a shared secret over an untrusted network
- DHE and ECDHE are the ephemeral versions: a new key for every session
- PFS: past sessions CANNOT be decrypted even if the private key leaks later
- Blockchain: immutable chained hashes. Alter one block and the chain breaks
Example: A server's private key is stolen next year. With ephemeral keys, recorded traffic from this year still cannot be read.

```say
Diffie-Hellman is clever because the shared secret is never sent across the wire. Each side combines public values with its own secret and both arrive at the same answer.
The ephemeral versions throw each session key away when the session ends. That is what gives perfect forward secrecy, because there is nothing left for a thief to use on old recordings.
Blockchain is really a hashing idea. Each block includes the hash of the one before, so changing any block breaks every link that follows it.
? Why does using a brand new key for every session protect conversations that have already finished?
expect: Each session key is discarded, so stealing the long-term private key does not reveal the old session keys or the recorded traffic.
```

## Guided practice (10 min)

### Choosing the right tool
- Ask first: is it confidentiality, integrity, trust or hiding?
- Then pick the strongest current option, never MD5, SHA-1, DES or 3DES
Example: Storing passwords calls for a salted hash with key stretching such as bcrypt or Argon2

```say
Work through the scenario the way the exam expects. Decide which property each requirement needs before you think about any product or algorithm.
Watch for the outdated options. They often appear as distractors because they sound familiar.
? A developer suggests storing passwords with plain SHA-256 and nothing else. What would you add, and why?
expect: A unique salt per password to defeat rainbow tables, and key stretching such as bcrypt, PBKDF2 or Argon2 to slow brute force.
```

### Scenario: Choosing the right tool
A small online retailer is launching a new site. They need customers' traffic protected in transit, customers' card numbers kept out of their own database, the encryption keys for their payment system held in tamper-resistant hardware, and staff laptops encrypted if stolen.

```say
Look at the scenario on the screen.
? Pick the right technique or device for each of the four needs, and say why.
expect: TLS with asymmetric key exchange then AES for traffic; tokenisation for card numbers; an HSM for the payment keys; the TPM with BitLocker for laptops.
```

## Review (5 min)

### Key distinctions and traps
- Encryption = confidentiality. Hashing = integrity. Signature = integrity, authentication, non-repudiation
- Sign with YOUR private key. Encrypt for someone with THEIR public key
- CRL = periodic list. OCSP = real time
- TPM = safe in the wall. HSM = bank vault
- Hide: steganography. Swap: tokenisation. Blur: masking
Example: MD5, SHA-1, DES or 3DES as an answer for a new system is a trap

```say
The commonest slip is the key direction. Your private key proves it was you; someone else's public key lets you send them a secret only they can open.
Keep the hardware picture in mind. One protects a single machine like a safe built into the wall, the other protects a whole organisation like a bank vault.
And when a question says real time, think of the online status protocol rather than the downloaded list.
? If you want to send a file that only one colleague can open, whose key do you encrypt it with?
expect: The colleague's public key, so only their private key can decrypt it.
? What is the difference between tokenisation and data masking?
expect: Tokenisation replaces the data with a random token and keeps the original in a vault; masking just obscures part of the data while keeping its format.
```

```quiz
[
 {
  "objective": "1.4",
  "type": "multiple_choice",
  "q": "Which cryptographic mechanism is designed to produce a fixed-length digest for integrity checking?",
  "options": [
   "Encryption",
   "Hashing",
   "Key exchange",
   "Certificate revocation"
  ],
  "answer": "Hashing",
  "why": "A hash function turns any input into a fixed-length, one-way digest, so comparing digests shows whether data has changed. Encryption protects confidentiality and can be reversed with a key.",
  "source": "exam"
 },
 {
  "objective": "1.4",
  "type": "multiple_choice",
  "q": "What does the PKI chain of trust provide?",
  "options": [
   "A way to make passwords longer",
   "A replacement for access control",
   "A trust relationship from a certificate to a trusted authority",
   "Physical destruction of keys"
  ],
  "answer": "A trust relationship from a certificate to a trusted authority",
  "why": "Each certificate is signed by the one above it, up to a root CA the browser already trusts, so a site certificate can be traced to a known authority.",
  "source": "exam"
 },
 {
  "objective": "1.4",
  "type": "multiple_choice",
  "q": "What is the main goal of perfect forward secrecy (PFS) when it is used in a key exchange?",
  "options": [
   "Eliminate the need for certificates",
   "Make hashes reversible",
   "Replace authentication",
   "Make old sessions safe if a long-term key is later exposed"
  ],
  "answer": "Make old sessions safe if a long-term key is later exposed",
  "why": "With ephemeral key exchange such as DHE or ECDHE, every session uses a fresh key that is thrown away, so a private key stolen afterwards cannot decrypt recorded past sessions.",
  "source": "exam"
 }
]
```
