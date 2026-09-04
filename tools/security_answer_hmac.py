#!/usr/bin/env python3
"""Compute the HMAC-SHA256 stored for a security-question answer.

Seed answers in Juice Shop are stored as HMAC-SHA256 with the static secret
used by routes/resetPassword.ts. Compare the output against the `answer`
column in the SecurityAnswers table (dump it via union_sqli.py) to confirm a
candidate plaintext before resetting an account.

Usage:
  security_answer_hmac.py "Samuel"
"""

import argparse
import hashlib
import hmac

SECRET = "pa4qacea4VK9t9nGv7yZtwmj"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("answer", help="plaintext security-question answer")
    args = ap.parse_args()
    digest = hmac.new(SECRET.encode(), args.answer.encode(), hashlib.sha256).hexdigest()
    print(digest)


if __name__ == "__main__":
    main()
