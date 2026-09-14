"""Bounded remote directory download into an allowed local workspace."""

from __future__ import annotations

import stat
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from . import sftp_client
    from .deployment_store import safe_remote_path
    from .security import validate_local_path
except ImportError:
    import sftp_client  # type: ignore
    from deployment_store import safe_remote_path  # type: ignore
    from security import validate_local_path  # type: ignore


def download_tree(
    server: dict[str, Any], remote_root: str, local_root: str, *,
    dry_run: bool = True, max_files: int = 500, max_bytes: int = 200_000_000,
    max_entries: int = 10000,
) -> dict[str, Any]:
    """Plan or download a directory; reject symlinks and oversized trees."""
    remote = safe_remote_path(remote_root, server.get("allowedRemotePaths") or None)
    local = validate_local_path(local_root, server)
    max_files = min(max(1, int(max_files)), 5000)
    max_bytes = min(max(1, int(max_bytes)), 1_000_000_000)
    max_entries = min(max(1, int(max_entries)), 20000)
    files: list[dict[str, Any]] = []
    total = 0
    visited = 0
    with sftp_client.RemoteSession(sftp_client.session_server(server)) as sess:
        pending = [(remote, PurePosixPath("."))]
        while pending:
            folder, rel_dir = pending.pop()
            sftp_client._guard_remote_path(sess.sftp, server, folder)
            for attr in sess.sftp.listdir_attr(folder):
                name = attr.filename
                if name in (".", "..") or "/" in name or "\\" in name or "\x00" in name:
                    continue
                visited += 1
                if visited > max_entries:
                    raise ValueError("remote directory exceeds download entry limit")
                rel = rel_dir / name
                path = folder.rstrip("/") + "/" + name
                mode = attr.st_mode or 0
                if stat.S_ISLNK(mode):
                    continue
                sftp_client._guard_remote_path(sess.sftp, server, path)
                if stat.S_ISDIR(mode):
                    pending.append((path, rel))
                    continue
                size = int(attr.st_size or 0)
                total += size
                if len(files) >= max_files or total > max_bytes or size > sftp_client.MAX_UPLOAD_BYTES:
                    raise ValueError("remote directory exceeds download limits")
                destination = validate_local_path(local.joinpath(*rel.parts), server)
                files.append({"remotePath": path, "localPath": str(destination), "bytes": size})
        if not dry_run:
            for item in files:
                remote_path = item["remotePath"]
                # Re-check at open time — listed regular files can be replaced by
                # symlinks between plan and download (TOCTOU).
                sftp_client._guard_remote_path(sess.sftp, server, remote_path)
                destination = validate_local_path(item["localPath"], server)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with sess.sftp.open(remote_path, "rb") as source:
                    data = source.read(sftp_client.MAX_UPLOAD_BYTES + 1)
                if len(data) > sftp_client.MAX_UPLOAD_BYTES:
                    raise ValueError("remote file exceeds download limit")
                destination.write_bytes(data)
    return {
        "ok": True, "dryRun": bool(dry_run), "remoteRoot": remote,
        "localRoot": str(local), "count": len(files), "bytes": total,
        "downloaded": 0 if dry_run else len(files), "files": files,
    }
