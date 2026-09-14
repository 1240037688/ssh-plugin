"""Regression: blocking SSH helpers must not pin the FastAPI event loop."""

from __future__ import annotations

import asyncio
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard import plugin_api  # noqa: E402


class TestSshCallDoesNotBlockLoop(unittest.IsolatedAsyncioTestCase):
    async def test_health_stays_responsive_during_blocking_ssh(self):
        """A slow blocking fn in the SSH pool must not stall /health."""

        def slow_ls(_server, _path):
            time.sleep(0.25)
            return {"entries": [], "path": "/"}

        async def health_now():
            await asyncio.sleep(0)
            return {"ok": True}

        t0 = time.perf_counter()
        ssh_task = asyncio.create_task(plugin_api._ssh_call(slow_ls, {"id": "x"}, "/"))
        # Health-style coroutine should complete while SSH is still sleeping.
        health = await asyncio.wait_for(health_now(), timeout=0.1)
        self.assertTrue(health["ok"])
        result = await asyncio.wait_for(ssh_task, timeout=2)
        self.assertEqual(result["entries"], [])
        self.assertLess(time.perf_counter() - t0, 1.5)

    async def test_ssh_call_propagates_kwargs_and_errors(self):
        def echo(a, *, b=0):
            return a + b

        self.assertEqual(await plugin_api._ssh_call(echo, 1, b=2), 3)

        def boom():
            raise RuntimeError("nope")

        with self.assertRaises(RuntimeError):
            await plugin_api._ssh_call(boom)

    async def test_fs_ls_uses_executor_path(self):
        with patch.object(
            plugin_api.sftp_client, "list_dir", return_value={"entries": [{"name": "a"}], "path": "/"}
        ) as mocked:
            with patch.object(plugin_api, "_server_or_404", return_value={"id": "s1"}):
                with patch.object(plugin_api, "_safe_path", return_value="/"):
                    with patch.object(plugin_api.sftp_client, "filter_excluded", side_effect=lambda e, _x: e):
                        out = await plugin_api.fs_ls("s1", "/")
        self.assertEqual(out["entries"][0]["name"], "a")
        mocked.assert_called_once()


class TestDefaultTimeout(unittest.TestCase):
    def test_connection_timeout_defaults_to_10s(self):
        import ssh_session as ss

        with patch.object(ss, "_require_pk", create=True):
            # _connect_kwargs needs paramiko loaders only for key auth
            kwargs = ss._connect_kwargs({"host": "h", "username": "u", "auth": "password"})
        self.assertEqual(kwargs["timeout"], 10.0)
        self.assertEqual(kwargs["banner_timeout"], 10.0)
        self.assertEqual(kwargs["auth_timeout"], 10.0)

    def test_failed_connection_releases_server_lock(self):
        import ssh_session as ss

        server = {"id": "failed-lock-test"}
        with patch.object(ss, "_open", side_effect=RuntimeError("connect failed")):
            with self.assertRaises(RuntimeError):
                with ss.get_session(server):
                    pass
        entry = ss._entry_for(server)
        acquired = []
        import threading

        def try_lock():
            ok = entry.lock.acquire(timeout=0.2)
            acquired.append(ok)
            if ok:
                entry.lock.release()

        thread = threading.Thread(target=try_lock)
        thread.start()
        thread.join(timeout=1)
        self.assertEqual(acquired, [True])


if __name__ == "__main__":
    unittest.main()
