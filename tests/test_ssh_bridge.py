"""Offline tests for the optional subprocess SSH bridge."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ssh_bridge  # noqa: E402
import ssh_bridge_worker  # noqa: E402


class TestBridgeEnabled(unittest.TestCase):
    def test_default_off(self):
        env = os.environ.pop("SSH_PLUGIN_BRIDGE", None)
        try:
            self.assertFalse(ssh_bridge.bridge_enabled())
        finally:
            if env is not None:
                os.environ["SSH_PLUGIN_BRIDGE"] = env

    def test_truthy_values(self):
        for raw in ("1", "true", "ON", "yes"):
            with patch.dict(os.environ, {"SSH_PLUGIN_BRIDGE": raw}):
                self.assertTrue(ssh_bridge.bridge_enabled(), raw)
        with patch.dict(os.environ, {"SSH_PLUGIN_BRIDGE": "0"}):
            self.assertFalse(ssh_bridge.bridge_enabled())


class TestWorkerProtocol(unittest.TestCase):
    def test_unknown_op(self):
        msg = ssh_bridge_worker.handle_line(json.dumps({"id": 1, "op": "nope", "payload": {}}))
        self.assertFalse(msg["ok"])
        self.assertIn("unknown op", msg["error"])

    def test_invalid_json(self):
        msg = ssh_bridge_worker.handle_line("{not-json")
        self.assertFalse(msg["ok"])

    def test_list_dir_handler(self):
        fake = {"entries": [{"name": "a.txt", "type": "file"}], "path": "/"}
        with patch.object(ssh_bridge_worker.sftp_client, "list_dir", return_value=fake):
            result = ssh_bridge_worker.handle_line(
                json.dumps({"id": 2, "op": "list_dir", "payload": {"server": {"id": "s"}, "path": "/"}})
            )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["result"]["entries"][0]["name"], "a.txt")

    def test_call_spawns_worker_error_envelope(self):
        ssh_bridge.stop_worker()
        try:
            ssh_bridge.call("no_such_op", {}, timeout=20)
            self.fail("expected BridgeError")
        except ssh_bridge.BridgeError as exc:
            self.assertIn("unknown op", str(exc))
        finally:
            ssh_bridge.stop_worker()

    def test_persistent_worker_reused(self):
        ssh_bridge.stop_worker()
        try:
            try:
                ssh_bridge.call("no_such_op", {}, timeout=20)
            except ssh_bridge.BridgeError:
                pass
            proc1 = ssh_bridge._PROC
            self.assertIsNotNone(proc1)
            self.assertIsNone(proc1.poll())
            try:
                ssh_bridge.call("also_bad", {}, timeout=20)
            except ssh_bridge.BridgeError:
                pass
            self.assertIs(ssh_bridge._PROC, proc1)
        finally:
            ssh_bridge.stop_worker()

    def test_oneshot_does_not_keep_worker(self):
        ssh_bridge.stop_worker()
        with patch.dict(os.environ, {"SSH_PLUGIN_BRIDGE_ONESHOT": "1"}):
            try:
                ssh_bridge.call("no_such_op", {}, timeout=20)
            except ssh_bridge.BridgeError:
                pass
        self.assertIsNone(ssh_bridge._PROC)


class TestPluginApiRemoteDispatch(unittest.IsolatedAsyncioTestCase):
    async def test_remote_uses_inprocess_when_bridge_off(self):
        from dashboard import plugin_api as api

        with patch.dict(os.environ, {"SSH_PLUGIN_BRIDGE": "0"}):
            mocked = lambda p: {"ok": True}  # noqa: E731
            with patch.dict(api._INPROCESS_OPS, {"health": mocked}):
                out = await api._remote("health", {"server": {"id": "x"}})
        self.assertTrue(out["ok"])

    async def test_remote_uses_bridge_when_enabled(self):
        from dashboard import plugin_api as api

        with patch.dict(os.environ, {"SSH_PLUGIN_BRIDGE": "1"}):
            with patch("ssh_bridge.call", return_value={"ok": True}) as bridge_mock:
                out = await api._remote("health", {"server": {"id": "x"}})
        self.assertTrue(out["ok"])
        bridge_mock.assert_called_once_with("health", {"server": {"id": "x"}})


if __name__ == "__main__":
    unittest.main()
