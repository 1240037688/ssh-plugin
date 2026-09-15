"""Offline tests for optional hv:// vault secret refs."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
        with patch.object(vault_secrets, "vault_available", return_value=True):
            with patch.object(vault_secrets, "resolve_ref", return_value="from-vault") as mocked:
                out = vault_secrets.resolve_server_secrets(
                    {"id": "s1", "password": "hv://ssh-prod?alias=tdh"}
                )
        self.assertEqual(out["password"], "from-vault")
        mocked.assert_called_once_with("hv://ssh-prod?alias=tdh")

    def test_private_key_ref_becomes_inline_content(self):
        with patch.object(vault_secrets, "vault_available", return_value=True):
            with patch.object(vault_secrets, "resolve_ref", return_value="-----BEGIN KEY-----"):
                out = vault_secrets.resolve_server_secrets(
                    {"id": "s1", "auth": "password", "privateKey": "hv://ssh-key"}
                )
        self.assertEqual(out["privateKeyContent"], "-----BEGIN KEY-----")
        self.assertIsNone(out["privateKey"])
        self.assertEqual(out["auth"], "key")

    def test_missing_vault_skips_path_without_error(self):
        """No hermes_vault → do not take the vault path; do not fail connect."""
        with patch.object(vault_secrets, "vault_available", return_value=False):
            with patch.object(vault_secrets, "resolve_ref") as resolve_mock:
                out = vault_secrets.resolve_server_secrets(
                    {
                        "id": "s1",
                        "password": "hv://ssh-prod",
                        "passphrase": "hv://keyphrase",
                        "privateKey": "hv://ssh-key",
                    }
                )
        resolve_mock.assert_not_called()
        self.assertIsNone(out["password"])
        self.assertIsNone(out["passphrase"])
        self.assertIsNone(out["privateKey"])

    def test_literals_untouched_when_vault_missing(self):
        with patch.object(vault_secrets, "vault_available", return_value=False):
            out = vault_secrets.resolve_server_secrets({"id": "s1", "password": "literal"})
        self.assertEqual(out["password"], "literal")

    def test_resolve_ref_still_errors_if_called_without_package(self):
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "hermes_vault" or name.startswith("hermes_vault"):
                raise ImportError("no vault")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(vault_secrets.VaultRefError):
                vault_secrets.resolve_ref("hv://ssh-prod")

    def test_session_server_resolves_refs(self):
        import sftp_client

        with patch.object(vault_secrets, "vault_available", return_value=True):
            with patch.object(vault_secrets, "resolve_ref", return_value="vault-pass"):
                out = sftp_client.session_server(
                    {"id": "s1", "password": "hv://svc", "passphrase": "***"}
                )
        self.assertEqual(out["password"], "vault-pass")
        self.assertIsNone(out["passphrase"])

    def test_session_server_without_vault_clears_refs(self):
        import sftp_client

        with patch.object(vault_secrets, "vault_available", return_value=False):
            out = sftp_client.session_server({"id": "s1", "password": "hv://svc"})
        self.assertIsNone(out["password"])


if __name__ == "__main__":
    unittest.main()
