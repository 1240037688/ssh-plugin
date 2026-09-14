"""Audit log tests — no secrets, append-only JSONL."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import audit_log  # noqa: E402


class TestAudit(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["HERMES_HOME"] = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_record_and_tail(self):
        audit_log.record("write", server_id="s1", server_name="prod", path="/var/a.txt", addedLines=2)
        audit_log.record("delete", server_id="s1", path="/var/b.txt", ok=False, error="boom")
        entries = audit_log.tail(10)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["op"], "write")
        self.assertEqual(entries[0]["path"], "/var/a.txt")
        self.assertFalse(entries[1]["ok"])

    def test_strips_secrets(self):
        audit_log.record(
            "write",
            server_id="s1",
            path="/x",
            detail={
                "password": "SHOULD_NOT_APPEAR",
                "content": "BODY",
                "contentBase64": "BBB",
                "note": "ok",
            },
        )
        raw = (audit_log.audit_path()).read_text(encoding="utf-8")
        self.assertNotIn("SHOULD_NOT_APPEAR", raw)
        self.assertNotIn("BODY", raw)
        self.assertNotIn("BBB", raw)
        self.assertIn("ok", raw)


if __name__ == "__main__":
    unittest.main()
