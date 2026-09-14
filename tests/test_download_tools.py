"""Offline coverage for bounded directory download and result readers."""

from __future__ import annotations

import io
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import download_plan  # noqa: E402
import sftp_client  # noqa: E402


class FakeSftp:
    def __init__(self):
        self.content = b"hello\nworld\n"

    def stat(self, path):
        return SimpleNamespace(st_size=len(self.content))

    def normalize(self, path):
        return path

    def listdir_attr(self, path):
        if path == "/allowed":
            return [SimpleNamespace(filename="result.log", st_mode=stat.S_IFREG, st_size=len(self.content))]
        return []

    def open(self, path, mode):
        return io.BytesIO(self.content)


class FakeSession:
    def __init__(self, *_args):
        self.sftp = FakeSftp()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class TestResultTools(unittest.TestCase):
    def test_download_tree_dry_run_then_write(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            server = {"allowedRemotePaths": ["/allowed"], "allowedLocalPaths": [tmp]}
            target = Path(tmp) / "results"
            with patch.object(sftp_client, "RemoteSession", FakeSession):
                preview = download_plan.download_tree(server, "/allowed", str(target))
                self.assertEqual(preview["count"], 1)
                self.assertFalse(target.exists())
                done = download_plan.download_tree(server, "/allowed", str(target), dry_run=False)
            self.assertEqual(done["downloaded"], 1)
            self.assertEqual((target / "result.log").read_bytes(), b"hello\nworld\n")

    def test_glob_and_tail(self):
        server = {"allowedRemotePaths": ["/allowed"]}
        with patch.object(sftp_client, "RemoteSession", FakeSession):
            found = sftp_client.glob_files(server, "/allowed", "*.log")
            tail = sftp_client.tail_text(server, "/allowed/result.log", limit=6)
        self.assertEqual([m["relativePath"] for m in found["matches"]], ["result.log"])
        self.assertEqual(tail["content"], "world\n")
        self.assertEqual(tail["offset"], 6)


if __name__ == "__main__":
    unittest.main()
