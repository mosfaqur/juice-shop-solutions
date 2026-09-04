#!/usr/bin/env python3
"""Raw Socket.IO v4 polling client (no third-party socket library).

Some challenges are solved by emitting Socket.IO verifier events
(verifyLocalXssChallenge, verifyCloseNotificationsChallenge,
verifySvgInjectionChallenge). python-socketio can fail namespace negotiation
through the MultiJuicer proxy, so this uses the plain engine.io polling
transport:

  GET  /socket.io/?EIO=4&transport=polling            -> sid
  POST /socket.io/?EIO=4&transport=polling&sid=<sid>  body: 40
  POST /socket.io/?EIO=4&transport=polling&sid=<sid>  body: 42["<event>","<data>"]

Usage:
  socketio_client.py --base BASE [--cookie C] emit --event NAME [--data JSON]
  socketio_client.py --base BASE [--cookie C] listen [--seconds N]
"""

import argparse
import json
import sys
import time

import requests

EIO = "4"


def base_url(base: str) -> str:
    return f"{base}/socket.io/?EIO={EIO}&transport=polling"


def handshake(base: str, cookie: str) -> str:
    headers = {"Cookie": cookie} if cookie else {}
    r = requests.get(base_url(base), headers=headers, timeout=15)
    # engine.io open packet: 0{"sid":"...",...}
    payload = r.text
    if not payload.startswith("0"):
        sys.exit(f"unexpected handshake: {payload[:200]}")
    return json.loads(payload[1:])["sid"]


def post(base: str, sid: str, cookie: str, body: str):
    headers = {"Cookie": cookie} if cookie else {}
    return requests.post(f"{base_url(base)}&sid={sid}", data=body, headers=headers, timeout=15)


def open_socket(base: str, sid: str, cookie: str):
    post(base, sid, cookie, "40")


def poll_once(base: str, sid: str, cookie: str) -> list:
    headers = {"Cookie": cookie} if cookie else {}
    r = requests.get(f"{base_url(base)}&sid={sid}", headers=headers, timeout=15)
    return [line for line in r.text.splitlines() if line]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="app origin, e.g. https://host")
    ap.add_argument("--cookie", default="", help="proxy/session cookie header value")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("emit")
    pe.add_argument("--event", required=True)
    pe.add_argument("--data", default="[]", help="JSON payload for the event args")
    pe.add_argument("--post", action="store_true", help="send an engine.io HTTP POST body")

    pl = sub.add_parser("listen")
    pl.add_argument("--seconds", type=float, default=5.0)

    args = ap.parse_args()

    sid = handshake(args.base, args.cookie)
    print(f"[*] sid={sid}")
    open_socket(args.base, sid, args.cookie)

    if args.cmd == "emit":
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError:
            data = args.data
        packet = json.dumps([args.event, data], separators=(",", ":"))
        r = post(args.base, sid, args.cookie, f"42{packet}")
        print(f"[*] emit HTTP {r.status_code}")
        time.sleep(1.0)
        for line in poll_once(args.base, sid, args.cookie):
            print(line)
    else:
        deadline = time.time() + args.seconds
        while time.time() < deadline:
            for line in poll_once(args.base, sid, args.cookie):
                print(line)
            time.sleep(0.25)


if __name__ == "__main__":
    main()
