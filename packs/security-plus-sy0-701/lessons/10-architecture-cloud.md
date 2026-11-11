<!-- objectives: 3.1,3.2 -->
<!-- pack-lesson: 10 -->
# Architecture and Cloud

## Retrieval (5 min)

### Retrieval
Quick check on earlier material.

```say
? What do you already know about the difference between software, platform and infrastructure as a service?
expect: SaaS is a ready-made application, PaaS is a platform to deploy your own apps, IaaS is raw virtual servers you manage.
? What does a firewall do, in one sentence?
expect: It allows or blocks network traffic according to rules.
```

## Intro (5 min)

### Why architecture is a security decision
- Who secures what in the cloud
- Special environments: IoT, SCADA, RTOS, embedded, containers, serverless
- Where firewalls, proxies and sensors sit
- Fail open or fail closed
- Modern network ideas and secure protocol swaps
Example: Every server you put on the internet adds to the attack surface

```say
Today is about design choices. Each time an organisation picks a cloud model, connects a smart device or puts a server in front of the public, it changes how much an attacker can reach.
That reachable area is called the attack surface. Good architecture shrinks it, and careless architecture grows it without anyone noticing.
The exam loves short scenario questions here, so we will keep asking one thing: who is responsible, and where should the control sit?
? In your own words, what is an attack surface?
expect: Everything exposed that an attacker could reach or target; design choices make it bigger or smaller.
```

## Teaching (15 min)

### Shared responsibility and the cloud stack
- Shared responsibility: security duties split between provider and customer
- SaaS: you manage data and user access only
- PaaS: you manage applications and data
- IaaS: you manage the OS, applications and data
- Confusion over the split is a listed vulnerability
Example: Microsoft 365 is SaaS: the provider patches everything, but you still decide who gets an account and what is shared
Common mix-up: If we move to a cloud service, the provider takes care of all the security for us. The provider secures its part of the stack, but the customer always keeps responsibility for its data and access settings, and more besides in platform or infrastructure services.

```say
In the cloud, security is never handed over completely. The provider and the customer each own a slice, and the size of your slice depends on the service you buy.
Picture a stack of layers from the physical building up to your data. With software as a service, the provider runs almost the whole stack. With infrastructure as a service, you take over the operating system and everything above it.
Notice what never moves: your data and who can access it are always yours. When a company assumes the provider is handling something it is not, settings get left open, and that gap is exactly where breaches happen.
Software as a service is a fully furnished serviced apartment, platform as a service is a house with walls and a roof that you furnish, and infrastructure as a service is an empty plot where you build. It breaks down because even in infrastructure as a service the provider still supplies the physical servers, network and virtualisation, so the plot already has utilities connected.
Here is a common mistake. If we move to a cloud service, the provider takes care of all the security for us. That is not right. The provider secures its part of the stack, but the customer always keeps responsibility for its data and access settings, and more besides in platform or infrastructure services.
? Which cloud model gives the customer the most control, and what extra work comes with that?
expect: IaaS; the customer must manage and patch the operating system, applications and data.
? Name one thing the customer is responsible for in every cloud model.
expect: Their data, and user access to it.
```

### Special environments
- IoT: weak authentication, default credentials, rarely patched, so segment it
- SCADA and ICS: industrial control, attacks cause physical damage
- RTOS: real-time systems where availability comes first
- Embedded: built-in computers that cannot run security agents
- Containers share the host kernel; serverless still leaves you the code and permissions
Example: Stuxnet damaged industrial centrifuges by attacking their control systems
Example: A smart TV on the staff network is a stepping stone; on its own segment it is contained
Common mix-up: Serverless means there is nothing left for us to secure. The provider runs the infrastructure, but the customer still owns the code it deploys and the permissions that code is given.

```say
Some systems cannot be protected the normal way. Smart devices ship with factory passwords and rarely get updates, so the safe answer is nearly always to put them on their own separate network.
Industrial control systems run power plants and factories. A successful attack there does not just leak data, it can break real machinery, which is why Stuxnet is the famous example.
Real-time operating systems run things like medical devices and aircraft, where a delay can cost lives, so availability beats everything. Embedded devices like printers often cannot take an antivirus agent, so you protect the network around them instead.
Containers are lighter than virtual machines because they share the host's kernel, which also means weaker isolation and a risk of escape. With serverless, the provider runs the servers, but your code and its permissions are still yours to secure.
Here is a common mistake. Serverless means there is nothing left for us to secure. That is not right. The provider runs the infrastructure, but the customer still owns the code it deploys and the permissions that code is given.
? Why are containers considered less isolated than virtual machines?
expect: They share the host operating system kernel, so a container escape can affect the host and other containers.
? For a real-time system in a hospital, which part of the CIA triad usually comes first, and why?
expect: Availability, because a delay or outage could harm patients.
```

