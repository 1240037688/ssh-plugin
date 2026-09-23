"""Tests for host masking and mapping/diff helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deploy_paths import (
    agent_list_servers,
    agent_public_server,
    agent_unmask_server,
    map_local_to_remote,
    map_remote_to_local,
    unified_diff,
)


class TestMask(unittest.TestCase):
    def test_agent_public_minimal_shape(self):
        s = {
            "id": "srv_1",
            "name": "workbox",
            "host": "203.0.113.9",
            "port": 22,
            "username": "root",
            "password": "secret",
            "endpoint": "root@203.0.113.9:22",
            "connectionString": "ssh://root@203.0.113.9",
            "userHost": "root@203.0.113.9",
            "allow_exec": True,
        }
        pub = agent_public_server(s)
        self.assertEqual(
            pub,
            {"name": "workbox", "configured": True, "allow_exec": True},
        )
        blob = str(pub)
        for leak in ("203.0.113.9", "root", "secret", "***", "endpoint", "userHost"):
            self.assertNotIn(leak, blob)
        self.assertNotIn("password", pub)
        self.assertNotIn("host", pub)
        self.assertNotIn("port", pub)
        self.assertNotIn("username", pub)

    def test_agent_list_servers_is_minimal(self):
        listed = agent_list_servers(
            [{"id": "a", "name": "workbox", "host": "10.0.0.1", "port": 2222, "username": "u"}]
        )
        self.assertEqual(
            listed, [{"name": "workbox", "configured": True, "allow_exec": False}]
        )

    def test_agent_unmask_no_secrets_or_derived(self):
        s = {
            "id": "srv_1",
            "name": "workbox",
            "host": "203.0.113.9",
            "port": 2200,
            "username": "root",
            "password": "secret",
            "privateKey": "C:/key",
            "endpoint": "root@203.0.113.9:22",
            "connectionString": "ssh://root@203.0.113.9",
        }
        un = agent_unmask_server(s)
        self.assertEqual(un["host"], "203.0.113.9")
        self.assertEqual(un["username"], "root")
        self.assertEqual(un["port"], 2200)
        for key in ("password", "privateKey", "endpoint", "connectionString"):
            self.assertNotIn(key, un)


class TestMap(unittest.TestCase):
    def setUp(self):
        self.server = {
            "mappings": [
                {"localRoot": "E:/proj", "remoteRoot": "/var/www"},
                {"localRoot": "E:/proj/sub", "remoteRoot": "/srv/sub"},
            ]
        }

    def test_local_to_remote_longest_wins(self):
        r = map_local_to_remote(self.server, "E:/proj/sub/a.txt")
        self.assertTrue(r["ok"])
        self.assertEqual(r["remotePath"], "/srv/sub/a.txt")

    def test_local_to_remote_outer(self):
        r = map_local_to_remote(self.server, "E:/proj/x/y.txt")
        self.assertTrue(r["ok"])
        self.assertEqual(r["remotePath"], "/var/www/x/y.txt")

    def test_remote_to_local(self):
        r = map_remote_to_local(self.server, "/var/www/x/y.txt")
        self.assertTrue(r["ok"])
        self.assertIn("proj", r["localPath"].replace("/", "\\"))

    def test_unmapped(self):
        r = map_local_to_remote(self.server, "C:/elsewhere/a.txt")
        self.assertFalse(r["ok"])


class TestDiff(unittest.TestCase):
    def test_diff_stats(self):
        d = unified_diff("a\nb\n", "a\nc\n", "f.txt")
        self.assertFalse(d["identical"])
        self.assertGreaterEqual(d["addedLines"], 1)
        self.assertGreaterEqual(d["removedLines"], 1)

    def test_identical(self):
        d = unified_diff("same\n", "same\n", "f.txt")
        self.assertTrue(d["identical"])

    def test_empty_remote(self):
        d = unified_diff("", "new\n", "f.txt")
        self.assertTrue(d["emptyRemote"])


if __name__ == "__main__":
    unittest.main()
