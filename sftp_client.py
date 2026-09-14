"""Thin paramiko SFTP client wrapper used by REST + agent tools."""

from __future__ import annotations

import base64
import fnmatch
import io
import stat
from datetime import datetime, timezone
from typing import Any

try:
    import paramiko
except ImportError:  # pragma: no cover - surfaced as API error
    paramiko = None  # type: ignore

MAX_READ_BYTES = 1_000_000
MAX_PREVIEW_BYTES = 8_000_000
MAX_UPLOAD_BYTES = 50_000_000

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".ico"}
TEXT_EXT = {
    ".txt", ".md", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".css", ".html", ".htm", ".xml", ".sh",
    ".env", ".log", ".csv", ".go", ".rs", ".java", ".c", ".h", ".cpp", ".sql",
}


class SftpError(Exception):
    pass


def require_paramiko() -> Any:
    if paramiko is None:
        raise SftpError("paramiko is not installed in the Hermes gateway environment")
    return paramiko


def _connect(server: dict[str, Any]):
    pk = require_paramiko()
    host = server.get("host")
    if not host:
        raise SftpError("server host is empty")
    port = int(server.get("port") or 22)
    username = server.get("username") or ""
    password = server.get("password") or None
    timeout = float(server.get("timeout") or 20)

    client = pk.SSHClient()
    # Prefer strict verification against ~/.ssh/known_hosts; fall back to
    # auto-accept only when no known_hosts file exists (first-run UX).
    from pathlib import Path as _P

    known = _P.home() / ".ssh" / "known_hosts"
    if known.is_file():
        try:
            client.load_host_keys(str(known))
            client.set_missing_host_key_policy(pk.RejectPolicy())
        except Exception:
            client.set_missing_host_key_policy(pk.AutoAddPolicy())
    else:
        client.set_missing_host_key_policy(pk.AutoAddPolicy())
    connect_kwargs: dict[str, Any] = {
        "hostname": host,
        "port": port,
        "username": username,
        "timeout": timeout,
        "banner_timeout": timeout,
        "auth_timeout": timeout,
        "allow_agent": False,
        "look_for_keys": False,
    }
    auth = (server.get("auth") or "password").lower()
    if auth == "key":
        key_path = server.get("privateKey")
        if not key_path:
            raise SftpError("privateKey path is required for key auth")
        key = None
        passphrase = server.get("passphrase") or None
        data = None
        # Allow inline key content for tests; otherwise treat as filesystem path
        content = server.get("privateKeyContent")
        if content:
            data = io.StringIO(content)
        else:
            data = open(str(key_path).expanduser(), "r", encoding="utf-8")
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
            raise SftpError("unable to load private key")
        connect_kwargs["pkey"] = key
    elif auth == "agent":
        connect_kwargs["allow_agent"] = True
        connect_kwargs["look_for_keys"] = True
    else:
        connect_kwargs["password"] = password

    client.connect(**connect_kwargs)
    return client


class RemoteSession:
    """Pool-backed SSH session. Reuses keep-alive connections per server id."""

    def __init__(self, server: dict[str, Any]):
        self.server = server
        self.client = None
        self.sftp = None
        self._ctx = None

    def __enter__(self) -> "RemoteSession":
        try:
            from .ssh_session import get_session
        except ImportError:
            from ssh_session import get_session  # type: ignore
        self._ctx = get_session(self.server)
        self.sftp, self.client = self._ctx.__enter__()
        return self

    def __exit__(self, *args) -> bool:
        if self._ctx is not None:
            return bool(self._ctx.__exit__(*args))
        return False


def test_connection(server: dict[str, Any]) -> dict[str, Any]:
    try:
        with RemoteSession(session_server(server)) as sess:
            stdin, stdout, stderr = sess.client.exec_command("hostname; uname -a", timeout=15)
            out = stdout.read().decode("utf-8", errors="replace").strip()
            lines = out.splitlines()
            return {
                "ok": True,
                "host": server.get("host"),
                "hostname": lines[0] if lines else None,
                "info": out[:500],
            }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def session_server(server: dict[str, Any]) -> dict[str, Any]:
    # Strip masked placeholders before connecting
    s = dict(server)
    for k in ("password", "passphrase"):
        if s.get(k) == "***":
            s[k] = None
    if s.get("privateKey") == "***":
        s["privateKey"] = None
    return s


