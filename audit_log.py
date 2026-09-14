"""Append-only JSONL audit log for SSH plugin mutations (no secrets)."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
# Never write these keys even if a caller passes them by mistake
_BANNED = frozenset({"password", "passphrase", "privateKey", "privateKeyContent", "content", "contentBase64", "secret"})


def audit_path() -> Path:
    home = os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    root = Path(home) / "plugin-data" / "ssh-plugin"
    root.mkdir(parents=True, exist_ok=True)
    return root / "audit.jsonl"


def _sanitize(detail: dict[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in (detail or {}).items():
        if k in _BANNED:
            continue
        if isinstance(v, str) and len(v) > 500:
            v = v[:500] + "…"
        out[k] = v
    return out


def record(
    op: str,
    *,
    server_id: str | None = None,
    server_name: str | None = None,
    path: str | None = None,
    ok: bool = True,
    source: str = "plugin",
    detail: dict[str, Any] | None = None,
    **extra: Any,
) -> None:
    """Best-effort append one audit line. Never raises to callers."""
    merged = dict(detail or {})
    merged.update(extra or {})
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()) + f".{int(time.time() * 1000) % 1000:03d}",
        "op": op,
        "serverId": server_id,
        "serverName": server_name,
        "path": path,
        "ok": bool(ok),
        "source": source,
        "detail": _sanitize(merged),
    }
    line = json.dumps(entry, ensure_ascii=False)
    try:
        with _LOCK:
            p = audit_path()
            with p.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
    except OSError:
        pass


def tail(n: int = 50) -> list[dict[str, Any]]:
    """Read last n audit entries (for Desktop / debugging)."""
    p = audit_path()
    if not p.exists():
        return []
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out: list[dict[str, Any]] = []
    for line in lines[-max(0, int(n)) :]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