### The screened subnet and where appliances sit
- Screened subnet (DMZ): public servers between two firewalls
- Jump server: the single audited door for admin access
- Forward proxy filters outbound; reverse proxy filters inbound
- WAF sits in front of web servers specifically
- IDS or IPS sits inside, behind the firewall
Example: Internet, then firewall, then DMZ with web, mail and DNS servers, then firewall, then the internal network
Example: Load balancer: active-active uses every node for speed; active-passive keeps a standby, which is cheaper
Common mix-up: A reverse proxy is just a proxy that protects users while they browse. That is the forward proxy; a reverse proxy faces the internet on behalf of your servers and filters the requests coming in to them.

```say
Think of a bank. The street outside is the internet, the public banking hall is the screened subnet, and the vault is the internal network. Customers can walk into the hall, but a second locked door keeps them out of the vault.
Administrators should not connect straight to servers from anywhere. They go through one hardened jump server, so every admin session passes one point that is logged and watched.
To tell the proxies apart, follow the direction. A forward proxy sits in front of your users going out to the internet. A reverse proxy sits in front of your servers, taking requests coming in.
A web application firewall is the specialist for websites, so it goes directly in front of web servers. Intrusion detection and prevention sensors go behind the main firewall, where they inspect the traffic that made it through.
Here is a common mistake. A reverse proxy is just a proxy that protects users while they browse. That is not right. That is the forward proxy; a reverse proxy faces the internet on behalf of your servers and filters the requests coming in to them.
? Staff browsing needs filtering so they cannot reach malicious sites. Which kind of proxy do you need?
expect: A forward proxy, because it handles outbound traffic from users to the internet.
? Why does a screened subnet use two firewalls rather than one?
expect: So public-facing servers are reachable from the internet but a second barrier still protects the internal network if one of them is compromised.
```

### Fail open or fail closed
- Fail open: device dies, traffic keeps flowing
- Fail closed: device dies, traffic is blocked
- Fail open puts availability first and risks security
- Fail closed puts security first and risks availability
Example: A fire door that unlocks in a power cut fails open so people can escape
Example: A firewall guarding a payments database should fail closed

```say
Every inline security device will break one day, and the design question is what happens to traffic when it does. Either it carries on unchecked, or everything stops.
Neither is always right. If keeping the service running matters most, you let it fail open. If letting unchecked traffic through is unacceptable, you let it fail closed and accept the outage.
In a question, look for the clue about priorities. Words like life safety or must stay online point one way, while sensitive data or must never be exposed point the other.
? An intrusion prevention system protecting card payment data loses power. Should it fail open or closed, and what is the cost?
expect: Fail closed to protect the data; the cost is lost availability until it is fixed.
```

### Modern network concepts and secure protocols
- VLAN: logical separation on shared hardware
- 802.1X: devices authenticate before joining
- SD-WAN: software-managed WAN over internet links, must be encrypted
- SASE: networking and security as one cloud service
- Microsegmentation: every workload isolated, zero-trust style
Example: HTTP 80 to HTTPS 443, Telnet 23 to SSH 22, FTP 21 to SFTP 22 or FTPS 990
Example: LDAP 389 to LDAPS 636, SNMP v1 or v2 to SNMPv3, DNS to DNS over HTTPS
Common mix-up: SNMP version 3 needs a different port from the older versions. Version 3 still uses port 161; the improvement is that it adds authentication and encryption, not a new port.

