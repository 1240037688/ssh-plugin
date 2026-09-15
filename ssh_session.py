"""Per-server SSH/SFTP session pool with keepalive and one-shot reconnect."""

from __future__ import annotations

import threading
import time
from typing import Any

try:
    import paramiko
except ImportError:  # pragma: no cover
    paramiko = None  # type: ignore

from pathlib import Path

KEEPALIVE_INTERVAL = 15
KEEPALIVE_COUNT_MAX = 3


class SessionError(Exception):
    pass


class _Entry:
    __slots__ = ("client", "sftp", "lock", "last_ok", "connect_ms", "server_id")

    def __init__(self) -> None:
        self.client = None
        self.sftp = None
        self.lock = threading.RLock()
        self.last_ok: float | None = None
        self.connect_ms: float | None = None
        self.server_id: str | None = None


_pool: dict[str, _Entry] = {}
_pool_lock = threading.RLock()


def _require_pk():
    if paramiko is None:
        raise SessionError("paramiko is not installed in the Hermes gateway environment")
    return paramiko


def _connect_kwargs(server: dict[str, Any]) -> dict[str, Any]:
    pk = _require_pk()
    host = server.get("host")
    if not host:
        raise SessionError("server host is empty")
    # Default 10s — a hung handshake must not pin a worker for 30s.
    timeout = float(server.get("connectionTimeoutMs") or 10000) / 1000.0
    kwargs: dict[str, Any] = {
        "hostname": host,
        "port": int(server.get("port") or 22),
        "username": server.get("username") or "",
        "timeout": timeout,
        "banner_timeout": timeout,
        "auth_timeout": timeout,
        "allow_agent": False,
        "look_for_keys": False,
    }
    auth = (server.get("auth") or "password").lower()
    if auth == "key":
        key_path = server.get("privateKey")
        passphrase = server.get("passphrase") or None
        content = server.get("privateKeyContent")
        if content:
            data = __import__("io").StringIO(content)
        elif key_path and key_path != "***":
            data = open(str(key_path).expanduser(), "r", encoding="utf-8")
        else:
            raise SessionError("privateKey path is required for key auth")
        key = None
        try:
            for loader in (
                pk.RSAKey,
                getattr(pk, "Ed25519Key", None),
                getattr(pk, "ECDSAKey", None),
                getattr(pk, "DSSKey", None),
            ):
                if loader is None:
                    continue
                try:
                    data.seek(0)
                    key = loader.from_private_key(data, password=passphrase)
                    break
                except Exception:
                    continue
        finally:
            try:
                data.close()
            except Exception:
                pass
        if key is None:
            raise SessionError("unable to load private key")
        kwargs["pkey"] = key
    elif auth == "agent":
        kwargs["allow_agent"] = True
        kwargs["look_for_keys"] = True
    else:
        password = server.get("password")
        if password == "***":
            password = None
        kwargs["password"] = password or None
    return kwargs


def _open(server: dict[str, Any]) -> tuple[Any, Any, float]:
    pk = _require_pk()
    t0 = time.perf_counter()
    client = pk.SSHClient()
    known = Path.home() / ".ssh" / "known_hosts"
    if known.is_file():
        try:
            client.load_host_keys(str(known))
            client.set_missing_host_key_policy(pk.RejectPolicy())
        except Exception:
            client.set_missing_host_key_policy(pk.AutoAddPolicy())
    else:
        client.set_missing_host_key_policy(pk.AutoAddPolicy())
    client.connect(**_connect_kwargs(server))
    client.get_transport().set_keepalive(
        int(server.get("keepaliveIntervalMs") or KEEPALIVE_INTERVAL * 1000) // 1000 or KEEPALIVE_INTERVAL
    )
    sftp = client.open_sftp()
    ms = (time.perf_counter() - t0) * 1000.0
    return client, sftp, ms


def _close_quiet(entry: _Entry) -> None:
    try:
        if entry.sftp is not None:
            entry.sftp.close()
    except Exception:
        pass
    try:
        if entry.client is not None:
            entry.client.close()
    except Exception:
        pass
    entry.sftp = None
    entry.client = None


