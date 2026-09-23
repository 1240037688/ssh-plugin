"""Tool handlers — always return a JSON string, never raise."""

from __future__ import annotations

import json
import errno
from typing import Any

try:
    from . import deployment_store, sftp_client
    from .audit_log import record as audit_record
    from .deploy_paths import agent_list_servers, agent_unmask_server, map_local_to_remote, map_remote_to_local, unified_diff
    from .security import validate_local_path
except ImportError:
    import deployment_store  # type: ignore
    import sftp_client  # type: ignore
    from audit_log import record as audit_record  # type: ignore
    from deploy_paths import (  # type: ignore
        agent_list_servers,
        agent_unmask_server,
        map_local_to_remote,
        map_remote_to_local,
        unified_diff,
    )
    from security import validate_local_path  # type: ignore


def _audit(op: str, server: dict[str, Any] | None, path: str | None, ok: bool = True, **detail: Any) -> None:
    audit_record(
        op,
        server_id=(server or {}).get("id"),
        server_name=(server or {}).get("name"),
        path=path,
        ok=ok,
        source="agent",
        detail=detail,
    )


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
            [agent_unmask_server(s) for s in full]
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
        if args.get("offset") is not None or args.get("limit") is not None:
            return _ok(
                sftp_client.read_text_chunk(
                    server,
                    path,
                    offset=int(args.get("offset") or 0),
                    limit=int(args.get("limit") or sftp_client.CHUNK_DEFAULT),
                )
            )
        return _ok(sftp_client.read_text(server, path))
    except Exception as exc:
        return _err(str(exc))


def ssh_sync(args: dict, **kwargs) -> str:
    del kwargs
    try:
        from .sync_plan import plan_sync
    except ImportError:
        from sync_plan import plan_sync  # type: ignore
    try:
        server = _resolve_server(str(args.get("server") or ""))
        local_root = str(args.get("localRoot") or "")
        if not local_root:
            # first mapping localRoot
            maps = server.get("mappings") or []
            if not maps:
                return _err("no mappings configured for this server")
            local_root = maps[0].get("localRoot") or ""
        dry_run = True if args.get("dryRun") is None else bool(args.get("dryRun"))
        result = plan_sync(server, local_root, dry_run=dry_run, max_files=int(args.get("maxFiles") or 500))
        if result.get("ok"):
            _audit(
                "sync",
                server,
                None,
                dryRun=dry_run,
                count=result.get("count"),
                uploaded=result.get("uploaded"),
                localRoot=result.get("localRoot"),
            )
        return _ok(result)
    except Exception as exc:
        _audit("sync", None, None, ok=False, error=str(exc)[:200])
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
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise
        meta = unified_diff(old, new_content, path)
        if dry_run:
            return _ok({"ok": True, "dryRun": True, "written": False, **meta})
        result = sftp_client.write_text(server, path, new_content)
        _audit("write", server, path, addedLines=meta["addedLines"], removedLines=meta["removedLines"])
        return _ok({"ok": True, "dryRun": False, "written": True, **result, **{
            k: meta[k] for k in ("addedLines", "removedLines", "identical")
        }})
    except Exception as exc:
        _audit("write", locals().get("server"), str(args.get("path") or ""), ok=False, error=str(exc)[:200])
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
        result = sftp_client.mkdir(server, path)
        _audit("mkdir", server, path)
        return _ok(result)
    except Exception as exc:
        _audit("mkdir", None, str(args.get("path") or ""), ok=False, error=str(exc)[:200])
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
        result = sftp_client.delete(server, path, recursive=bool(args.get("recursive")))
        _audit("delete", server, path, recursive=bool(args.get("recursive")))
        return _ok(result)
    except Exception as exc:
        _audit("delete", None, str(args.get("path") or ""), ok=False, error=str(exc)[:200])
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
        result = sftp_client.upload_bytes(server, path, local.read_bytes())
        _audit("upload", server, path, localPath=str(local), bytes=result.get("bytes"))
        return _ok(result)
    except Exception as exc:
        _audit("upload", None, str(args.get("remotePath") or ""), ok=False, error=str(exc)[:200])
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
        _audit("download", server, path, localPath=str(local), bytes=len(data))
        return _ok({"path": path, "localPath": str(local), "bytes": len(data)})
    except Exception as exc:
        _audit("download", None, str(args.get("remotePath") or ""), ok=False, error=str(exc)[:200])
        return _err(str(exc))


def ssh_download_tree(args: dict, **kwargs) -> str:
    del kwargs
    try:
        from .download_plan import download_tree
    except ImportError:
        from download_plan import download_tree  # type: ignore
    try:
        server = _resolve_server(str(args.get("server") or ""))
        result = download_tree(
            server, str(args.get("remoteRoot") or ""), str(args.get("localRoot") or ""),
            dry_run=True if args.get("dryRun") is None else bool(args["dryRun"]),
            max_files=int(args.get("maxFiles") or 500),
            max_entries=int(args.get("maxEntries") or 10000),
        )
        _audit("download_tree", server, result["remoteRoot"], dryRun=result["dryRun"], count=result["count"])
        return _ok(result)
    except Exception as exc:
        _audit("download_tree", locals().get("server"), str(args.get("remoteRoot") or ""), ok=False, error=str(exc)[:200])
        return _err(str(exc))


def ssh_glob(args: dict, **kwargs) -> str:
    del kwargs
    try:
        server = _resolve_server(str(args.get("server") or ""))
        root = deployment_store.safe_remote_path(
            str(args.get("root") or "/"), server.get("allowedRemotePaths") or None
        )
        return _ok(sftp_client.glob_files(
            server, root, str(args.get("pattern") or ""), int(args.get("maxResults") or 500)
        ))
    except Exception as exc:
        return _err(str(exc))


def ssh_tail(args: dict, **kwargs) -> str:
    del kwargs
    try:
        server = _resolve_server(str(args.get("server") or ""))
        path = deployment_store.safe_remote_path(
            str(args.get("path") or ""), server.get("allowedRemotePaths") or None
        )
        return _ok(sftp_client.tail_text(server, path, int(args.get("limit") or 65536)))
    except Exception as exc:
        return _err(str(exc))


def ssh_exec(args: dict, **kwargs) -> str:
    del kwargs
    try:
        server = _resolve_server(str(args.get("server") or ""))
        command = str(args.get("command") or "").strip()
        timeout = int(args.get("timeout") or 30)
        result = sftp_client.exec_command(server, command, timeout=timeout)
        _audit("exec", server, None, command=command[:200], exitCode=result.get("exitCode"))
        return _ok(result)
    except Exception as exc:
        _audit("exec", None, None, ok=False, command=str(args.get("command") or "")[:200], error=str(exc)[:200])
        return _err(str(exc))
