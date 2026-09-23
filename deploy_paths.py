"""Host masking for agent-facing payloads + PyCharm-style path mapping."""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any


def mask_host(host: str) -> str:
    """Keep a stable opaque token; never echo the raw address to the agent."""
    if not host:
        return ""
    if host.startswith("***"):
        return host
    return "***"


# Secret material — never returned to the agent, not even as "***".
_SECRET_KEYS = ("password", "passphrase", "privateKey", "privateKeyContent")
# Derived strings that can leak host/user when unmask=false.
_LEAKY_KEYS = (
    "endpoint",
    "connectionString",
    "userHost",
    "hostPort",
    "host_port",
    "user@host",
)


def agent_public_server(server: dict[str, Any]) -> dict[str, Any]:
    """Minimal safe shape for LLM / ssh_list_servers (default, unmask=false).

    Returns only name / configured / allow_exec. No host, port, username,
    password (or "***"), and no derived endpoint / connectionString / userHost.
    """
    name = str(server.get("name") or server.get("id") or "")
    return {
        "name": name,
        "configured": True,
        "allow_exec": bool(server.get("allow_exec")),
    }


def agent_unmask_server(server: dict[str, Any]) -> dict[str, Any]:
    """Operator-explicit unmask=true: real host/user, still no secrets.

    Also drops derived leak keys so unmask does not add connectionString etc.
    """
    out = deepcopy(server)
    for key in _SECRET_KEYS:
        out.pop(key, None)
    for key in _LEAKY_KEYS:
        out.pop(key, None)
    out["host"] = str(out.get("host") or "")
    out["username"] = str(out.get("username") or "")
    out["port"] = out.get("port") or 22
    return out


def agent_list_servers(servers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [agent_public_server(s) for s in servers]


def _norm_local(p: str) -> str:
    return str(p or "").replace("/", "\\").rstrip("\\") or ""


def _norm_remote(p: str) -> str:
    s = str(p or "").replace("\\", "/")
    if not s.startswith("/"):
        s = "/" + s
    return str(PurePosixPath(s))


def map_local_to_remote(server: dict[str, Any], local_path: str) -> dict[str, Any]:
    """Resolve local path via mappings (longest localRoot wins)."""
    local = _norm_local(local_path)
    best: dict[str, Any] | None = None
    for m in server.get("mappings") or []:
        root = _norm_local(m.get("localRoot") or "")
        if not root:
            continue
        root_l = root.lower()
        loc_l = local.lower()
        if loc_l == root_l or loc_l.startswith(root_l + "\\"):
            rel = local[len(root) :].lstrip("\\/")
            remote = _norm_remote(str(m.get("remoteRoot") or "").rstrip("/") + "/" + rel.replace("\\", "/"))
            cand = {
                "localPath": local_path,
                "remotePath": remote,
                "localRoot": m.get("localRoot"),
                "remoteRoot": m.get("remoteRoot"),
            }
            if best is None or len(_norm_local(m.get("localRoot") or "")) > len(
                _norm_local(best.get("localRoot") or "")
            ):
                best = cand
    if best is None:
        return {"ok": False, "error": "local path is not under any mapping", "localPath": local_path}
    return {"ok": True, **best}


def map_remote_to_local(server: dict[str, Any], remote_path: str) -> dict[str, Any]:
    remote = _norm_remote(remote_path)
    best: dict[str, Any] | None = None
    for m in server.get("mappings") or []:
        root = _norm_remote(m.get("remoteRoot") or "")
        if not root or root == "/":
            # skip empty/root-only unless exact
            if remote == root:
                pass
            else:
                continue
        if remote == root or remote.startswith(root.rstrip("/") + "/"):
            rel = remote[len(root) :].lstrip("/")
            local_root = _norm_local(m.get("localRoot") or "")
            local = str(PureWindowsPath(local_root) / PurePosixPath(rel).as_posix().replace("/", "\\")) if local_root else ""
            cand = {
                "remotePath": remote,
                "localPath": local,
                "localRoot": m.get("localRoot"),
                "remoteRoot": m.get("remoteRoot"),
            }
            if best is None or len(_norm_remote(m.get("remoteRoot") or "")) > len(
                _norm_remote(best.get("remoteRoot") or "")
            ):
                best = cand
    if best is None:
        return {"ok": False, "error": "remote path is not under any mapping", "remotePath": remote_path}
    return {"ok": True, **best}


def unified_diff(old: str, new: str, path: str, context: int = 3, max_lines: int = 400) -> dict[str, Any]:
    """Compact unified-style diff for write preview (no external deps)."""
    import difflib

    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    if old and not old.endswith("\n"):
        old_lines.append("\n")
    if new and not new.endswith("\n"):
        new_lines.append("\n")
    diff = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            n=context,
        )
    )
    truncated = len(diff) > max_lines
    text = "".join(diff[:max_lines] if truncated else diff)
    added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
    return {
        "path": path,
        "diff": text,
        "addedLines": added,
        "removedLines": removed,
        "identical": old == new,
        "truncated": truncated,
        "emptyRemote": old == "",
    }