def _entry_for(server: dict[str, Any]) -> _Entry:
    key = str(server.get("id") or server.get("name") or server.get("host") or "default")
    with _pool_lock:
        entry = _pool.get(key)
        if entry is None:
            entry = _Entry()
            entry.server_id = key
            _pool[key] = entry
        return entry


def _alive(transport) -> bool:
    try:
        return bool(transport and transport.is_active())
    except Exception:
        return False


def get_session(server: dict[str, Any], *, force_new: bool = False):
    """Yield (sftp, client) under the per-server lock. Caller must stay in `with`."""
    try:
        from .vault_secrets import resolve_server_secrets
    except ImportError:
        from vault_secrets import resolve_server_secrets  # type: ignore
    server = resolve_server_secrets(server)
    entry = _entry_for(server)

    class _Ctx:
        def __enter__(self):
            entry.lock.acquire()
            try:
                if force_new:
                    _close_quiet(entry)
                if entry.sftp is None or entry.client is None or not _alive(entry.client.get_transport()):
                    _close_quiet(entry)
                    client, sftp, ms = _open(server)
                    entry.client, entry.sftp, entry.connect_ms = client, sftp, ms
                try:
                    # cheap probe — catches half-open sockets
                    entry.sftp.listdir(".")
                except Exception:
                    _close_quiet(entry)
                    client, sftp, ms = _open(server)
                    entry.client, entry.sftp, entry.connect_ms = client, sftp, ms
                entry.last_ok = time.time()
                return entry.sftp, entry.client
            except Exception:
                entry.lock.release()
                raise

        def __exit__(self, *args):
            entry.lock.release()
            return False

    return _Ctx()


def with_sftp(server: dict[str, Any], fn):
    """Run fn(sftp) with pool + one reconnect retry."""
    last: Exception | None = None
    for attempt in (0, 1):
        try:
            with get_session(server, force_new=attempt == 1) as (sftp, _client):
                return fn(sftp)
        except Exception as exc:  # noqa: BLE001 — reconnect once
            last = exc
            continue
    raise SessionError(str(last) if last else "sftp failed")


def with_ssh(server: dict[str, Any], fn):
    """Run fn(client) for exec_channel style work; same retry policy."""
    last: Exception | None = None
    for attempt in (0, 1):
        try:
            with get_session(server, force_new=attempt == 1) as (_sftp, client):
                return fn(client)
        except Exception as exc:  # noqa: BLE001
            last = exc
            continue
    raise SessionError(str(last) if last else "ssh failed")


def health(server: dict[str, Any]) -> dict[str, Any]:
    entry = _entry_for(server)
    t0 = time.perf_counter()
    try:
        def _probe(sftp):
            sftp.stat(".")
            return True

        with_sftp(server, _probe)
        latency = (time.perf_counter() - t0) * 1000.0
        return {
            "ok": True,
            "serverId": entry.server_id,
            "latencyMs": round(latency, 1),
            "connectMs": round(entry.connect_ms or 0, 1),
            "reused": entry.last_ok is not None,
            "pooled": entry.client is not None and _alive(entry.client.get_transport()),
        }
    except Exception as exc:
        return {
            "ok": False,
            "serverId": entry.server_id,
            "error": str(exc),
            "pooled": False,
        }


def stats() -> dict[str, Any]:
    with _pool_lock:
        out = []
        for key, entry in _pool.items():
            try:
                active = entry.client is not None and _alive(entry.client.get_transport())
            except Exception:
                active = False
            out.append(
                {
                    "serverId": key,
                    "pooled": active,
                    "lastOk": entry.last_ok,
                    "connectMs": entry.connect_ms,
                }
            )
        return {"servers": out}


def close_all() -> None:
    with _pool_lock:
        for entry in _pool.values():
            with entry.lock:
                _close_quiet(entry)
        _pool.clear()
