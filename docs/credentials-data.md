# Key Credentials, Hashes & Data Points

All values below are **static application seed data / public-source material**
from Juice Shop v20.2.0, reproduced here only for reference in the writeups.
Nothing here is a live environment secret. (Live session material — team
cookie, join passcode, proxy hostname — is deliberately absent from this repo.)

| Entity | Value | Use |
| :--- | :--- | :--- |
| Admin SQLi | `email=admin@juice-sh.op'--` | admin session (basket id 1) |
| Exposed test account | `testing@juice-sh.op` / `IamUsedForTesting` (admin) | Exposed Credentials |
| J12934 (leaked logs) | `0Y8rMnww$*9VFYE§59-!Fg1L6t&6lB` | Leaked Access Logs |
| Support team | `J6aVjTgOpRs@?5l!Zkq2AYnCE@RF$P` | Login Support Team |
| HMAC key (security answers) | `pa4qacea4VK9t9nGv7yZtwmj` (static) | verify stored answer hashes |
| John geo answer | `Daniel Boone National Forest` | reset john@juice-sh.op |
| Emma geo answer | `ITsec` | reset emma@juice-sh.op |
| Reset answers | jim=`Samuel`; bjoern@owasp.org=`Zaya`; bender=`Stop'n'Drop`; uvogin=`Silence of the Lambs`; bjoern@juice-sh.op=`West-2082`; morty=`5N0wb41L` | reset challenges |
| CSAF checksum | `7e7ce7c6...42e843` (prefix/suffix) | Security Advisory |
| Vulnerable infra | `mongo` + `4.4.29` | Vulnerable Infrastructure |
| Leaked API key | `6PPi37DBxP4lDwlriuaxP15HaDJpsUXY5TspVmie` | Leaked API Key |
| Admin MD5 | `0192023a7bbd73250516f069df18b500` | Weird Crypto |
| SSRF/SSTi solve key | `tRy_H4rd3r_n0thIng_iS_Imp0ssibl3` | `/solve/challenges/server-side?key=...` |
| Profile-username eval trigger | username containing `#{...}` | SSTi flag / read oracle |
| XSS payloads | `<iframe src="javascript:alert(\`xss\`)">`, `<script>alert(\`xss\`)</script>` | DOM / Reflected / username XSS |
| Product search columns | 9 | UNION shape |
| Users-username sanitizer | `sanitizeLegacy`: `/<(?:\w+)\W+?[\w]/gi` | CSP Bypass (username). Client-side XSS Protection is checked on the **email** field, which is not sanitized at all. |
| Hashids (continue codes) | salt `this is my salt`, min length 60, alphabet `a-zA-Z0-9` | Imaginary Challenge |
| JWT algorithm confusion | `/encryptionkeys/jwt.pub` bytes as HS256 secret | Forged Signed JWT |
| NFT private-key surface | wallet private key accepted at NFT unlock endpoint | NFT Takeover |
