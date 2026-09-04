# OWASP Juice Shop — Full Solution Writeups

Detailed, step-by-step exploitation walkthroughs for the OWASP Juice Shop
application, produced during a team CTF engagement (**111 of 116 hacking
challenges** solved, plus **70 of 70 coding challenges**).

- **Platform:** OWASP Juice Shop `v20.2.0` served through a MultiJuicer CTF
  reverse proxy
- **Result:** 3870 CTF points, rank 1 of 8 teams
- **Report basis:** [`JUICE.md`](./JUICE.md) — the full engagement report
  (source of truth for every finding below)

> **Redactions.** Anything needed to reach the *live* competition instance
> (team session cookie, join passcode, proxy hostname) has been removed from
> this public repository. Every credential, hash, key and answer that is part
> of the Juice Shop seed data or the public source tree is kept — those are
> static application data, not live secrets.

**Single-document PDF:** [`Juice-Shop-Solutions.pdf`](./Juice-Shop-Solutions.pdf) —
a 76-page A4 document covering all 181 solved challenges (111 detailed hacking
writeups + the 70 coding-challenge solution method), with cover summary,
solved-challenge register and section links.

---

## What is in this repository

```
.
├── JUICE.md                        # Full engagement report (source of truth)
├── docs/
│   ├── environment-setup.md        # Target network, routing, tooling setup
│   ├── authentication-model.md     # JWT / cookie / localStorage auth split
│   ├── endpoint-reference.md       # Every route used, grouped by surface
│   ├── challenges/                 # One file per difficulty tier, 111 writeups
│   │   ├── 1-star.md               #   13 challenges
│   │   ├── 2-star.md               #   17 challenges
│   │   ├── 3-star.md               #   25 challenges
│   │   ├── 4-star.md               #   26 challenges
│   │   ├── 5-star.md               #   19 challenges
│   │   └── 6-star.md               #   11 challenges
│   ├── coding-challenges.md        # 35× find-it + 35× fix-it methodology
│   ├── blocked-challenges.md       # The 5 remaining, with proof they are env-blocked
│   ├── exploit-primitives.md       # 9 reusable, verified exploit techniques
│   └── credentials-data.md         # Seed creds, hashes, reset answers
└── tools/                          # Reusable exploit scripts & payloads
    └── README.md                   # Usage for every tool
```

## Writeup format

Every challenge entry follows the same template so writeups can be skimmed or
replayed:

1. **Difficulty / tier** and **vulnerability class** (CWE-style)
2. **Attack surface** — the exact endpoint(s), route(s) or socket involved
3. **Root cause** — the underlying flaw, with file references where known
4. **Step-by-step exploit** — copy-pasteable commands / payloads
5. **Verification** — how the challenge was confirmed solved

Entries solved collaboratively on the shared team instance are tagged
`(team activity)` and are described at a slightly higher level; entries
performed and verified directly in the authoring sessions contain full
reproducible steps.

## Categories exercised

Broken Access Control / IDOR / BOLA · SQL injection (UNION schema & data
exfiltration) · XXE + XXE-DoS · YAML alias bombs · mass assignment ·
business-logic abuse · CSRF · SSTi → `eval` · SSRF · sandboxed RCE
(`notevil`/`vm`) · zip-slip arbitrary file write · reflected / DOM / persisted
XSS · CSP injection · client-side secret disclosure · OSINT via EXIF · weak &
reused credentials · crypto weaknesses (hardcoded HMAC key, weak/unsigned &
algorithm-confused JWTs) · NoSQL injection · many security misconfigurations.

## Tools

All scripts in [`tools/`](./tools/) are dependency-light Python 3 (stdlib +
`requests`), parameterized against a `BASE_URL` and `COOKIE`/`TOKEN`, so they
replay against any Juice Shop deployment.

## Reading order

If you are new to Juice Shop, start with
[`docs/environment-setup.md`](./docs/environment-setup.md) and
[`docs/authentication-model.md`](./docs/authentication-model.md), then read
the tiers in difficulty order. If you are chasing a specific technique
(SQLi, SSTi, WebSocket verifiers, JWT tricks, …) skip straight to
[`docs/exploit-primitives.md`](./docs/exploit-primitives.md).

---

*Built for learning. Juice Shop is a deliberately vulnerable training target;
run exploits only against instances you own or are authorized to test.*
