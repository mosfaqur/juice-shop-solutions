# Authentication Model (as observed)

Juice Shop runs **two parallel authentication channels** plus the SPA storage.
Knowing which one a route uses is the single most important thing when
replaying any exploit.

| Mechanism | Header / Cookie | Used by | Notes |
| :--- | :--- | :--- | :--- |
| Bearer JWT | `Authorization: Bearer <jwt>` | Most `/rest` + `/api` (e.g. `POST /api/BasketItems/`, `PUT /api/Products/:id`, `/b2b/v2/orders`, `/rest/products/reviews`) | Missing header → `401 No Authorization header was found`. |
| Cookie token | `Cookie: token=<jwt>` | `/rest/user/whoami`, `/profile`, `/dataerasure`, `/rest/user/authentication-details`, `/rest/image-captcha` | These call `security.authenticatedUsers.get(req.cookies.token)` — an **in-memory store** cleared on instance restart. |
| SPA token | `localStorage['token']` | Angular app session | Browser automation must inject via `addInitScript`. |
| Proxy cookie | `Cookie: multi-juicer=...` | **All** requests | Gateway requirement (environment). |

## Consequences that shaped the engagement

1. **Restart discipline.** After any instance restart the in-memory auth
   store is empty: `cookie`-based routes (`/profile`, `/dataerasure`, …) start
   401-ing until you log in again. Bearer-token routes are unaffected because
   the JWT is self-contained. Always re-login after a restart and re-read
   `/api/Challenges/` before relying on cookie-based routes.

2. **Auth ≠ user id.** Several endpoints authorize only "is there a token"
   and trust a *client-supplied* resource id — that is the mass-assignment /
   IDOR surface (see tiers 3★ and 4★).

3. **CSRF surface.** The `token` cookie is sent automatically by the browser,
   so cookie-based `POST` routes (`/profile`, `/dataerasure`) are
   cross-site-requestable. Bearer-token routes are not (header cannot be set
   cross-origin without CORS help).

## Login mechanics

`POST /rest/user/login` runs a **raw SQL** query:

```sql
SELECT * FROM Users WHERE email='..' AND password='..' AND deletedAt IS NULL
```

- This is the SQL injection surface used for the *Login Admin* challenge
  (`email=admin@juice-sh.op'--`) and the pre-login weak/reused-credential
  checks.
- Successful login returns a JWT in `authentication.token` and the server
  also records it in the in-memory store (so cookie-based routes work after
  `POST /rest/user/login` even if the browser never held the token).

## JWT algorithm notes

- HS256 JWTs are signed with `jwtSecret` from `config/*.yml`
  (`#SECRET#` overridden at runtime).
- The RSA public key lives at `/encryptionkeys/jwt.pub` (world readable) —
  enables algorithm-confusion (HS256 signed with the public-key bytes).
- `alg:none` unsigned tokens are accepted for some routes (Unsigned JWT
  challenge). See [`exploit-primitives.md`](./exploit-primitives.md).
