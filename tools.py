"""Tool handlers — always return a JSON string, never raise."""

from __future__ import annotations

import json
from typing import Any

try:
    from . import deployment_store, sftp_client
    from .deploy_paths import agent_list_servers, map_local_to_remote, map_remote_to_local, unified_diff
    from .security import validate_local_path
except ImportError:
    import deployment_store  # type: ignore
    import sftp_client  # type: ignore
    from deploy_paths import (  # type: ignore
        agent_list_servers,
        map_local_to_remote,
        map_remote_to_local,
        unified_diff,
    )
    from security import validate_local_path  # type: ignore


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
    del kwargs
    try:
        unmask = bool((args or {}).get("unmask"))
        data = deployment_store.load()
        full = data["servers"]
        servers = (
            [deployment_store.public_server(s) for s in full]
            if unmask
            else agent_list_servers(full)
        )
        return _ok(
            {
                "servers": servers,
                "defaultServerId": data.get("defaultServerId"),
                "hostMasked": not unmask,
            }
        )
    except Exception as exc:
        return _err(str(exc))


def ssh_health(args: dict, **kwargs) -> str:
    del kwargs
    try:
        server = _resolve_server(str(args.get("server") or ""))
        return _ok(sftp_client.health_check(server))
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
        new_content = str(content)
        dry_run = bool(args.get("dryRun") or args.get("dry_run"))
        old = ""
        try:
            old = sftp_client.read_text(server, path)["content"]
        except Exception:
            old = ""
        meta = unified_diff(old, new_content, path)
        if dry_run:
            return _ok({"ok": True, "dryRun": True, "written": False, **meta})
        result = sftp_client.write_text(server, path, new_content)
        return _ok({"ok": True, "dryRun": False, "written": True, **result, **{
            k: meta[k] for k in ("addedLines", "removedLines", "identical")
        }})
    except Exception as exc:
        return _err(str(exc))


def ssh_map_path(args: dict, **kwargs) -> str:
    del kwargs
    try:
        server = _resolve_server(str(args.get("server") or ""))
        direction = str(args.get("direction") or "local_to_remote").lower()
        if direction in ("local_to_remote", "l2r", "to_remote"):
            return _ok(map_local_to_remote(server, str(args.get("path") or "")))
        if direction in ("remote_to_local", "r2l", "to_local"):
            return _ok(map_remote_to_local(server, str(args.get("path") or "")))
        return _err("direction must be local_to_remote or remote_to_local")
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
        local = validate_local_path(str(args.get("localPath") or ""), server)
        if not local.is_file():
            return _err(f"local file not found: {local}")
        remote_raw = args.get("remotePath")
        if not remote_raw:
            mapped = map_local_to_remote(server, str(local))
            if not mapped.get("ok"):
                return _err(str(mapped.get("error") or "cannot map local path"), mapped=mapped)
            remote_raw = mapped["remotePath"]
        path = deployment_store.safe_remote_path(
            str(remote_raw), server.get("allowedRemotePaths") or None
        )
        dry_run = bool(args.get("dryRun") or args.get("dry_run"))
        if dry_run:
            return _ok({"ok": True, "dryRun": True, "localPath": str(local), "remotePath": path, "bytes": local.stat().st_size})
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
        local = validate_local_path(str(args.get("localPath") or ""), server)
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
        timeout = int(args.get("timeout") or 30)
        return _ok(sftp_client.exec_command(server, command, timeout=timeout))
    except Exception as exc:
        return _err(str(exc))
