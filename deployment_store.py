"""Persist SSH server / mapping config under HERMES_HOME plugin-data."""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

_LOCK = threading.RLock()
_SECRET_FIELDS = frozenset({"password", "passphrase", "privateKeyContent"})


def plugin_data_dir() -> Path:
    home = os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    root = Path(home) / "plugin-data" / "ssh-plugin"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _store_path() -> Path:
    return plugin_data_dir() / "deployments.json"


def _empty() -> dict[str, Any]:
    return {"servers": [], "defaultServerId": None}


def _normalize_server(raw: dict[str, Any]) -> dict[str, Any]:
    auth = str(raw.get("auth") or "password").lower()
    if auth not in {"password", "key", "agent"}:
        auth = "password"
    server = {
        "id": str(raw.get("id") or f"srv_{uuid.uuid4().hex[:10]}"),
        "name": str(raw.get("name") or "server").strip() or "server",
        "host": str(raw.get("host") or "").strip(),
        "port": int(raw.get("port") or 22),
        "username": str(raw.get("username") or "").strip(),
        "auth": auth,
        "password": raw.get("password") or None,
        "privateKey": raw.get("privateKey") or None,
        "passphrase": raw.get("passphrase") or None,
        "mappings": [],
        "exclusions": [],
        "allowedRemotePaths": [],
        "allow_exec": bool(raw.get("allow_exec") or raw.get("allowExec") or False),
    }
    for m in raw.get("mappings") or []:
        if not isinstance(m, dict):
            continue
        local = str(m.get("localRoot") or "").strip()
        remote = str(m.get("remoteRoot") or "").strip()
        if local and remote:
            server["mappings"].append({"localRoot": local, "remoteRoot": remote})
    for e in raw.get("exclusions") or []:
        s = str(e).strip()
        if s:
            server["exclusions"].append(s)
    for p in raw.get("allowedRemotePaths") or []:
        s = str(p).strip()
        if s:
            server["allowedRemotePaths"].append(s)
    return server


def load() -> dict[str, Any]:
    with _LOCK:
        path = _store_path()
        if not path.exists():
            return _empty()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return _empty()
        if not isinstance(data, dict):
            return _empty()
        servers = [_normalize_server(s) for s in data.get("servers") or [] if isinstance(s, dict)]
        return {"servers": servers, "defaultServerId": data.get("defaultServerId")}


def save(data: dict[str, Any]) -> None:
    with _LOCK:
        path = _store_path()
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)


def public_server(server: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(server)
    for key in _SECRET_FIELDS:
        if out.get(key):
            out[key] = "***"
    return out


def list_servers() -> list[dict[str, Any]]:
    data = load()
    return [public_server(s) for s in data["servers"]]


def get_server(server_id: str) -> dict[str, Any] | None:
    data = load()
    for s in data["servers"]:
        if s["id"] == server_id or s["name"] == server_id:
            return s
    return None


def upsert_server(payload: dict[str, Any]) -> dict[str, Any]:
    incoming = _normalize_server(payload or {})
    if not incoming["host"] or not incoming["username"]:
        raise ValueError("host and username are required")
    with _LOCK:
        data = load()
        existing = None
        idx = None
        for i, s in enumerate(data["servers"]):
            if s["id"] == incoming["id"] or (payload.get("id") and s["id"] == payload.get("id")):
                existing, idx = s, i
                break
        if existing is not None:
            # Empty / omitted / masked secrets mean "keep previous value".
            # Only a non-empty non-placeholder overwrites.
            for secret in ("password", "passphrase", "privateKey"):
                if incoming.get(secret) in (None, "", "***"):
                    incoming[secret] = existing.get(secret)
            data["servers"][idx] = incoming
        else:
            data["servers"].append(incoming)
        if not data.get("defaultServerId"):
            data["defaultServerId"] = incoming["id"]
        save(data)
    return public_server(incoming)


def delete_server(server_id: str) -> bool:
    with _LOCK:
        data = load()
        before = len(data["servers"])
        data["servers"] = [s for s in data["servers"] if s["id"] != server_id]
        if data.get("defaultServerId") == server_id:
            data["defaultServerId"] = data["servers"][0]["id"] if data["servers"] else None
        save(data)
        return len(data["servers"]) != before


def set_default(server_id: str) -> bool:
    with _LOCK:
        data = load()
        if not any(s["id"] == server_id for s in data["servers"]):
            return False
        data["defaultServerId"] = server_id
        save(data)
        return True


def set_mappings(server_id: str, mappings: list[dict], exclusions: list[str]) -> dict[str, Any]:
    with _LOCK:
        data = load()
        for s in data["servers"]:
            if s["id"] == server_id:
                norm = _normalize_server({**s, "mappings": mappings or [], "exclusions": exclusions or []})
                s["mappings"] = norm["mappings"]
                s["exclusions"] = norm["exclusions"]
                save(data)
                return public_server(s)
    raise ValueError("server not found")


def safe_remote_path(path: str, allowed: list[str] | None) -> str:
    p = (path or "/").replace("\\", "/")
    if "\x00" in p:
        raise ValueError("invalid path")
    if not p.startswith("/"):
        p = "/" + p
    # Collapse . and reject ..
    parts: list[str] = []
    for seg in p.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            raise ValueError("path traversal is not allowed")
        parts.append(seg)
    resolved = "/" + "/".join(parts)
    if allowed:
        ok = False
        for prefix in allowed:
            pref = prefix.rstrip("/") or "/"
            if resolved == pref or resolved.startswith(pref if pref.endswith("/") else pref + "/") or pref == "/":
                ok = True
                break
        if not ok:
            raise ValueError(f"path not in allowedRemotePaths: {resolved}")
    return resolved if resolved != "/" else "/"


def match_exclusion(rel_path: str, patterns: list[str]) -> bool:
    """Very small glob subset: * and ** against POSIX-style relative paths."""
    rel = rel_path.replace("\\", "/").lstrip("/")
    for pat in patterns or []:
        pat = pat.replace("\\", "/").strip()
        if not pat:
            continue
        if _glob_match(rel, pat) or _glob_match(rel, pat.rstrip("/")):
            return True
        # dir/** should also hide the directory entry itself
        if pat.endswith("/**"):
            base = pat[:-3].rstrip("/")
            if base and (rel == base or rel.startswith(base + "/")):
                return True
        # basename match for patterns like *.pyc
        if "/" not in pat.rstrip("/") and _glob_match(rel.split("/")[-1], pat):
            return True
    return False


def _glob_match(text: str, pattern: str) -> bool:
    # Translate simplified glob to regex
    i = 0
    out = []
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return re.fullmatch("".join(out), text or "") is not None
