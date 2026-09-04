# Blocked Challenges (5 remaining)

111 of 116 hacking challenges were solved. The remaining 5 are **blocked at the
deployment level** — none of them are reachable through the HTTP API as
configured:

| Challenge | Tier | Status |
| :--- | :--- | :--- |
| AI Debugging | ★★ | **Blocked** — needs a `tool-call` event, which only a live LLM emits |
| Chatbot Prompt Injection | ★★ | **Blocked** — `generateCoupon` tool needs a live LLM |
| Greedy Chatbot Manipulation | ★★★ | **Blocked** — needs LLM to emit ≥50% coupon |
| Mint the Honey Pot | ★★★ | **Blocked** — `ALCHEMY_API_KEY` unset, so the event listener never subscribes |
| Wallet Depletion | ★★★★★★ | **Blocked** — same root cause: `ContractExploited` can never be observed |

## Web3 blocker (verified against the verifier source)

Both Web3 challenges are gated on **server-side** `ethers` event listeners, not
on anything the client does:

- `routes/nftMint.ts` — `walletNFTVerify()` only solves when the submitted
  address is in `addressesMinted`, and the **only** write to that Set is inside
  `contract.on('NFTMinted', ...)`.
- `routes/web3Wallet.ts` — `web3WalletChallenge` is solved **inside** the
  `contract.on('ContractExploited', ...)` callback.

Both listeners are built against:

```js
new WebSocketProvider(`wss://eth-sepolia.g.alchemy.com/v2/${process.env.ALCHEMY_API_KEY ?? ''}`)
```

Reading the live environment through the SSTi read oracle shows the key is
**not configured**:

| Probe | Result |
| :--- | :--- |
| `process.env.ALCHEMY_API_KEY` | `<UNSET>` |
| env keys matching `/KEY\|ALCHEMY\|WEB3\|ETH/i` | `CTF_KEY` only |
| `process.env.NODE_ENV` | `multi-juicer` |

So the provider URL degrades to `wss://eth-sepolia.g.alchemy.com/v2/` with an
empty key, which Alchemy rejects (`HTTP/2 401 Must be authenticated!`).
`GET /rest/web3/nftMintListen` still returns
`{"success":true,"message":"Event Listener Created"}` because `ethers`
connects lazily — the failure only surfaces later on `provider.websocket.onerror`.
That success message is misleading.

> Even a funded Sepolia wallet and a genuine on-chain mint would not solve
> these, because the server never establishes the subscription and therefore
> never observes the event. Supplying `ALCHEMY_API_KEY` to the deployment is
> the only thing that would put these two in reach. Note this is *not* the
> "needs internet" limitation assumed earlier — the pod has full egress; the
> block is purely configuration.

## LLM blocker (verified with the correct request shape)

`/rest/chat` takes AI-SDK **model messages** directly:

```bash
POST /rest/chat   {"messages":[{"role":"user","content":"Hello"}]}
```

With the correct shape the endpoint returns `200` and streams SSE, but the body
is:

```
data: {"error":"LLM error: AI_RetryError: Failed after 3 attempts. Last error: Cannot connect to API: "}
```

Live config read through the SSTi oracle:

| Config / env | Value |
| :--- | :--- |
| `application.chatBot.llmApiUrl` | `http://localhost:11434/v1` (Ollama) |
| `application.chatBot.model` | `gemma4:e4b` |
| `application.chatBot.name` | `Juicy the Smart Assistant` |

(`appConfiguration` deletes `llmApiUrl` from its response, so this had to be
read via the eval oracle, not the config endpoint.)

The three AI challenges need the model to *act* — Prompt Injection and Greedy
Manipulation both require the `generateCoupon` tool to fire, and AI Debugging
requires a `tool-call` event — all confirmed blocked by the **deployment**, not
by request format or any bypassable filter.

> **Correction worth remembering:** *System Prompt Extraction* was initially
> grouped with these, which was wrong — it is verified against the Complaints
> table, not the chat stream, and was solved without a live model (see 3-star
> writeup).

## Bridging the LLM gap (SSTi → in-process fake LLM)

Because the three AI challenges gate on the server-side `streamText` call to
the configured `llmApiUrl`, a working OpenAI-compatible endpoint at
`http://localhost:11434/v1` would let them be solved through the *legitimate*
tool-execution path. The SSTi `eval` gives enough control to try:

- Use a `#{...}` username eval to start an **in-process** `http` server on
  `127.0.0.1:11434` (no child process — `child_process.spawn`/`exec` reliably
  502s / restarts the pod, and `/tmp` is not writable; the uploads directory
  is). The fake model returns an SSE `tool_calls` chunk invoking
  `generateCoupon` with `{"discount":50}` and emits a `tool-call` event (→ AI
  Debugging with the `show_tool_calls=true` cookie + non-admin token). The
  file-write side of the eval (to the uploads directory) was verified working.

Outcome: the deploy succeeded once, but the instance then entered a sustained
`instance-restarting` loop, wiping users back to the seed and killing both the
in-memory auth store and the in-process server before `/rest/chat` could
complete. Conclusion: the three AI challenges are *technically* reachable via
this bridge; the remaining blocker is **instance stability**, not the LLM.
