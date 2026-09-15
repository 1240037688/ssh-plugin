"""Hermes SSH Deploy backend adapter (mounted at /api/plugins/ssh-plugin/).

Security model (aligned with hermes-vault desktop adapter conventions):
- Secrets never appear in REST list/upsert responses (masked ``***``).
- Remote paths are canonicalized; ``..`` / NUL rejected; optional
  ``allowedRemotePaths`` prefix allowlist.
- Local upload/download paths constrained by ``allowedLocalPaths`` + process cwd.
- ``ssh_exec`` gated by ``allow_exec`` + optional command whitelist/blacklist.
- Host header must be loopback unless the app records an explicit bound host
  (DNS-rebinding / R1 hardening, same idea as hermes-vault-desktop).
- Failures return structured HTTP errors; connection ops surface backend detail
  without echoing credentials.
"""

from __future__ import annotations

import asyncio
import base64
import errno
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

_T = TypeVar("_T")

# Paramiko is blocking; keep it off the uvicorn event loop so a slow/hung
# SSH handshake cannot freeze /health and the rest of the plugin REST API.
_SSH_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="ssh-plugin")


async def _ssh_call(fn: Callable[..., _T], /, *args: Any, **kwargs: Any) -> _T:
    loop = asyncio.get_running_loop()
    if kwargs:
        return await loop.run_in_executor(_SSH_EXECUTOR, lambda: fn(*args, **kwargs))
    return await loop.run_in_executor(_SSH_EXECUTOR, fn, *args)


async def _remote(op: str, payload: dict[str, Any]) -> Any:
    """Run an SSH op in-process, or via subprocess bridge when enabled."""
    try:
        from ssh_bridge import bridge_enabled, call as bridge_call
    except ImportError:
        from ..ssh_bridge import bridge_enabled, call as bridge_call  # type: ignore
    if bridge_enabled():
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_SSH_EXECUTOR, bridge_call, op, payload)
    handler = _INPROCESS_OPS[op]
    return await _ssh_call(handler, payload)


def _in_list_dir(p: dict[str, Any]) -> Any:
    return sftp_client.list_dir(p["server"], p["path"])


def _in_read_text(p: dict[str, Any]) -> Any:
    if p.get("offset") is not None or p.get("limit") is not None:
        return sftp_client.read_text_chunk(
            p["server"],
            p["path"],
            offset=int(p.get("offset") or 0),
            limit=int(p.get("limit") or sftp_client.CHUNK_DEFAULT),
        )
    return sftp_client.read_text(p["server"], p["path"])


def _in_write_text(p: dict[str, Any]) -> Any:
    return sftp_client.write_text(p["server"], p["path"], p.get("content") or "")


def _in_mkdir(p: dict[str, Any]) -> Any:
    return sftp_client.mkdir(p["server"], p["path"])


def _in_delete(p: dict[str, Any]) -> Any:
    return sftp_client.delete(p["server"], p["path"], recursive=bool(p.get("recursive")))


def _in_rename(p: dict[str, Any]) -> Any:
    return sftp_client.rename(p["server"], p["src"], p["dst"])


def _in_upload(p: dict[str, Any]) -> Any:
    return sftp_client.upload_bytes(p["server"], p["path"], p["data"])


def _in_download(p: dict[str, Any]) -> Any:
    return sftp_client.download_bytes(p["server"], p["path"])


def _in_preview(p: dict[str, Any]) -> Any:
    return sftp_client.preview_image(p["server"], p["path"])


def _in_test(p: dict[str, Any]) -> Any:
    return sftp_client.test_connection(p["server"])


def _in_health(p: dict[str, Any]) -> Any:
    return sftp_client.health_check(p["server"])


def _in_download_tree(p: dict[str, Any]) -> Any:
    from download_plan import download_tree

    return download_tree(
        p["server"],
        p["remoteRoot"],
        p["localRoot"],
        dry_run=bool(p.get("dryRun", True)),
        max_files=int(p.get("maxFiles") or 500),
        max_entries=int(p.get("maxEntries") or 10000),
    )


