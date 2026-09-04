# Environment Setup & Network Architecture

How the target was reached and how the assessment tooling was configured.

## Layout

The target ran on a dedicated CTF Wi-Fi network (`multi_juicer_5G`) with **no
outbound internet from the assessment client**. Internet access was carried on
a second interface, giving a dual-homed client:

| Interface | Purpose | Addressing |
| :--- | :--- | :--- |
| `usb0` | Outbound internet / DNS / tool traffic (GitHub source cross-reference, reverse geocoding) | DHCP, gateway on phone tether |
| `wlan0` | Direct route to the target CTF network | `192.168.0.163/24`, `ipv4.never-default yes` / `ipv6.never-default yes` |

Connecting the target interface without pulling the default route:

```bash
nmcli connection add type wifi ifname wlan0 con-name "multi_juicer_5G" \
  ssid "multi_juicer_5G"
nmcli connection modify "multi_juicer_5G" \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk "<wifi-passphrase>"
nmcli connection modify "multi_juicer_5G" \
  ipv4.never-default yes ipv6.never-default yes
nmcli connection up "multi_juicer_5G"
```

## Target addressing

- App hostname resolved via mDNS + an `/etc/hosts` entry pointing at the
  instance pod IP (e.g. `192.168.0.101`).
- Only TCP 80/443 were open on the pod.
- The Juice Shop instance is only reachable **through the MultiJuicer reverse
  proxy**. Every request needs the team `multi-juicer` session cookie;
  otherwise every path `302`s to `/multi-juicer`.

## Team access

- Team joined with a one-time join passcode via
  `POST /multi-juicer/api/teams/<team>/join` (`{"passcode": "..."}`).
- Once joined, the `multi-juicer` cookie must be attached to **every** request
  for `https://ctf-proxy.local/...` to be proxied to the team instance.
- Score / solved-list is readable from
  `GET /multi-juicer/api/teams/<team>/status`.

## Egress correction (important)

The Juice Shop **pod itself has full outbound internet egress**, even though
the *client* network does not. This was proven with the profile-image fetch
primitive (`POST /profile/image/url`), which stores an uploads path on
success and the raw URL on failure: a `raw.githubusercontent.com` URL came
back as `/assets/public/images/uploads/2.jpg` (fetched), while a LAN control
behaved identically. Earlier assumptions that the target had no egress were
wrong, and that assumption made the Web3 challenges look untestable — see
[`blocked-challenges.md`](./blocked-challenges.md) for the *actual* (server
configuration) blocker.

## Application stack fingerprint

| Component | Detail |
| :--- | :--- |
| Express | `^4.22.1` (version banner leaked in error pages) |
| SQLite | 3.44.2 (product search, users, captchas) |
| MongoDB | reviews / orders / complaints |
| XML parsing | `libxml2-wasm`, external entities enabled |
| B2B eval sandbox | `notevil` inside a `node:vm` |
| Templating | Handlebars views (`views/*.hbs`) + Pug (profile) |
| Realtime | Socket.IO, Prometheus `/metrics` |
| Version | Juice Shop **v20.2.0** (read via Local File Read of `/juice-shop/package.json`) |

## Source cross-referencing

A shallow sparse clone of the pinned upstream
`juice-shop/juice-shop` (tag `v20.2.0`) was used to read seed data, runtime
config and challenge-verifier source (`routes/*.ts`, `models/*.ts`,
`config/*.yml`) so exploits could be driven precisely and the LLM/Web3
blockers confirmed from the verifier code.

## Tooling

`curl`, `jq`, Python 3 (`urllib`/`requests`), `playwright-core` + system
Chromium headless (SPA routes / localStorage token injection), raw
Socket.IO polling, `exiftool`, `zipfile`/`pyyaml` for file-upload payloads.
See [`../tools/README.md`](../tools/README.md).
