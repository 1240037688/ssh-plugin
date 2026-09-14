"""Tool handlers — always return a JSON string, never raise."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

try:
    from . import deployment_store, sftp_client
except ImportError:
    import deployment_store  # type: ignore
    import sftp_client  # type: ignore


def _ok(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _err(message: str, **extra: Any) -> str:
    return json.dumps({"error": message, **extra}, ensure_ascii=False)


def _resolve_server(name: str) -> dict[str, Any]:
    server = deployment_store.get_server(name)
    if not server:
        raise ValueError(f"unknown server: {name}")
    return server


def ssh_list_servers(args: dict, **kwargs) -> str:
    del args, kwargs
    try:
        data = deployment_store.load()
        return _ok(
            {
                "servers": deployment_store.list_servers(),
                "defaultServerId": data.get("defaultServerId"),
            }
        )
    except Exception as exc:
        return _err(str(exc))


def ssh_ls(args: dict, **kwargs) -> str:
    del kwargs
    try:
        server = _resolve_server(str(args.get("server") or ""))
        path = deployment_store.safe_remote_path(
            str(args.get("path") or "/"), server.get("allowedRemotePaths") or None
        )
        result = sftp_client.list_dir(server, path)
        result["entries"] = sftp_client.filter_excluded(result["entries"], server.get("exclusions") or [])
        return _ok(result)
    except Exception as exc:
        return _err(str(exc))


def ssh_read_file(args: dict, **kwargs) -> str:
    del kwargs
    try:
        server = _resolve_server(str(args.get("server") or ""))
        path = deployment_store.safe_remote_path(
            str(args.get("path") or ""), server.get("allowedRemotePaths") or None
        )
        return _ok(sftp_client.read_text(server, path))
    except Exception as exc:
        return _err(str(exc))


def ssh_write_file(args: dict, **kwargs) -> str:
    del kwargs
    try:
        server = _resolve_server(str(args.get("server") or ""))
        path = deployment_store.safe_remote_path(
            str(args.get("path") or ""), server.get("allowedRemotePaths") or None
        )
        content = args.get("content")
        if content is None:
            return _err("content is required")
        return _ok(sftp_client.write_text(server, path, str(content)))
    except Exception as exc:
        return _err(str(exc))


def ssh_mkdir(args: dict, **kwargs) -> str:
    del kwargs
    try:
        server = _resolve_server(str(args.get("server") or ""))
        path = deployment_store.safe_remote_path(
            str(args.get("path") or ""), server.get("allowedRemotePaths") or None
        )
        return _ok(sftp_client.mkdir(server, path))
    except Exception as exc:
        return _err(str(exc))


def ssh_delete(args: dict, **kwargs) -> str:
    del kwargs
    try:
        server = _resolve_server(str(args.get("server") or ""))
        path = deployment_store.safe_remote_path(
            str(args.get("path") or ""), server.get("allowedRemotePaths") or None
        )
        if path == "/":
            return _err("refusing to delete root")
        return _ok(sftp_client.delete(server, path, recursive=bool(args.get("recursive"))))
    except Exception as exc:
        return _err(str(exc))


def ssh_upload(args: dict, **kwargs) -> str:
    del kwargs
    try:
        server = _resolve_server(str(args.get("server") or ""))
        local = Path(str(args.get("localPath") or "")).expanduser()
        if not local.is_file():
            return _err(f"local file not found: {local}")
        path = deployment_store.safe_remote_path(
            str(args.get("remotePath") or ""), server.get("allowedRemotePaths") or None
        )
        return _ok(sftp_client.upload_bytes(server, path, local.read_bytes()))
    except Exception as exc:
        return _err(str(exc))


def ssh_download(args: dict, **kwargs) -> str:
    del kwargs
    try:
        server = _resolve_server(str(args.get("server") or ""))
        path = deployment_store.safe_remote_path(
            str(args.get("remotePath") or ""), server.get("allowedRemotePaths") or None
        )
        local = Path(str(args.get("localPath") or "")).expanduser()
        local.parent.mkdir(parents=True, exist_ok=True)
        data = sftp_client.download_bytes(server, path)
        local.write_bytes(data)
        return _ok({"path": path, "localPath": str(local), "bytes": len(data)})
    except Exception as exc:
        return _err(str(exc))


def ssh_exec(args: dict, **kwargs) -> str:
    del kwargs
    try:
        server = _resolve_server(str(args.get("server") or ""))
        command = str(args.get("command") or "").strip()
        if not command:
            return _err("command is required")
        timeout = int(args.get("timeout") or 30)
        return _ok(sftp_client.exec_command(server, command, timeout=timeout))
    except Exception as exc:
        return _err(str(exc))