def _in_sync_plan(p: dict[str, Any]) -> Any:
    from sync_plan import plan_sync

    return plan_sync(
        p["server"],
        p["localRoot"],
        dry_run=bool(p.get("dryRun", True)),
        max_files=int(p.get("maxFiles") or 500),
        expected_files=p.get("expectedFiles"),
    )


def _in_exec(p: dict[str, Any]) -> Any:
    return sftp_client.exec_command(p["server"], p["command"], timeout=int(p.get("timeout") or 30))


_INPROCESS_OPS: dict[str, Callable[[dict[str, Any]], Any]] = {
    "list_dir": _in_list_dir,
    "read_text": _in_read_text,
    "write_text": _in_write_text,
    "mkdir": _in_mkdir,
    "delete": _in_delete,
    "rename": _in_rename,
    "upload": _in_upload,
    "download": _in_download,
    "preview": _in_preview,
    "test": _in_test,
    "health": _in_health,
    "download_tree": _in_download_tree,
    "sync_plan": _in_sync_plan,
    "exec": _in_exec,
}

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import deployment_store  # noqa: E402
import sftp_client  # noqa: E402

try:
    from security import security_warnings
except ImportError:
    from ..security import security_warnings  # type: ignore

try:
    from deploy_paths import agent_list_servers, map_local_to_remote, map_remote_to_local, unified_diff
except ImportError:
    from ..deploy_paths import (  # type: ignore
        agent_list_servers,
        map_local_to_remote,
        map_remote_to_local,
        unified_diff,
    )

try:
    from audit_log import record as audit_record, tail as audit_tail
except ImportError:
    from ..audit_log import record as audit_record, tail as audit_tail  # type: ignore


def _audit(op: str, server: dict[str, Any] | None, path: str | None, ok: bool = True, **detail: Any) -> None:
    audit_record(
        op,
        server_id=(server or {}).get("id"),
        server_name=(server or {}).get("name"),
        path=path,
        ok=ok,
        source="rest",
        detail=detail,
    )

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})


def _host_only(host_header: str) -> str:
    h = (host_header or "").strip()
    if h.startswith("["):
        close = h.find("]")
        if close != -1:
            return h[1:close].lower()
        return h.strip("[]").lower()
    if ":" in h:
        return h.rsplit(":", 1)[0].lower()
    return h.lower()


def _validate_host_header(request: Request) -> None:
    host = request.headers.get("host", "")
    if not host:
        return
    if _host_only(host) in LOOPBACK_HOSTS:
        return
    bound_host = getattr(request.app.state, "bound_host", None)
    if bound_host and _host_only(host) == _host_only(str(bound_host)):
        return
    # Wildcard binds are operator opt-in; skip host-layer reject to match host app.
    if bound_host in ("0.0.0.0", "::", "[::]"):
        return
    raise HTTPException(status_code=400, detail="invalid Host header")


router = APIRouter(dependencies=[Depends(_validate_host_header)])


def _server_or_404(server_id: str) -> dict[str, Any]:
    server = deployment_store.get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail=f"server not found: {server_id}")
    return server


def _safe_path(server: dict[str, Any], path: str) -> str:
    try:
        return deployment_store.safe_remote_path(path, server.get("allowedRemotePaths") or None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _err(exc: Exception, status: int = 500) -> HTTPException:
    return HTTPException(status_code=status, detail=str(exc))


class ServerIn(BaseModel):
    id: str | None = None
    name: str = "server"
    host: str
    port: int = 22
    username: str
    auth: str = "password"
    password: str | None = None
    privateKey: str | None = None
    passphrase: str | None = None
    mappings: list[dict[str, Any]] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    allowedRemotePaths: list[str] = Field(default_factory=list)
    allowedLocalPaths: list[str] = Field(default_factory=list)
    commandWhitelist: list[str] = Field(default_factory=list)
    commandBlacklist: list[str] = Field(default_factory=list)
    allow_exec: bool = False


class WriteIn(BaseModel):
    id: str
    path: str
    content: str = ""
    dryRun: bool = False


class MapIn(BaseModel):
    id: str
    path: str
    direction: str = "local_to_remote"


class MkdirIn(BaseModel):
    id: str
    path: str


class RenameIn(BaseModel):
    id: str
    src: str | None = None
    dst: str | None = None
    # Aliases accepted for spec/compat
    from_path: str | None = Field(default=None, alias="from")
    to_path: str | None = Field(default=None, alias="to")

    model_config = {"populate_by_name": True}

    def resolved(self) -> tuple[str, str]:
        src = self.src or self.from_path or ""
        dst = self.dst or self.to_path or ""
        return src, dst


class DeleteIn(BaseModel):
    id: str
    path: str
    recursive: bool = False


class UploadIn(BaseModel):
    id: str
    path: str | None = None
    remotePath: str | None = None
    contentBase64: str
    filename: str | None = None

    def resolved_path(self) -> str:
        return self.path or self.remotePath or ""


class MappingsIn(BaseModel):
    id: str
    mappings: list[dict[str, Any]] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)


