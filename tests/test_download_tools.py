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

    def test_download_tree_entry_limit(self):
        class WideSftp(FakeSftp):
            def listdir_attr(self, path):
                if path == "/allowed":
                    return [
                        SimpleNamespace(filename=f"f{i}.txt", st_mode=stat.S_IFREG, st_size=1)
                        for i in range(5)
                    ]
                return []

        class WideSession(FakeSession):
            def __init__(self, *_args):
                self.sftp = WideSftp()

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            server = {"allowedRemotePaths": ["/allowed"], "allowedLocalPaths": [tmp]}
            with patch.object(sftp_client, "RemoteSession", WideSession):
                with self.assertRaises(ValueError):
                    download_plan.download_tree(
                        server, "/allowed", str(Path(tmp) / "out"), max_entries=3
                    )

    def test_download_tree_reguards_at_open(self):
        """Open must re-check allowlist even if plan-time list succeeded."""

        class SwapSftp(FakeSftp):
            def __init__(self):
                super().__init__()
                self.normalize_calls = 0

            def normalize(self, path):
                self.normalize_calls += 1
                # Plan walk: 2 guards (folder + file). Open-time re-check is the 3rd.
                if self.normalize_calls > 2 and str(path).endswith("result.log"):
                    return "/etc/passwd"
                return path

        class SwapSession(FakeSession):
            def __init__(self, *_args):
                self.sftp = SwapSftp()

        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            server = {"allowedRemotePaths": ["/allowed"], "allowedLocalPaths": [tmp]}
            with patch.object(sftp_client, "RemoteSession", SwapSession):
                with self.assertRaises(ValueError):
                    download_plan.download_tree(
                        server, "/allowed", str(Path(tmp) / "out"), dry_run=False
                    )
            # dry-run never opens; plan-time guards alone must still succeed
            with patch.object(sftp_client, "RemoteSession", SwapSession):
                preview = download_plan.download_tree(
                    server, "/allowed", str(Path(tmp) / "out2"), dry_run=True
                )
            self.assertEqual(preview["count"], 1)

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
