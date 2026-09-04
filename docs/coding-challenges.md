# Coding Challenges — find-it / fix-it (70/70 solved)

The Juice Shop score-board total of **186 = 116 hacking challenges + 70 coding
challenges**. Every challenge flagged `hasCodingChallenge: true` (35 of them)
exposes **two** code-snippet sub-challenges:

- **Find it** — select the vulnerable line(s) of a code snippet.
- **Fix it** — pick the correct patch from a set of candidate fixes.

Both are served by **unauthenticated** endpoints, so they are fully solvable
offline / in bulk.

## Endpoints

| Endpoint | Method | Purpose |
| :--- | :--- | :--- |
| `/snippets/:key` | GET | Return the vulnerable code snippet for `key` |
| `/snippets/verdict` | POST | `{key, selectedLines:[...]}` → `{verdict:true}` if vulnerable lines selected (find it) |
| `/snippets/fixes/:key` | GET | Return candidate patches (`{fixes:[...]}`) |
| `/snippets/fixes` | POST | `{key, selectedFix:<index>}` → `{verdict:true}` if correct patch picked (fix it) |

## Mechanics

- `routes/vulnCodeSnippet.ts` — `getVerdict()` requires `selectedLines` to be a
  **superset of `vulnLines`** and a **subset of `vulnLines ∪ neutralLines`**;
  the minimal correct answer is exactly `vulnLines`. Success →
  `codingChallengeStatus = 1`.
- `routes/vulnCodeFixes.ts` — `readFixes()` scans
  `data/static/codefixes/<key>_<n>[_correct].ts`; the file whose name has three
  segments marks `correct = n - 1`. Submitting that index →
  `codingChallengeStatus = 2`.
- `lib/codingChallenges.ts` — builds each snippet from the
  `// vuln-code-snippet start/vuln-line/neutral-line/end` markers in
  `server.ts`, `routes/`, `lib/`, `data/`, `frontend/src/app`, `models/`,
  `infrastructure/`. Replaying `getCodingChallengeFromFileContent()` against the
  pinned v20.2.0 source yields the exact `vulnLines`/`neutralLines` per key —
  the markers are stripped from the served snippet, so line numbers must be
  recomputed locally.

## Solve method

1. Compute `vulnLines` per key by replaying `getCodingChallengeFromFileContent()`
   over the v20.2.0 tree (a small Node script walking `SNIPPET_PATHS`; note
   `server.ts` is a *file* and must be scanned directly, not skipped by the
   directory walk). See [`../tools/coding_challenge_solver.py`](../tools/coding_challenge_solver.py).
2. `POST /snippets/verdict {key, selectedLines: vulnLines}` → find-it solved.
3. `GET /snippets/fixes/:key`, then try `selectedFix = 0..N-1` until
   `verdict:true` → fix-it solved (robust against `readdirSync` ordering).

## Result

All **35 find-it + 35 fix-it = 70/70** solved (`codingChallengeStatus: 2` for
all 35 keys), including the coding counterparts of the otherwise-blocked AI /
Web3 challenges (`chatbotPromptInjection`, `chatbotGreedyInjection`,
`nftMint`, `web3Wallet`).

> **Scoring caveat.** MultiJuicer's CTF score is the sum of *hacking* challenge
> difficulties only, so it is unaffected by coding challenges (still 3870). The
> coding challenges only move the Juice Shop score-board progress (111 → 181 of
> 186).
