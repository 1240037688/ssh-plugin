"""Optional subprocess bridge for paramiko-backed SSH operations.

When ``SSH_PLUGIN_BRIDGE`` is truthy, REST handlers run SSH/SFTP work in a
helper process instead of the gateway thread pool. Default is off (in-process).

Protocol: one JSON object per line on stdin → one JSON line on stdout.

Worker lifetime:
- **Persistent (default when bridge is on)** — one long-lived worker is reused
  across calls so the child's SSH session pool (keepalive) can survive between
  REST requests. Requests are serialized with a lock.
- **One-shot** — set ``SSH_PLUGIN_BRIDGE_ONESHOT=1`` to spawn a fresh process
  per call (maximum isolation, no cross-request keepalive).
- If the persistent worker dies or times out, the next call restarts it.
"""

from __future__ import annotations

import atexit
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent
_WORKER = _ROOT / "ssh_bridge_worker.py"
_LOCK = threading.RLock()
_SEQ = 0
_PROC: subprocess.Popen[str] | None = None

DEFAULT_TIMEOUT_S = 90.0


class BridgeError(RuntimeError):
    pass


def bridge_enabled() -> bool:
    raw = (os.environ.get("SSH_PLUGIN_BRIDGE") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def oneshot_enabled() -> bool:
    raw = (os.environ.get("SSH_PLUGIN_BRIDGE_ONESHOT") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _worker_cmd() -> list[str]:
    return [sys.executable, "-u", str(_WORKER)]


def _worker_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("SSH_PLUGIN_BRIDGE", None)
    env["PYTHONPATH"] = str(_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _spawn() -> subprocess.Popen[str]:
    try:
        return subprocess.Popen(
            _worker_cmd(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            env=_worker_env(),
            cwd=str(_ROOT),
            bufsize=1,
        )
    except OSError as exc:
        raise BridgeError(f"failed to start ssh bridge worker: {exc}") from exc


def _kill(proc: subprocess.Popen[str] | None) -> None:
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=2)
    except Exception:
        pass
    for stream in (proc.stdin, proc.stdout, proc.stderr):
        try:
            if stream is not None:
                stream.close()
        except Exception:
            pass


def stop_worker() -> None:
    """Stop the persistent worker (used by tests and process exit)."""
    global _PROC
    with _LOCK:
        _kill(_PROC)
        _PROC = None


atexit.register(stop_worker)


def _ensure_worker() -> subprocess.Popen[str]:
    global _PROC
    if _PROC is not None and _PROC.poll() is None and _PROC.stdin and _PROC.stdout:
        return _PROC
    _kill(_PROC)
    _PROC = _spawn()
    return _PROC


def _read_line(stream: Any, timeout: float, op: str) -> str:
    """Read one line with a timeout (Windows pipes are not select()-able)."""
    box: list[str] = []

    def _target() -> None:
        try:
            box.append(stream.readline())
        except Exception:
            box.append("")

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise BridgeError(f"ssh bridge op timed out after {timeout:.0f}s: {op}")
    line = box[0] if box else ""
    return (line or "").strip()


def _parse_result(line: str, op: str) -> Any:
    if not line:
        raise BridgeError(f"ssh bridge produced no result: {op}")
    try:
        msg = json.loads(line)
    except json.JSONDecodeError as exc:
        raise BridgeError(f"ssh bridge returned invalid JSON: {line[:200]}") from exc
    if not msg.get("ok"):
        raise BridgeError(str(msg.get("error") or "bridge op failed"))
    return msg.get("result")


def _call_oneshot(op: str, payload: dict[str, Any], req_id: int, timeout: float) -> Any:
    request = json.dumps({"id": req_id, "op": op, "payload": payload}, ensure_ascii=False)
    proc = _spawn()
    try:
        out, _err = proc.communicate(request + "\n", timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _kill(proc)
        raise BridgeError(f"ssh bridge op timed out after {timeout:.0f}s: {op}") from exc
    line = ""
    for candidate in (out or "").splitlines():
        if candidate.strip():
            line = candidate.strip()
            break
    return _parse_result(line, op)


def _call_persistent(op: str, payload: dict[str, Any], req_id: int, timeout: float) -> Any:
    global _PROC
    request = json.dumps({"id": req_id, "op": op, "payload": payload}, ensure_ascii=False)
    with _LOCK:
        proc = _ensure_worker()
        assert proc.stdin is not None and proc.stdout is not None
        try:
            proc.stdin.write(request + "\n")
            proc.stdin.flush()
            line = _read_line(proc.stdout, timeout, op)
        except BridgeError:
            _kill(proc)
            _PROC = None
            raise
        except Exception as exc:
            _kill(proc)
            _PROC = None
            raise BridgeError(f"ssh bridge worker I/O failed: {exc}") from exc
        if proc.poll() is not None and not line:
            _PROC = None
            raise BridgeError(f"ssh bridge worker exited while handling {op}")
        return _parse_result(line, op)


def call(op: str, payload: dict[str, Any], *, timeout: float = DEFAULT_TIMEOUT_S) -> Any:
    """Run one op via the bridge. Thread-safe."""
    global _SEQ
    if not op or not isinstance(payload, dict):
        raise BridgeError("invalid bridge request")
    with _LOCK:
        _SEQ += 1
        req_id = _SEQ
    if oneshot_enabled():
        return _call_oneshot(op, payload, req_id, timeout)
    return _call_persistent(op, payload, req_id, timeout)