def _meta(st_mode: int, size: int, mtime: float, name: str) -> dict[str, Any]:
    is_dir = stat.S_ISDIR(st_mode)
    return {
        "name": name,
        "path": name,
        "type": "dir" if is_dir else "file",
        "size": int(size),
        "mtime": datetime.fromtimestamp(mtime or 0, tz=timezone.utc).isoformat() if mtime else None,
        "isImage": (not is_dir) and PathLike(name).suffix.lower() in IMAGE_EXT,
        "isText": (not is_dir) and (
            PathLike(name).suffix.lower() in TEXT_EXT
            or PathLike(name).name.startswith(".")
        ),
    }


def PathLike(name: str):
    from pathlib import PurePosixPath

    return PurePosixPath(name)


def _guard_remote_path(sftp, server: dict[str, Any], path: str) -> None:
    """Check the SFTP server's resolved path, including symlinked ancestors."""
    allowed = server.get("allowedRemotePaths") or []
    if not allowed:
        return
    try:
        from .deployment_store import safe_remote_path
    except ImportError:
        from deployment_store import safe_remote_path  # type: ignore

    safe_remote_path(path, allowed)
    ancestor = path
    missing: list[str] = []
    while True:
        try:
            sftp.stat(ancestor)
            break
        except OSError as exc:
            import errno

            if exc.errno != errno.ENOENT:
                raise
            if ancestor == "/":
                raise
            ancestor, leaf = ancestor.rsplit("/", 1)
            ancestor = ancestor or "/"
            missing.insert(0, leaf)
    real = sftp.normalize(ancestor).rstrip("/") or "/"
    resolved = real.rstrip("/") + ("/" + "/".join(missing) if missing else "")
    safe_remote_path(resolved, allowed)


def list_dir(server: dict[str, Any], path: str) -> dict[str, Any]:
    with RemoteSession(session_server(server)) as sess:
        _guard_remote_path(sess.sftp, server, path)
        items = []
        for attr in sess.sftp.listdir_attr(path):
            name = attr.filename
            if name in (".", ".."):
                continue
            st = attr.st_mode or 0
            item = _meta(st, attr.st_size or 0, attr.st_mtime or 0, name)
            item["path"] = (path.rstrip("/") + "/" + name) if path not in ("", "/") else "/" + name
            items.append(item)
        items.sort(key=lambda x: (0 if x["type"] == "dir" else 1, x["name"].lower()))
        return {"path": path or "/", "entries": items}


def read_text(server: dict[str, Any], path: str, max_bytes: int = MAX_READ_BYTES) -> dict[str, Any]:
    with RemoteSession(session_server(server)) as sess:
        _guard_remote_path(sess.sftp, server, path)
        with sess.sftp.open(path, "rb") as f:
            f.prefetch()
            data = f.read(max_bytes + 1)
        truncated = len(data) > max_bytes
        if truncated:
            data = data[:max_bytes]
        text = data.decode("utf-8", errors="replace")
        return {"path": path, "content": text, "truncated": truncated, "bytes": len(data)}


CHUNK_DEFAULT = 256 * 1024
CHUNK_MAX = 1_000_000


def read_text_chunk(
    server: dict[str, Any],
    path: str,
    offset: int = 0,
    limit: int = CHUNK_DEFAULT,
) -> dict[str, Any]:
    """Read a UTF-8 byte window [offset, offset+limit) from a remote file."""
    offset = max(0, int(offset or 0))
    limit = min(max(1, int(limit or CHUNK_DEFAULT)), CHUNK_MAX)
    with RemoteSession(session_server(server)) as sess:
        _guard_remote_path(sess.sftp, server, path)
        with sess.sftp.open(path, "rb") as f:
            try:
                size = f.stat().st_size
            except Exception:
                size = None
            if offset:
                f.seek(offset)
            raw = f.read(limit)
    text = raw.decode("utf-8", errors="replace")
    end = offset + len(raw)
    return {
        "path": path,
        "content": text,
        "offset": offset,
        "bytes": len(raw),
        "nextOffset": end if raw else None,
        "eof": size is not None and end >= size,
        "fileSize": size,
        "limit": limit,
    }


