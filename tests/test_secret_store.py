"""DPAPI secret-at-rest tests (Windows only)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from secret_store import (
    ENCRYPTED_PREFIX,
    decrypt_server_secrets,
    encrypt_server_secrets,
    is_encrypted,
)


@unittest.skipUnless(sys.platform == "win32", "DPAPI requires Windows")
class TestDpapi(unittest.TestCase):
    def test_roundtrip(self):
        s = {"password": "s3cret-pass", "passphrase": "pp", "host": "h"}
        enc = encrypt_server_secrets(s)
        self.assertTrue(is_encrypted(enc["password"]))
        self.assertNotIn("s3cret-pass", json.dumps(enc))
        self.assertEqual(enc["host"], "h")
        dec = decrypt_server_secrets(enc)
        self.assertEqual(dec["password"], "s3cret-pass")
        self.assertEqual(dec["passphrase"], "pp")

    def test_store_disk_not_plaintext(self):
        import deployment_store as ds

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["HERMES_HOME"] = tmp
            ds.upsert_server(
                {
                    "name": "p",
                    "host": "10.0.0.1",
                    "username": "u",
                    "password": "DiskShouldNotShowThis",
                }
            )
            raw = (Path(tmp) / "plugin-data" / "ssh-plugin" / "deployments.json").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("DiskShouldNotShowThis", raw)
            self.assertIn(ENCRYPTED_PREFIX, raw)
            # load returns usable secret in-process
            got = ds.get_server("p")
            self.assertEqual(got["password"], "DiskShouldNotShowThis")

    def test_idempotent_encrypt(self):
        s = encrypt_server_secrets({"password": "abc"})
        again = encrypt_server_secrets(s)
        self.assertEqual(again["password"], s["password"])


if __name__ == "__main__":
    unittest.main()
