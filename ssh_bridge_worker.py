"""SSH bridge worker — stdin/stdout JSON line server for isolated paramiko ops."""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import sftp_client  # noqa: E402


def _op_list_dir(p: dict[str, Any]) -> Any:
    return sftp_client.list_dir(p["server"], p["path"])


def _op_read_text(p: dict[str, Any]) -> Any:
    if p.get("offset") is not None or p.get("limit") is not None:
        return sftp_client.read_text_chunk(
            p["server"],
            p["path"],
            offset=int(p.get("offset") or 0),
            limit=int(p.get("limit") or sftp_client.CHUNK_DEFAULT),
        )
    return sftp_client.read_text(p["server"], p["path"])


def _op_write_text(p: dict[str, Any]) -> Any:
    return sftp_client.write_text(p["server"], p["path"], p.get("content") or "")


def _op_mkdir(p: dict[str, Any]) -> Any:
    return sftp_client.mkdir(p["server"], p["path"])


def _op_delete(p: dict[str, Any]) -> Any:
    return sftp_client.delete(p["server"], p["path"], recursive=bool(p.get("recursive")))


def _op_rename(p: dict[str, Any]) -> Any:
    return sftp_client.rename(p["server"], p["src"], p["dst"])


def _op_upload(p: dict[str, Any]) -> Any:
    import base64

    raw = base64.b64decode(p.get("contentBase64") or "")
    return sftp_client.upload_bytes(p["server"], p["path"], raw)


def _op_download(p: dict[str, Any]) -> Any:
    import base64

    data = sftp_client.download_bytes(p["server"], p["path"])
    return {"path": p["path"], "bytes": len(data), "contentBase64": base64.b64encode(data).decode("ascii")}


def _op_preview(p: dict[str, Any]) -> Any:
    return sftp_client.preview_image(p["server"], p["path"])


def _op_test(p: dict[str, Any]) -> Any:
    return sftp_client.test_connection(p["server"])


def _op_health(p: dict[str, Any]) -> Any:
    return sftp_client.health_check(p["server"])


def _op_glob(p: dict[str, Any]) -> Any:
    return sftp_client.glob_files(
        p["server"], p["root"], p["pattern"], max_results=int(p.get("maxResults") or 500)
    )


def _op_tail(p: dict[str, Any]) -> Any:
    return sftp_client.tail_text(p["server"], p["path"], limit=int(p.get("limit") or 65536))


def _op_download_tree(p: dict[str, Any]) -> Any:
    from download_plan import download_tree

    return download_tree(
        p["server"],
        p["remoteRoot"],
        p["localRoot"],
        dry_run=bool(p.get("dryRun", True)),
        max_files=int(p.get("maxFiles") or 500),
        max_entries=int(p.get("maxEntries") or 10000),
    )


def _op_sync_plan(p: dict[str, Any]) -> Any:
    from sync_plan import plan_sync

    return plan_sync(
        p["server"],
        p["localRoot"],
        dry_run=bool(p.get("dryRun", True)),
        max_files=int(p.get("maxFiles") or 500),
        expected_files=p.get("expectedFiles") or None,
    )


def _op_exec(p: dict[str, Any]) -> Any:
    return sftp_client.exec_command(p["server"], p["command"], timeout=int(p.get("timeout") or 30))


OPS: dict[str, Callable[[dict[str, Any]], Any]] = {
    "list_dir": _op_list_dir,
    "read_text": _op_read_text,
    "write_text": _op_write_text,
    "mkdir": _op_mkdir,
    "delete": _op_delete,
    "rename": _op_rename,
    "upload": _op_upload,
    "download": _op_download,
    "preview": _op_preview,
    "test": _op_test,
    "health": _op_health,
    "glob": _op_glob,
    "tail": _op_tail,
    "download_tree": _op_download_tree,
    "sync_plan": _op_sync_plan,
    "exec": _op_exec,
}


def handle_line(line: str) -> dict[str, Any]:
    try:
        req = json.loads(line)
    except json.JSONDecodeError:
        return {"id": None, "ok": False, "error": "invalid JSON request"}
    req_id = req.get("id")
    op = req.get("op")
    payload = req.get("payload") or {}
    if not isinstance(payload, dict):
        return {"id": req_id, "ok": False, "error": "payload must be an object"}
    fn = OPS.get(str(op or ""))
    if fn is None:
        return {"id": req_id, "ok": False, "error": f"unknown op: {op}"}
    try:
        result = fn(payload)
        return {"id": req_id, "ok": True, "result": result}
    except Exception as exc:  # noqa: BLE001
        return {"id": req_id, "ok": False, "error": str(exc), "trace": traceback.format_exc(limit=3)}


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        sys.stdout.write(json.dumps(handle_line(line), ensure_ascii=False, default=str) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
