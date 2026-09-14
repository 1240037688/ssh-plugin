"""Offline tests for ssh-plugin store/security/session (no real SSH)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import deployment_store as ds  # noqa: E402
import security  # noqa: E402
import ssh_session as ss  # noqa: E402


class TestStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["HERMES_HOME"] = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_secret_preserved_on_empty_update(self):
        s = ds.upsert_server(
            {"name": "a", "host": "h", "username": "u", "auth": "password", "password": "s3cret"}
        )
        ds.upsert_server(
            {"id": s["id"], "name": "a", "host": "h", "username": "u", "auth": "password", "password": ""}
        )
        raw = json.loads(
            (Path(self._tmp.name) / "plugin-data" / "ssh-plugin" / "deployments.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(raw["servers"][0]["password"], "s3cret")

    def test_public_masks_secret(self):
        s = ds.upsert_server(
            {"name": "b", "host": "h", "username": "u", "password": "x"}
        )
        pub = ds.public_server(s)
        self.assertEqual(pub["password"], "***")

    def test_traversal_blocked(self):
        with self.assertRaises(ValueError):
            ds.safe_remote_path("/a/../b", None)

    def test_dir_glob_hides_directory(self):
        self.assertTrue(ds.match_exclusion("node_modules", ["node_modules/**"]))
        self.assertFalse(ds.match_exclusion("app.py", ["node_modules/**"]))


class TestSecurity(unittest.TestCase):
    def test_whitelist_full_match_and_shell_control(self):
        srv = {
            "allow_exec": True,
            "commandWhitelist": [r"^ls$"],
            "commandBlacklist": [r"rm"],
        }
        self.assertEqual(security.validate_command(srv, "ls"), "ls")
        with self.assertRaises(security.SecurityError):
            security.validate_command(srv, "ls; id")
        with self.assertRaises(security.SecurityError):
            security.validate_command(srv, "rm -rf /")
        with self.assertRaises(security.SecurityError):
            security.validate_command({"allow_exec": False}, "ls")

    def test_local_path_allowlist(self):
        p = security.validate_local_path("plugin.yaml", {})
        self.assertEqual(p.name, "plugin.yaml")
        with self.assertRaises(security.SecurityError):
            security.validate_local_path("C:/Windows/System32/drivers/etc/hosts", {})


class TestPool(unittest.TestCase):
    def test_reuse_and_health(self):
        ss.close_all()
        server = {"id": "t1", "host": "h", "username": "u", "password": "x"}
        opens = {"n": 0}

        class FakeSftp:
            def listdir(self, p):
                return []

            def stat(self, p):
                return MagicMock()

            def close(self):
                pass

        class FakeClient:
            def get_transport(self):
                t = MagicMock()
                t.is_active.return_value = True
                return t

            def open_sftp(self):
                return FakeSftp()

            def close(self):
                pass

        def fake_open(srv):
            opens["n"] += 1
            return FakeClient(), FakeSftp(), 1.0

        with patch.object(ss, "_open", side_effect=fake_open):
            self.assertEqual(ss.with_sftp(server, lambda s: "ok"), "ok")
            n = opens["n"]
            self.assertEqual(ss.with_sftp(server, lambda s: "ok2"), "ok2")
            self.assertEqual(opens["n"], n)
            self.assertTrue(ss.health(server)["ok"])
        ss.close_all()


if __name__ == "__main__":
    unittest.main()