class ExecIn(BaseModel):
    id: str
    command: str
    timeout: int = 30


@router.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "plugin": "ssh-plugin"}


@router.get("/health/server")
async def health_server(id: str) -> dict[str, Any]:
    server = _server_or_404(id)
    return await _remote("health", {"server": server})


@router.get("/conn/stats")
async def conn_stats() -> dict[str, Any]:
    return sftp_client.pool_stats()


@router.get("/audit")
async def get_audit(limit: int = 50) -> dict[str, Any]:
    return {"entries": audit_tail(min(max(limit, 1), 500))}


class SyncIn(BaseModel):
    id: str
    localRoot: str | None = None
    dryRun: bool = True
    maxFiles: int = 500
    expectedFiles: list[dict[str, Any]] | None = None


class DownloadTreeIn(BaseModel):
    id: str
    remoteRoot: str
    localRoot: str
    dryRun: bool = True
    maxFiles: int = 500
    maxEntries: int = 10000


@router.post("/fs/download-tree")
async def fs_download_tree(body: DownloadTreeIn) -> dict[str, Any]:
    server = _server_or_404(body.id)
    try:
        result = await _remote(
            "download_tree",
            {"server": server, "remoteRoot": body.remoteRoot, "localRoot": body.localRoot,
             "dryRun": body.dryRun, "maxFiles": body.maxFiles, "maxEntries": body.maxEntries},
        )
        _audit("download_tree", server, result["remoteRoot"], dryRun=body.dryRun, count=result["count"])
        return result
    except Exception as exc:
        raise _err(exc, 502) from exc


@router.post("/fs/sync")
async def fs_sync(body: SyncIn) -> dict[str, Any]:
    server = _server_or_404(body.id)
    try:
        from sync_plan import plan_sync
    except ImportError:
        from ..sync_plan import plan_sync  # type: ignore
    local_root = body.localRoot or ((server.get("mappings") or [{}])[0].get("localRoot") or "")
    if not local_root:
        raise HTTPException(status_code=400, detail="localRoot required (or configure mappings)")
    try:
        result = await _remote(
            "sync_plan",
            {"server": server, "localRoot": local_root, "dryRun": body.dryRun,
             "maxFiles": body.maxFiles, "expectedFiles": body.expectedFiles},
        )
        if result.get("ok"):
            _audit(
                "sync",
                server,
                None,
                dryRun=body.dryRun,
                count=result.get("count"),
                uploaded=result.get("uploaded"),
            )
        return result
    except Exception as exc:
        _audit("sync", server, None, ok=False, error=str(exc)[:200])
        raise _err(exc, 502) from exc


@router.get("/servers")
async def servers(mask: bool = False) -> dict[str, Any]:
    data = deployment_store.load()
    full_servers = data["servers"]
    if mask:
        listed = agent_list_servers(full_servers)
    else:
        listed = [deployment_store.public_server(s) for s in full_servers]
    for item in listed:
        raw = next((s for s in full_servers if s["id"] == item.get("id")), None) or item
        item["securityWarnings"] = security_warnings(raw)
        item["hostMasked"] = bool(mask)
    return {"servers": listed, "defaultServerId": data.get("defaultServerId")}


@router.post("/servers")
async def upsert_server(body: ServerIn) -> dict[str, Any]:
    try:
        return {"server": deployment_store.upsert_server(body.model_dump())}
    except ValueError as exc:
        raise _err(exc, 400) from exc


