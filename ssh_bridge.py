"""Optional subprocess bridge for paramiko-backed SSH operations.

When ``SSH_PLUGIN_BRIDGE`` is truthy, REST handlers run SSH/SFTP work in a
short-lived helper process instead of the gateway thread pool. A hung
handshake or crash stays in the child; the parent only sees a structured
error. Default is off (in-process) for compatibility.

Protocol: one JSON object per line on stdin → one JSON line on stdout.
``{"id": n, "op": "list_dir", "payload": {...}}`` →
``{"id": n, "ok": true, "result": ...}`` or ``{"id": n, "ok": false, "error": "..."}``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent
_WORKER = _ROOT / "ssh_bridge_worker.py"
_LOCK = threading.Lock()
_SEQ = 0

DEFAULT_TIMEOUT_S = 90.0


class BridgeError(RuntimeError):
    pass


def bridge_enabled() -> bool:
    raw = (os.environ.get("SSH_PLUGIN_BRIDGE") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _worker_cmd() -> list[str]:
    return [sys.executable, str(_WORKER)]


def call(op: str, payload: dict[str, Any], *, timeout: float = DEFAULT_TIMEOUT_S) -> Any:
    """Run one op in a fresh worker process. Thread-safe."""
    global _SEQ
    if not op or not isinstance(payload, dict):
        raise BridgeError("invalid bridge request")
    with _LOCK:
        _SEQ += 1
        req_id = _SEQ
    request = json.dumps({"id": req_id, "op": op, "payload": payload}, ensure_ascii=False)
    env = os.environ.copy()
    env.pop("SSH_PLUGIN_BRIDGE", None)
    env["PYTHONPATH"] = str(_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    try:
        proc = subprocess.Popen(
            _worker_cmd(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=env,
            cwd=str(_ROOT),
        )
    except OSError as exc:
        raise BridgeError(f"failed to start ssh bridge worker: {exc}") from exc
    try:
        out, err = proc.communicate(request + "\n", timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        proc.kill()
        proc.communicate()
        raise BridgeError(f"ssh bridge op timed out after {timeout:.0f}s: {op}") from exc
    if proc.returncode not in (0, None) and not out.strip():
        detail = (err or "").strip()[-400:]
        raise BridgeError(f"ssh bridge worker exited {proc.returncode}: {detail}")
    line = ""
    for candidate in out.splitlines():
        if candidate.strip():
            line = candidate.strip()
            break
    if not line:
        detail = (err or "").strip()[-400:]
        raise BridgeError(f"ssh bridge produced no result: {detail}")
    try:
        msg = json.loads(line)
    except json.JSONDecodeError as exc:
        raise BridgeError(f"ssh bridge returned invalid JSON: {line[:200]}") from exc
    if not msg.get("ok"):
        raise BridgeError(str(msg.get("error") or "bridge op failed"))
    return msg.get("result")
