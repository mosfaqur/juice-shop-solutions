#!/usr/bin/env bash
# Generate Juice-Shop-Solutions.pdf from Juice-Shop-Solutions.md using Pandoc & Weasyprint

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SOURCE="$REPO_ROOT/Juice-Shop-Solutions.md"
TARGET="$REPO_ROOT/Juice-Shop-Solutions.pdf"

echo "[*] Compiling PDF from $SOURCE..."
pandoc -f gfm "$SOURCE" \
  -o "$TARGET" \
  --pdf-engine=weasyprint \
  -V geometry:margin=2cm \
  -V papersize=a4 \
  --metadata title="OWASP Juice Shop - 181 Solved Challenges" \
  --metadata author="Mosfaqur"

echo "[+] Successfully generated: $TARGET"
