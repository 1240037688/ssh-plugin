"""Security checks aligned with ssh-mcp-server semantics.

Ported ideas (not a line-for-line copy):
- commandWhitelist / commandBlacklist with full-string match
- reject shell control syntax when a whitelist is active
- allowedLocalPaths (+ process cwd) for local upload/download
- actionable warnings when remote path / command policy is open
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

# Shell metacharacters that must not appear when whitelist mode is on.
_SHELL_CONTROL = re.compile(r"[;&|`<>\r\n]|\$\(")


class SecurityError(Exception):
    def __init__(self, message: str, code: str = "SECURITY"):
        super().__init__(message)
        self.code = code


def _compile_patterns(patterns: list[str] | None, kind: str) -> list[re.Pattern[str]]:
    out: list[re.Pattern[str]] = []
    for pattern in patterns or []:
        s = str(pattern).strip()
        if not s:
            continue
        try:
            out.append(re.compile(s))
        except re.error as exc:
            raise SecurityError(f"invalid {kind} pattern {s!r}: {exc}", "INVALID_PATTERN") from exc
    return out


def validate_command(server: dict[str, Any], command: str) -> str:
    """Return command if allowed; raise SecurityError otherwise."""
    if not server.get("allow_exec"):
        raise SecurityError(
            "ssh_exec is disabled for this server (set allow_exec true)",
            "EXEC_DISABLED",
        )
    cmd = (command or "").strip()
    if not cmd:
        raise SecurityError("command is required", "EMPTY_COMMAND")

    whitelist = _compile_patterns(server.get("commandWhitelist"), "whitelist")
    blacklist = _compile_patterns(server.get("commandBlacklist"), "blacklist")

    if whitelist:
        # Conservative: a hit cannot authorize pipelines, redirects, $(...), etc.
        if _SHELL_CONTROL.search(cmd):
            raise SecurityError(
                "command contains shell control syntax forbidden by the whitelist",
                "SHELL_CONTROL_FORBIDDEN",
            )
        matched = False
        for regex in whitelist:
            m = regex.search(cmd)
            if m and m.start() == 0 and m.group(0) == cmd:
                matched = True
                break
        if not matched:
            raise SecurityError("command not in whitelist, execution forbidden", "NOT_WHITELISTED")

    for regex in blacklist:
        if regex.search(cmd):
            raise SecurityError("command matches blacklist, execution forbidden", "BLACKLISTED")

    return cmd


def allowed_local_roots(server: dict[str, Any] | None = None) -> list[Path]:
    roots = [Path.cwd()]
    for raw in (server or {}).get("allowedLocalPaths") or []:
        s = str(raw).strip()
        if not s:
            continue
        p = Path(s).expanduser()
        try:
            roots.append(p.resolve())
        except OSError:
            roots.append(p)
    # Dedup while preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for r in roots:
        key = str(r).lower()
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def validate_local_path(local_path: str | os.PathLike[str], server: dict[str, Any] | None = None) -> Path:
    """Ensure a local file path stays under cwd + allowedLocalPaths."""
    raw = str(local_path or "").strip()
    if not raw:
        raise SecurityError("local path is required", "EMPTY_LOCAL_PATH")
    p = Path(raw).expanduser()
    try:
        resolved = p.resolve()
    except OSError as exc:
        raise SecurityError(f"cannot resolve local path: {exc}", "LOCAL_PATH_INVALID") from exc

    roots = allowed_local_roots(server)
    for root in roots:
        try:
            root_r = root.resolve()
        except OSError:
            root_r = root
        if resolved == root_r or resolved.is_relative_to(root_r):
            return resolved

    raise SecurityError(
        "local path is not within process cwd or allowedLocalPaths",
        "LOCAL_PATH_NOT_ALLOWED",
    )


def security_warnings(server: dict[str, Any]) -> list[str]:
    """Human-readable gaps — similar to ssh-mcp-server startup WARNINGs."""
    warnings: list[str] = []
    if not server.get("allowedRemotePaths"):
        warnings.append(
            "allowedRemotePaths is empty: SFTP can access any remote path. "
            "Configure allowedRemotePaths to restrict the surface."
        )
    if server.get("allow_exec") and not server.get("commandWhitelist"):
        warnings.append(
            "allow_exec is enabled without commandWhitelist: any command may run. "
            "Add commandWhitelist (and preferably commandBlacklist)."
        )
    if not server.get("allowedLocalPaths"):
        warnings.append(
            "allowedLocalPaths is empty: local upload/download is limited only to process cwd."
        )
    return warnings
