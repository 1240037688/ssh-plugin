"""FastAPI router mounted at /api/plugins/ssh-plugin/ by Hermes dashboard bridge."""

from __future__ import annotations

import base64
from typing import Any

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import deployment_store  # noqa: E402
import sftp_client  # noqa: E402

router = APIRouter()


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
    allow_exec: bool = False


class WriteIn(BaseModel):
    id: str
    path: str
    content: str = ""


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


@router.get("/servers")
async def servers() -> dict[str, Any]:
    return {"servers": deployment_store.list_servers(), "defaultServerId": deployment_store.load().get("defaultServerId")}


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
    return sftp_client.test_connection(server)


@router.get("/fs/ls")
async def fs_ls(id: str, path: str = "/") -> dict[str, Any]:
    server = _server_or_404(id)
    p = _safe_path(server, path)
    try:
        result = sftp_client.list_dir(server, p)
    except sftp_client.SftpError as exc:
        raise _err(exc, 502) from exc
    except Exception as exc:
        raise _err(exc, 502) from exc
    result["entries"] = sftp_client.filter_excluded(result.get("entries") or [], server.get("exclusions") or [])
    return result


@router.get("/fs/read")
async def fs_read(id: str, path: str) -> dict[str, Any]:
    server = _server_or_404(id)
    p = _safe_path(server, path)
    try:
        return sftp_client.read_text(server, p)
    except Exception as exc:
        raise _err(exc, 502) from exc


@router.get("/fs/preview")
async def fs_preview(id: str, path: str) -> dict[str, Any]:
    server = _server_or_404(id)
    p = _safe_path(server, path)
    try:
        return sftp_client.preview_image(server, p)
    except Exception as exc:
        raise _err(exc, 502) from exc


@router.get("/fs/download")
async def fs_download(id: str, path: str) -> dict[str, Any]:
    server = _server_or_404(id)
    p = _safe_path(server, path)
    try:
        data = sftp_client.download_bytes(server, p)
    except Exception as exc:
        raise _err(exc, 502) from exc
    name = p.rstrip("/").rsplit("/", 1)[-1]
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
        return sftp_client.write_text(server, p, body.content)
    except Exception as exc:
        raise _err(exc, 502) from exc


@router.post("/fs/mkdir")
async def fs_mkdir(body: MkdirIn) -> dict[str, Any]:
    server = _server_or_404(body.id)
    p = _safe_path(server, body.path)
    try:
        return sftp_client.mkdir(server, p)
    except Exception as exc:
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
        return sftp_client.rename(server, src, dst)
    except Exception as exc:
        raise _err(exc, 502) from exc


@router.post("/fs/delete")
async def fs_delete(body: DeleteIn) -> dict[str, Any]:
    server = _server_or_404(body.id)
    p = _safe_path(server, body.path)
    if p == "/":
        raise HTTPException(status_code=400, detail="refusing to delete root")
    try:
        return sftp_client.delete(server, p, recursive=body.recursive)
    except Exception as exc:
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
        return sftp_client.upload_bytes(server, p, raw)
    except Exception as exc:
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
        return sftp_client.exec_command(server, body.command, timeout=body.timeout)
    except sftp_client.SftpError as exc:
        raise _err(exc, 403 if "disabled" in str(exc) else 502) from exc
    except Exception as exc:
        raise _err(exc, 502) from exc
