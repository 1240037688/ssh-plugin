"""Batch sync: map local files under mapping.localRoot → remoteRoot (dry-run first)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from .deploy_paths import map_local_to_remote
    from .security import validate_local_path
except ImportError:
    from deploy_paths import map_local_to_remote  # type: ignore
    from security import validate_local_path  # type: ignore

# Skip common junk by default when no exclusions configured
_DEFAULT_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", ".hg", ".svn"}


def _is_excluded(rel: str, patterns: list[str]) -> bool:
    try:
        from .deployment_store import match_exclusion
    except ImportError:
        from deployment_store import match_exclusion  # type: ignore
    return match_exclusion(rel, patterns or [])


def plan_sync(
    server: dict[str, Any],
    local_root: str,
    *,
    dry_run: bool = True,
    max_files: int = 500,
) -> dict[str, Any]:
    """Walk local_root and plan uploads via mappings. Never writes unless dry_run=False."""
    root = validate_local_path(local_root, server)
    if not root.is_dir():
        return {"ok": False, "error": f"local root is not a directory: {root}"}
    exclusions = server.get("exclusions") or []
    planned: list[dict[str, Any]] = []
    skipped = 0
    errors: list[str] = []

    import os

    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in _DEFAULT_SKIP_DIRS and not _is_excluded(d, exclusions)
        ]
        for name in filenames:
            if _is_excluded(name, exclusions):
                skipped += 1
                continue
            local = Path(dirpath) / name
            mapped = map_local_to_remote(server, str(local))
            if not mapped.get("ok"):
                skipped += 1
                continue
            try:
                rel = str(local.relative_to(root))
            except ValueError:
                rel = name
            planned.append(
                {
                    "localPath": str(local),
                    "remotePath": mapped["remotePath"],
                    "size": local.stat().st_size,
                    "rel": rel.replace("\\", "/"),
                }
            )
            if len(planned) >= max_files:
                break
        if len(planned) >= max_files:
            break

    uploaded: list[dict[str, Any]] = []
    if not dry_run:
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
