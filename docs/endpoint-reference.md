# Endpoints & Routes Reference

Every route exercised during the engagement, grouped by surface.

## MultiJuicer management

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/multi-juicer/` | GET | Juicer landing / team selector |
| `/multi-juicer/api/teams/:team/status` | GET | Score, rank, solved list |
| `/multi-juicer/api/teams/:team/join` | POST | Join with `{"passcode":...}` |
| `/multi-juicer/api/teams/logout` | POST | Leave |

## Auth & user management

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/rest/user/login` | POST | Raw-SQL auth query → SQLi (Login Admin). Pre-login checks solve weak/reused-credential challenges. |
| `/rest/user/whoami` | GET | Profile; `?fields=` projection can include `password` (Password Hash Leak). |
| `/rest/user/authentication-details` | GET | All users (masked passwords for non-admin). |
| `/rest/user/reset-password` | POST | Reset w/ plaintext answer; compare `HMAC-SHA256(answer, '<static secret>')`. |
| `/rest/user/security-question?email=` | GET | Resolve security question. |
| `/api/Users/` | POST | Registration (mass-assignable `role`, `username` via setter w/ weak sanitizer). |
| `/profile` | GET/POST | Profile page / username change (cookie token). POST is CSRF-able. Renders Pug with username → SSTi + CSP-bypass surface. |
| `/profile/image/url` | POST | Fetch URL as profile image; on fetch failure stores raw URL (SSRF + profileImage injection). |
| `/profile/image/file` | POST | Multipart profile image upload. |
| `/dataerasure` | GET/POST | GDPR erasure. `layout` body param → Handlebars layout = **Local File Read**. |
| `/rest/image-captcha` | GET | Returns SVG captcha + plaintext answer. |
| `/rest/user/data-export` | POST | GDPR data export (image-captcha gated). |

## Shop / orders / reviews / B2B

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/rest/products/search?q=` | GET | SQL UNION-injectable search (9 cols). |
| `/rest/products/:id/reviews` | GET/PUT | Reviews (Mongo). |
| `/rest/products/reviews` | POST | Like a review (race → Multiple Likes). |
| `/rest/products/:id/reviews` (via `$where`) | GET | NoSQL DoS (`sleep` injection). |
| `/rest/basket/:id` | GET | IDOR basket read. |
| `/api/BasketItems/` | POST | Trusts `BasketId` + accepts negative quantity. |
| `/rest/basket/:id/checkout` | POST | Places order incl. negative totals; orderId `hash(email)[0:4]-<hex>`. |
| `/rest/deluxe-membership` | GET/POST | Deluxe upgrade; `paymentMode` not enforced → free deluxe. |
| `/api/Products/:id` | PUT | Product edit (admin) → Product Tampering. |
| `/b2b/v2/orders` | POST | B2B order; evaluates `orderLinesData` with `notevil` in a vm → RCE DoS challenges. |
| `/rest/track-order/:id` | GET | Reflects `id` (Reflected XSS). |
| `/api/Complaints/` | POST | Complaint messages scanned for challenge proof strings. |
| `/rest/wallet/balance`, `/rest/web3*`, `/rest/nft*` | … | Web3 wallet surface (blocked). |

## Files, feedback, misc

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/rest/captcha/` | GET | Math CAPTCHA w/ answer; reusable (CAPTCHA Bypass). |
| `/api/Feedbacks/` | GET/POST | Requires captcha; `UserId` mass-assignable (Forged Feedback). |
| `/file-upload` | POST | Multipart upload (`file`). XML → XXE; size/type checks; ZIP → zip-slip **Arbitrary File Write**; YAML → alias bomb. |
| `/ftp/`, `/ftp/:file` | GET | Directory listing / downloads. |
| `/rest/memories` | GET | Photo wall (leaks user records incl. password hashes). |
| `/rest/chat` | POST | Chat SSE (LLM unreachable in this deployment). |
| `/socket.io` | WS | Socket.IO events: `verifyLocalXssChallenge`, `verifyCloseNotificationsChallenge`, `verifySvgInjectionChallenge`. |
| `/snippets/:key`, `/snippets/verdict`, `/snippets/fixes/:key`, `/snippets/fixes` | GET/POST | Coding-challenge snippets & verdicts (find-it / fix-it; **unauthenticated**). |
| `/solve/challenges/server-side?key=...` | GET | Marks SSTi/SSRF solved when `abused_ssti_bug`/`abused_ssrf_bug` are set. |
| `/we/may/also/instruct/you/to/refuse/all/reasonably/necessary/responsibility` | GET | Privacy-Policy proof image. |
| `/rest/admin/application-configuration` | GET | Full runtime config. |
| `/metrics`, `/api/Challenges/`, `/.well-known/security.txt`, `/robots.txt` | GET | Standard recon surface. |

## SPA routes

`/#/score-board`, `/#/search` (DOM XSS sink), `/#/contact`,
`/#/administration`, `/#/privacy-security/privacy-policy`, `/#/web3-sandbox`,
`/#/chatbot`, `/#/photo-wall`, `/#/deluxe-membership` (accepts `?testDecal=`
→ SVG-injection proof), `/#/track-result?id=` (reflected XSS).
