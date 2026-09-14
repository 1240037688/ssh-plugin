"""Tests for host masking and mapping/diff helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deploy_paths import (
    agent_public_server,
    map_local_to_remote,
    map_remote_to_local,
    unified_diff,
)


class TestMask(unittest.TestCase):
    def test_agent_public_masks_host_and_user(self):
        s = {
            "id": "srv_1",
            "name": "prod",
            "host": "203.0.113.9",
            "port": 22,
            "username": "root",
            "password": "secret",
        }
        pub = agent_public_server(s)
        self.assertEqual(pub["host"], "***")
        self.assertEqual(pub["username"], "***")
        self.assertEqual(pub["password"], "***")
        self.assertNotIn("203.0.113.9", str(pub))


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