@router.delete("/servers/{server_id}")
async def delete_server(server_id: str) -> dict[str, Any]:
    ok = deployment_store.delete_server(server_id)
    if not ok:
        raise HTTPException(status_code=404, detail="server not found")
    return {"ok": True}


@router.post("/servers/default")
async def set_default(body: dict[str, Any]) -> dict[str, Any]:
    ok = deployment_store.set_default(str(body.get("id") or ""))
    return {"ok": ok}


@router.post("/servers/{server_id}/test")
async def test_server(server_id: str) -> dict[str, Any]:
    server = _server_or_404(server_id)
    return await _remote("test", {"server": server})


@router.get("/fs/ls")
async def fs_ls(id: str, path: str = "/") -> dict[str, Any]:
    server = _server_or_404(id)
    p = _safe_path(server, path)
    try:
        result = await _remote("list_dir", {"server": server, "path": p})
    except sftp_client.SftpError as exc:
        raise _err(exc, 502) from exc
    except Exception as exc:
        raise _err(exc, 502) from exc
    result["entries"] = sftp_client.filter_excluded(result.get("entries") or [], server.get("exclusions") or [])
    return result


@router.get("/fs/read")
async def fs_read(
    id: str,
    path: str,
    offset: int | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    server = _server_or_404(id)
    p = _safe_path(server, path)
    try:
        if offset is not None or limit is not None:
            return await _remote(
                "read_text",
                {"server": server, "path": p, "offset": offset or 0, "limit": limit or sftp_client.CHUNK_DEFAULT},
            )
        return await _remote("read_text", {"server": server, "path": p})
    except Exception as exc:
        raise _err(exc, 502) from exc


@router.get("/fs/preview")
async def fs_preview(id: str, path: str) -> dict[str, Any]:
    server = _server_or_404(id)
    p = _safe_path(server, path)
    try:
        return await _remote("preview", {"server": server, "path": p})
    except Exception as exc:
        raise _err(exc, 502) from exc


@router.get("/fs/download")
async def fs_download(id: str, path: str) -> dict[str, Any]:
    server = _server_or_404(id)
    p = _safe_path(server, path)
    try:
        data = await _remote("download", {"server": server, "path": p})
    except Exception as exc:
        raise _err(exc, 502) from exc
    name = p.rstrip("/").rsplit("/", 1)[-1]
    if isinstance(data, dict) and "contentBase64" in data:
        return {
            "path": p,
            "filename": name,
            "bytes": data.get("bytes"),
            "contentBase64": data["contentBase64"],
        }
    return {
        "path": p,
        "filename": name,
        "bytes": len(data),
        "contentBase64": base64.b64encode(data).decode("ascii"),
    }


@router.post("/fs/write")
async def fs_write(body: WriteIn) -> dict[str, Any]:
    server = _server_or_404(body.id)
    p = _safe_path(server, body.path)
    try:
        old = ""
        try:
            old = (await _remote("read_text", {"server": server, "path": p}))["content"]
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise
        meta = unified_diff(old, body.content, p)
        if body.dryRun:
            return {"ok": True, "dryRun": True, "written": False, **meta}
        result = await _remote("write_text", {"server": server, "path": p, "content": body.content})
        _audit("write", server, p, addedLines=meta["addedLines"], removedLines=meta["removedLines"])
        return {
            "ok": True,
            "dryRun": False,
            "written": True,
            **result,
            "addedLines": meta["addedLines"],
            "removedLines": meta["removedLines"],
            "identical": meta["identical"],
        }
    except Exception as exc:
        _audit("write", server, body.path, ok=False, error=str(exc)[:200])
        raise _err(exc, 502) from exc


@router.post("/fs/map")
async def fs_map(body: MapIn) -> dict[str, Any]:
    server = _server_or_404(body.id)
    direction = (body.direction or "local_to_remote").lower()
    if direction in ("local_to_remote", "l2r", "to_remote"):
        return map_local_to_remote(server, body.path)
    if direction in ("remote_to_local", "r2l", "to_local"):
        return map_remote_to_local(server, body.path)
    raise HTTPException(status_code=400, detail="direction must be local_to_remote or remote_to_local")


@router.post("/fs/mkdir")
async def fs_mkdir(body: MkdirIn) -> dict[str, Any]:
    server = _server_or_404(body.id)
    p = _safe_path(server, body.path)
    try:
        result = await _remote("mkdir", {"server": server, "path": p})
        _audit("mkdir", server, p)
        return result
    except Exception as exc:
        _audit("mkdir", server, p, ok=False, error=str(exc)[:200])
        raise _err(exc, 502) from exc


@router.post("/fs/rename")
async def fs_rename(body: RenameIn) -> dict[str, Any]:
    server = _server_or_404(body.id)
    raw_src, raw_dst = body.resolved()
    if not raw_src or not raw_dst:
        raise HTTPException(status_code=400, detail="rename requires src/dst or from/to")
    src = _safe_path(server, raw_src)
    dst = _safe_path(server, raw_dst)
    try:
        result = await _remote("rename", {"server": server, "src": src, "dst": dst})
        _audit("rename", server, src, dst=dst)
        return result
    except Exception as exc:
        _audit("rename", server, src, ok=False, error=str(exc)[:200])
        raise _err(exc, 502) from exc


@router.post("/fs/delete")
async def fs_delete(body: DeleteIn) -> dict[str, Any]:
    server = _server_or_404(body.id)
    p = _safe_path(server, body.path)
    if p == "/":
        raise HTTPException(status_code=400, detail="refusing to delete root")
    try:
        result = await _remote("delete", {"server": server, "path": p, "recursive": body.recursive})
        _audit("delete", server, p, recursive=body.recursive)
        return result
    except Exception as exc:
        _audit("delete", server, p, ok=False, error=str(exc)[:200])
        raise _err(exc, 502) from exc


@router.post("/fs/upload")
async def fs_upload(body: UploadIn) -> dict[str, Any]:
    server = _server_or_404(body.id)
    remote = body.resolved_path()
    if not remote:
        raise HTTPException(status_code=400, detail="upload requires path or remotePath")
    p = _safe_path(server, remote)
    try:
        raw = base64.b64decode(body.contentBase64 or "")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid base64: {exc}") from exc
    try:
        try:
            from ssh_bridge import bridge_enabled
        except ImportError:
            from ..ssh_bridge import bridge_enabled  # type: ignore
        if bridge_enabled():
            import base64 as _b64
            result = await _remote(
                "upload",
                {"server": server, "path": p, "contentBase64": _b64.b64encode(raw).decode("ascii")},
            )
        else:
            result = await _remote("upload", {"server": server, "path": p, "data": raw})
        _audit("upload", server, p, bytes=result.get("bytes"))
        return result
    except Exception as exc:
        _audit("upload", server, p, ok=False, error=str(exc)[:200])
        raise _err(exc, 502) from exc


@router.get("/mappings")
async def get_mappings(id: str) -> dict[str, Any]:
    server = _server_or_404(id)
    return {
        "id": server["id"],
        "mappings": server.get("mappings") or [],
        "exclusions": server.get("exclusions") or [],
    }


@router.put("/mappings")
async def put_mappings(body: MappingsIn) -> dict[str, Any]:
    try:
        return {"server": deployment_store.set_mappings(body.id, body.mappings, body.exclusions)}
    except ValueError as exc:
        raise _err(exc, 404 if "not found" in str(exc) else 400) from exc


@router.post("/exec")
async def exec_cmd(body: ExecIn) -> dict[str, Any]:
    server = _server_or_404(body.id)
    try:
        result = await _remote(
            "exec", {"server": server, "command": body.command, "timeout": body.timeout}
        )
        _audit("exec", server, None, command=body.command[:200], exitCode=result.get("exitCode"))
        return result
    except sftp_client.SftpError as exc:
        _audit("exec", server, None, ok=False, command=body.command[:200], error=str(exc)[:200])
        raise _err(exc, 403 if "disabled" in str(exc) else 502) from exc
    except Exception as exc:
        _audit("exec", server, None, ok=False, command=body.command[:200], error=str(exc)[:200])
        raise _err(exc, 502) from exc