```say
Virtual networks let one switch behave like several separate ones, which makes segmentation cheap. Port-based authentication goes further: a device must prove who it is before it gets on at all, which beats filtering by hardware address, because those addresses are easy to fake.
Software-defined wide area networking links branch offices over ordinary internet connections instead of expensive private lines, so the traffic has to be encrypted. Secure access service edge, pronounced sassy, bundles networking and security into a single service delivered from the cloud.
Microsegmentation takes isolation down to each individual workload, so one compromised server cannot freely talk to its neighbours.
For protocols, learn the swaps as pairs. If a question shows an old clear-text protocol, the answer is its encrypted replacement, and the port numbers often give it away.
Here is a common mistake. SNMP version 3 needs a different port from the older versions. That is not right. Version 3 still uses port 161; the improvement is that it adds authentication and encryption, not a new port.
? Why is port-based authentication stronger than allowing devices by their hardware address?
expect: MAC addresses can be spoofed, whereas 802.1X makes the device authenticate before it joins.
? An admin still manages switches with Telnet. What should replace it, and on which port?
expect: SSH on port 22, because it encrypts the session including credentials.
```

## Guided practice (10 min)

### Design a small company network
- Decide who owns each risk
- Choose where each device goes
- Pick fail open or fail closed with a reason
Example: Web shop servers go in the DMZ; the customer database stays internal

```say
Let us put this together. You will see a small company scenario on screen in a moment; talk me through your design one piece at a time. There is no single perfect answer, but every choice needs a reason.
Start with the easy wins: what is public, what is private, and which devices cannot defend themselves.
? Where would you put the company's public web server, and what would sit directly in front of it?
expect: In the screened subnet, with a web application firewall in front of it.
```

### Scenario: Design a small company network
A small online retailer runs its shop on rented virtual servers it patches itself, keeps a customer database in the office, has smart CCTV cameras with default passwords, and its IT contractor logs in from home to manage servers.

```say
Look at the scenario on the screen.
? Which cloud model is the shop using and what must the retailer patch, where do the cameras go, and how should the contractor get admin access?
expect: IaaS, so the retailer patches the OS and apps and owns data and access; put the cameras on their own segmented network or VLAN and change default credentials; route contractor admin access through a single audited jump server rather than direct connections.
```

## Review (5 min)

### Key distinctions and traps
- Data and access are always the customer's job
- Containers share a kernel; VMs do not
- Forward is outbound, reverse is inbound
- Fail open favours availability, fail closed favours security
- VLANs separate; 802.1X makes devices prove themselves first
Example: Cleartext protocol in the question? Pick its encrypted partner

```say
Three traps catch people here. Believing the cloud provider does everything, mixing up the two proxies, and forgetting that containers share a kernel.
When a question describes a fragile device that cannot be patched or run an agent, the answer is almost always to isolate it on its own network.
And for any failure question, ask what the scenario values more, staying online or staying safe, then pick the failure mode that matches.
? Which device would you place directly in front of a public website to stop attacks such as injection?
expect: A web application firewall.
? In platform as a service, what does the customer manage?
expect: Its applications and data, plus user access.
```

```quiz
[
 {
  "objective": "3.1",
  "type": "multiple_choice",
  "q": "In a cloud model, which party is responsible for more of the underlying infrastructure?",
  "options": [
   "The customer in every case",
   "Nobody",
   "The auditor only",
   "The provider as the service moves toward SaaS"
  ],
  "answer": "The provider as the service moves toward SaaS",
  "why": "The provider takes on more of the stack the more managed the service is: least in IaaS, most in SaaS, where the customer keeps only data and user access.",
  "source": "exam"
 },
 {
  "objective": "3.1",
  "type": "multiple_choice",
  "q": "Why is cloud misconfiguration a major security concern?",
  "options": [
   "A misconfigured service can expose resources despite otherwise strong controls",
   "Configuration is irrelevant in cloud",
   "Cloud removes access control",
   "Cloud prevents logging"
  ],
  "answer": "A misconfigured service can expose resources despite otherwise strong controls",
  "why": "Under shared responsibility the customer owns its settings and access, so one wrong setting, such as a publicly readable storage bucket, can expose data even when the provider's own security is strong.",
  "source": "exam"
 },
 {
  "objective": "3.2",
  "type": "multiple_choice",
  "q": "Which network concept places security controls according to where traffic must be inspected or enforced?",
  "options": [
   "Password hashing",
   "Network placement",
   "Data destruction",
   "Risk transfer"
  ],
  "answer": "Network placement",
  "why": "Placement means putting each control where the traffic it must handle actually passes, such as a WAF in front of web servers or a reverse proxy facing inbound requests.",
  "source": "exam"
 }
]
```