def write_text(server: dict[str, Any], path: str, content: str) -> dict[str, Any]:
    raw = content.encode("utf-8")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise SftpError("content too large")
    with RemoteSession(session_server(server)) as sess:
        _guard_remote_path(sess.sftp, server, path)
        _ensure_parent(sess.sftp, path)
        with sess.sftp.open(path, "wb") as f:
            f.write(raw)
    return {"path": path, "bytes": len(raw)}


def upload_bytes(server: dict[str, Any], path: str, data: bytes) -> dict[str, Any]:
    if len(data) > MAX_UPLOAD_BYTES:
        raise SftpError("upload too large")
    with RemoteSession(session_server(server)) as sess:
        _guard_remote_path(sess.sftp, server, path)
        _ensure_parent(sess.sftp, path)
        with sess.sftp.open(path, "wb") as f:
            f.write(data)
    return {"path": path, "bytes": len(data)}


def download_bytes(server: dict[str, Any], path: str) -> bytes:
    with RemoteSession(session_server(server)) as sess:
        _guard_remote_path(sess.sftp, server, path)
        with sess.sftp.open(path, "rb") as f:
            return f.read(MAX_UPLOAD_BYTES + 1)


def glob_files(server: dict[str, Any], root: str, pattern: str, max_results: int = 500) -> dict[str, Any]:
    """Find remote files under root with a bounded SFTP walk."""
    from pathlib import PurePosixPath
    try:
        from .deployment_store import _glob_match, safe_remote_path
    except ImportError:
        from deployment_store import _glob_match, safe_remote_path  # type: ignore
    root = safe_remote_path(root, server.get("allowedRemotePaths") or None)
    if not pattern or pattern.startswith("/") or ".." in PurePosixPath(pattern).parts:
        raise ValueError("pattern must be relative to root")
    max_results = min(max(1, int(max_results)), 5000)
    matches = []
    visited = 0
    with RemoteSession(session_server(server)) as sess:
        pending = [(root, "")]
        while pending:
            folder, rel_dir = pending.pop()
            _guard_remote_path(sess.sftp, server, folder)
            for attr in sess.sftp.listdir_attr(folder):
                name = attr.filename
                if name in (".", "..") or "/" in name or "\\" in name:
                    continue
                visited += 1
                if visited > 10000:
                    raise SftpError("remote search exceeds entry limit")
                rel = f"{rel_dir}/{name}".lstrip("/")
                path = folder.rstrip("/") + "/" + name
                mode = attr.st_mode or 0
                if stat.S_ISLNK(mode):
                    continue
                _guard_remote_path(sess.sftp, server, path)
                if stat.S_ISDIR(mode):
                    pending.append((path, rel))
                elif _glob_match(rel, pattern):
                    matches.append({"path": path, "relativePath": rel, "bytes": int(attr.st_size or 0)})
                    if len(matches) >= max_results:
                        return {"root": root, "pattern": pattern, "matches": matches, "truncated": True}
    return {"root": root, "pattern": pattern, "matches": matches, "truncated": False}


def tail_text(server: dict[str, Any], path: str, limit: int = 65536) -> dict[str, Any]:
    """Read the final byte window of a remote UTF-8 log."""
    limit = min(max(1, int(limit)), CHUNK_MAX)
    with RemoteSession(session_server(server)) as sess:
        _guard_remote_path(sess.sftp, server, path)
        size = int(sess.sftp.stat(path).st_size)
        offset = max(0, size - limit)
        with sess.sftp.open(path, "rb") as source:
            source.seek(offset)
            data = source.read(limit)
    return {"path": path, "content": data.decode("utf-8", errors="replace"),
            "offset": offset, "bytes": len(data), "fileSize": size}


