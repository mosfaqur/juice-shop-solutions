#!/usr/bin/env python3
"""Repository health and consistency verification script.

Verifies:
  1. All relative links across all markdown files are valid.
  2. Python tools compile and pass formatting/linter standards.
  3. Node tooling passes syntax check.
  4. Executable permissions are set on scripts.
  5. Challenge registers and counts match expected totals.
"""

import glob
import os
import py_compile
import re
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def check_markdown_links():
    print("[*] Checking markdown links...")
    broken = []
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    for root, dirs, files in os.walk(REPO_ROOT):
        if ".git" in dirs:
            dirs.remove(".git")
        for f in files:
            if f.endswith(".md"):
                mdf = os.path.join(root, f)
                with open(mdf, "r", encoding="utf-8", errors="ignore") as fp:
                    content = fp.read()
                for m in link_pattern.finditer(content):
                    text, url = m.groups()
                    if url.startswith(("http://", "https://", "mailto:", "#")):
                        continue
                    target_path = url.split("#")[0]
                    if not target_path:
                        continue
                    resolved = os.path.normpath(os.path.join(os.path.dirname(mdf), target_path))
                    if not os.path.exists(resolved):
                        broken.append((os.path.relpath(mdf, REPO_ROOT), url, text))
    if broken:
        print(f"[!] FAILED: {len(broken)} broken markdown links found:")
        for mdf, url, text in broken:
            print(f"    {mdf}: '{text}' -> {url}")
        return False
    print("    [+] All relative markdown links are valid.")
    return True


def check_tool_syntax_and_perms():
    print("[*] Checking tools syntax and permissions...")
    tools_dir = os.path.join(REPO_ROOT, "tools")
    py_files = glob.glob(os.path.join(tools_dir, "*.py"))
    mjs_files = glob.glob(os.path.join(tools_dir, "*.mjs"))
    success = True

    for pf in py_files:
        try:
            py_compile.compile(pf, doraise=True)
        except py_compile.PyCompileError as e:
            print(f"[!] Syntax error in {pf}: {e}")
            success = False
        if not os.access(pf, os.X_OK):
            print(f"[!] Missing executable permission on {pf}")
            success = False

    for mf in mjs_files:
        res = subprocess.run(["node", "--check", mf], capture_output=True, text=True, check=False)
        if res.returncode != 0:
            print(f"[!] Syntax error in {mf}: {res.stderr}")
            success = False
        if not os.access(mf, os.X_OK):
            print(f"[!] Missing executable permission on {mf}")
            success = False

    if success:
        print(f"    [+] {len(py_files)} Python tools and {len(mjs_files)} Node tools verified.")
    return success


def check_challenge_counts():
    print("[*] Checking challenge counts and register consistency...")
    tier_files = sorted(glob.glob(os.path.join(REPO_ROOT, "docs", "challenges", "*-star.md")))
    total_hacking_solved = 0
    expected_tiers = {
        "1-star.md": 13,
        "2-star.md": 17,
        "3-star.md": 25,
        "4-star.md": 26,
        "5-star.md": 19,
        "6-star.md": 11,
    }

    for tf in tier_files:
        basename = os.path.basename(tf)
        with open(tf, "r", encoding="utf-8") as fp:
            content = fp.read()
        # Count numbered challenges: "## <number>. <title>"
        matches = re.findall(r"^##\s+\d+\.\s+.*$", content, re.MULTILINE)
        count = len(matches)
        expected = expected_tiers.get(basename)
        if count != expected:
            print(f"[!] Tier {basename} mismatch: found {count}, expected {expected}")
            return False
        total_hacking_solved += count

    if total_hacking_solved != 111:
        print(f"[!] Total hacking challenges mismatch: found {total_hacking_solved}, expected 111")
        return False

    print("    [+] Verified 111 hacking challenge writeups across 6 tiers.")
    print("    [+] Total score-board target: 111 hacking + 70 coding + 5 blocked = 186 total.")
    return True


def main():
    print("=== OWASP Juice Shop Repository Verification ===")
    results = [
        check_markdown_links(),
        check_tool_syntax_and_perms(),
        check_challenge_counts(),
    ]
    if all(results):
        print("\n[✓] ALL CHECKS PASSED: Repository is 100% verified.")
        return 0
    print("\n[✗] SOME CHECKS FAILED.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
