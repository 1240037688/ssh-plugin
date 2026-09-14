"""Batch sync: map local files under mapping.localRoot → remoteRoot (dry-run first)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from .deploy_paths import map_local_to_remote
    from .security import validate_local_path
    from .deployment_store import match_exclusion, safe_remote_path
except ImportError:
    from deploy_paths import map_local_to_remote  # type: ignore
    from security import validate_local_path  # type: ignore
    from deployment_store import match_exclusion, safe_remote_path  # type: ignore

# Skip common junk by default when no exclusions configured
_DEFAULT_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", ".hg", ".svn"}


def _is_excluded(rel: str, patterns: list[str]) -> bool:
    return match_exclusion(rel, patterns or [])


def plan_sync(
    server: dict[str, Any],
    local_root: str,
    *,
    dry_run: bool = True,
    max_files: int = 500,
    expected_files: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Walk local_root and plan uploads via mappings. Never writes unless dry_run=False."""
    root = validate_local_path(local_root, server)
    max_files = max(1, int(max_files))
    if not root.is_dir():
        return {"ok": False, "error": f"local root is not a directory: {root}"}
    exclusions = server.get("exclusions") or []
    mapping_server = {
        **server,
        "mappings": [
            {**m, "localRoot": str(Path(m["localRoot"]).expanduser().resolve())}
            for m in server.get("mappings") or []
            if m.get("localRoot")
        ],
    }
    planned: list[dict[str, Any]] = []
    skipped = 0
    errors: list[str] = []

    import os

    for dirpath, dirnames, filenames in os.walk(str(root)):
        current = Path(dirpath)
        dirnames[:] = [
            d
            for d in dirnames
            if d not in _DEFAULT_SKIP_DIRS
            and not _is_excluded((current / d).relative_to(root).as_posix(), exclusions)
        ]
        for name in filenames:
            local = current / name
            rel = local.relative_to(root).as_posix()
            if _is_excluded(rel, exclusions):
                skipped += 1
                continue
            validate_local_path(local, server)
            mapped = map_local_to_remote(mapping_server, str(local))
            if not mapped.get("ok"):
                skipped += 1
                continue
            planned.append(
                {
                    "localPath": str(local),
                    "remotePath": safe_remote_path(mapped["remotePath"], server.get("allowedRemotePaths") or None),
                    "size": local.stat().st_size,
                    "rel": rel,
                }
            )
            if len(planned) >= max_files:
                break
        if len(planned) >= max_files:
            break

    uploaded: list[dict[str, Any]] = []
    if not dry_run:
        if expected_files is not None:
            identity = lambda items: [
                (item.get("localPath"), item.get("remotePath"), item.get("size")) for item in items
            ]
            if identity(planned) != identity(expected_files):
                raise ValueError("sync plan changed since preview; preview again")
        try:
            from . import sftp_client
        except ImportError:
            import sftp_client  # type: ignore
        for item in planned:
            try:
                data = Path(item["localPath"]).read_bytes()
                sftp_client.upload_bytes(server, item["remotePath"], data)
                item["uploaded"] = True
                uploaded.append(item)
            except Exception as exc:  # noqa: BLE001
                item["uploaded"] = False
                item["error"] = str(exc)
                errors.append(f"{item['localPath']}: {exc}")

    return {
        "ok": True,
        "dryRun": bool(dry_run),
        "localRoot": str(root),
        "count": len(planned),
        "skipped": skipped,
        "uploaded": len(uploaded) if not dry_run else 0,
        "files": planned,
        "errors": errors,
    }