def preview_image(server: dict[str, Any], path: str) -> dict[str, Any]:
    data = download_bytes(server, path)
    if len(data) > MAX_PREVIEW_BYTES:
        raise SftpError("image too large to preview")
    ext = PathLike(path).suffix.lower().lstrip(".") or "png"
    if ext == "jpg":
        ext = "jpeg"
    mime = "image/svg+xml" if ext == "svg" else f"image/{ext}"
    return {
        "path": path,
        "mime": mime,
        "bytes": len(data),
        "dataUrl": f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}",
    }


def mkdir(server: dict[str, Any], path: str) -> dict[str, Any]:
    with RemoteSession(session_server(server)) as sess:
        _guard_remote_path(sess.sftp, server, path)
        sess.sftp.mkdir(path)
    return {"path": path, "ok": True}


def rename(server: dict[str, Any], src: str, dst: str) -> dict[str, Any]:
    with RemoteSession(session_server(server)) as sess:
        _guard_remote_path(sess.sftp, server, src)
        _guard_remote_path(sess.sftp, server, dst)
        sess.sftp.posix_rename(src, dst)
    return {"from": src, "to": dst, "ok": True}


def delete(server: dict[str, Any], path: str, recursive: bool = False) -> dict[str, Any]:
    with RemoteSession(session_server(server)) as sess:
        _guard_remote_path(sess.sftp, server, path)
        try:
            st = sess.sftp.stat(path)
        except FileNotFoundError as exc:
            raise SftpError(f"not found: {path}") from exc
        import stat as stmod

        if stmod.S_ISDIR(st.st_mode):
            if not recursive:
                raise SftpError("path is a directory; pass recursive=true to delete")
            _rmtree(sess.sftp, path)
        else:
            sess.sftp.remove(path)
    return {"path": path, "ok": True}


def exec_command(server: dict[str, Any], command: str, timeout: int = 30) -> dict[str, Any]:
    try:
        from .security import validate_command
    except ImportError:
        from security import validate_command  # type: ignore

    cmd = validate_command(server, command)
    with RemoteSession(session_server(server)) as sess:
        stdin, stdout, stderr = sess.client.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        return {"command": cmd, "exitCode": code, "stdout": out[-100000:], "stderr": err[-100000:]}


def health_check(server: dict[str, Any]) -> dict[str, Any]:
    try:
        from .ssh_session import health as _health
    except ImportError:
        from ssh_session import health as _health  # type: ignore
    return _health(session_server(server))


def pool_stats() -> dict[str, Any]:
    try:
        from .ssh_session import stats as _stats
    except ImportError:
        from ssh_session import stats as _stats  # type: ignore
    return _stats()


def _ensure_parent(sftp, path: str) -> None:
    parent = path.rsplit("/", 1)[0]
    if not parent or parent == "/":
        return
    parts = [p for p in parent.split("/") if p]
    cur = ""
    for part in parts:
        cur = f"{cur}/{part}"
        try:
            sftp.stat(cur)
        except IOError:
            try:
                sftp.mkdir(cur)
            except IOError:
                # concurrent create or permission — re-check
                sftp.stat(cur)


def _rmtree(sftp, path: str) -> None:
    for attr in sftp.listdir_attr(path):
        child = path.rstrip("/") + "/" + attr.filename
        import stat as stmod

        if stmod.S_ISDIR(attr.st_mode or 0):
            _rmtree(sftp, child)
        else:
            sftp.remove(child)
    sftp.rmdir(path)


def filter_excluded(entries: list[dict], exclusions: list[str]) -> list[dict]:
    if not exclusions:
        return entries
    try:
        from .deployment_store import match_exclusion
    except ImportError:
        from deployment_store import match_exclusion  # type: ignore

    out = []
    for e in entries:
        if match_exclusion(e.get("name") or "", exclusions):
            continue
        out.append(e)
    return out
