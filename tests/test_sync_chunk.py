"""Tests for chunked read planning and sync dry-run."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deploy_paths import map_local_to_remote  # noqa: E402
from sync_plan import plan_sync  # noqa: E402
import sftp_client  # noqa: E402


class TestChunkRead(unittest.TestCase):
    def test_read_text_chunk_window(self):
        content = "A" * 100 + "B" * 50

        class FakeSftp:
            def open(self, path, mode):
                class F:
                    def __init__(self):
                        self._data = content.encode()
                        self._pos = 0

                    def stat(self):
                        m = MagicMock()
                        m.st_size = len(self._data)
                        return m

                    def seek(self, n):
                        self._pos = n

                    def read(self, n):
                        out = self._data[self._pos : self._pos + n]
                        self._pos += len(out)
                        return out

                    def close(self):
                        pass

                    def prefetch(self):
                        pass

                    def __enter__(self):
                        return self

                    def __exit__(self, *a):
                        return False

                return F()

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
            return FakeClient(), FakeSftp(), 1.0

        server = {"id": "t", "host": "h", "username": "u", "password": "x"}
        with patch.object(sftp_client.ssh_session if hasattr(sftp_client, "ssh_session") else __import__("ssh_session"), "_open", side_effect=fake_open):
            import ssh_session as ss

            with patch.object(ss, "_open", side_effect=fake_open):
                r = sftp_client.read_text_chunk(server, "/f.txt", offset=90, limit=20)
                self.assertEqual(r["bytes"], 20)
                self.assertFalse(r["eof"])
                self.assertEqual(r["nextOffset"], 110)
                r2 = sftp_client.read_text_chunk(server, "/f.txt", offset=140, limit=100)
                self.assertTrue(r2["eof"])
        ss.close_all()


class TestSyncPlan(unittest.TestCase):
    def test_dry_run_lists_mapped_files(self):
        os.environ["HERMES_HOME"] = tempfile.mkdtemp()
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "proj"
            (local / "sub").mkdir(parents=True)
            (local / "a.txt").write_text("1", encoding="utf-8")
            (local / "sub" / "b.txt").write_text("2", encoding="utf-8")
            (local / ".git").mkdir()
            (local / ".git" / "x").write_text("z", encoding="utf-8")
            server = {
                "id": "s",
                "mappings": [{"localRoot": str(local), "remoteRoot": "/var/www"}],
                "exclusions": [],
                "allowedLocalPaths": [str(Path(tmp).parent) if False else tmp],
            }
            # allow local path under tmp
            server["allowedLocalPaths"] = [tmp]
            r = plan_sync(server, str(local), dry_run=True)
            self.assertTrue(r["ok"])
            self.assertTrue(r["dryRun"])
            rels = {f["rel"] for f in r["files"]}
            self.assertIn("a.txt", rels)
            self.assertIn("sub/b.txt", rels)
            self.assertFalse(any(".git" in f["rel"] for f in r["files"]))
            self.assertTrue(all(f["remotePath"].startswith("/var/www") for f in r["files"]))


if __name__ == "__main__":
    unittest.main()
