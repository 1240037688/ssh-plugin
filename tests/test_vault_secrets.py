"""Offline tests for optional hv:// vault secret refs."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import vault_secrets  # noqa: E402


class TestParseRef(unittest.TestCase):
    def test_service_only(self):
        self.assertEqual(vault_secrets.parse_ref("hv://ssh-prod"), ("ssh-prod", None))

    def test_service_alias(self):
        self.assertEqual(vault_secrets.parse_ref("hv://ssh-prod?alias=tdh"), ("ssh-prod", "tdh"))

    def test_invalid(self):
        with self.assertRaises(vault_secrets.VaultRefError):
            vault_secrets.parse_ref("not-a-ref")
        with self.assertRaises(vault_secrets.VaultRefError):
            vault_secrets.parse_ref("hv://")

    def test_is_vault_ref(self):
        self.assertTrue(vault_secrets.is_vault_ref("hv://x"))
        self.assertFalse(vault_secrets.is_vault_ref("plain-password"))
        self.assertFalse(vault_secrets.is_vault_ref(None))


class TestResolveServerSecrets(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["HERMES_HOME"] = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_literal_password_untouched(self):
        server = {"id": "s1", "password": "literal", "passphrase": None}
        out = vault_secrets.resolve_server_secrets(server)
        self.assertEqual(out["password"], "literal")
        self.assertEqual(server["password"], "literal")  # input not mutated

    def test_resolves_password_ref(self):
        record = MagicMock()
        record.secret = "from-vault"
        with patch.object(vault_secrets, "resolve_ref", return_value="from-vault") as mocked:
            out = vault_secrets.resolve_server_secrets(
                {"id": "s1", "password": "hv://ssh-prod?alias=tdh"}
            )
        self.assertEqual(out["password"], "from-vault")
        mocked.assert_called_once_with("hv://ssh-prod?alias=tdh")

    def test_private_key_ref_becomes_inline_content(self):
        with patch.object(vault_secrets, "resolve_ref", return_value="-----BEGIN KEY-----"):
            out = vault_secrets.resolve_server_secrets(
                {"id": "s1", "auth": "password", "privateKey": "hv://ssh-key"}
            )
        self.assertEqual(out["privateKeyContent"], "-----BEGIN KEY-----")
        self.assertIsNone(out["privateKey"])
        self.assertEqual(out["auth"], "key")

    def test_missing_vault_package(self):
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "hermes_vault.vault" or name.startswith("hermes_vault"):
                raise ImportError("no vault")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(vault_secrets.VaultRefError) as ctx:
                vault_secrets.resolve_ref("hv://ssh-prod")
        self.assertIn("hermes_vault", str(ctx.exception))

    def test_session_server_resolves_refs(self):
        import sftp_client

        with patch.object(vault_secrets, "resolve_ref", return_value="vault-pass"):
            out = sftp_client.session_server(
                {"id": "s1", "password": "hv://svc", "passphrase": "***"}
            )
        self.assertEqual(out["password"], "vault-pass")
        self.assertIsNone(out["passphrase"])


if __name__ == "__main__":
    unittest.main()
