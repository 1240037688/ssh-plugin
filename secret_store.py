"""Encrypt secret fields at rest with Windows DPAPI (CurrentUser).

Non-Windows fallback marks values as plaintext with a ``plain:`` prefix.
On Windows, an encryption failure stops the save rather than writing plaintext.
Load returns usable strings; save writes the on-disk encoding.
"""

from __future__ import annotations

import base64
import ctypes
import sys
from ctypes import wintypes
from typing import Any

ENCRYPTED_PREFIX = "enc:dpapi:v1:"
PLAIN_PREFIX = "plain:"
SECRET_FIELDS = ("password", "passphrase", "privateKeyContent")

_CRYPTPROTECT_UI_FORBIDDEN = 0x01


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _is_windows() -> bool:
    return sys.platform == "win32"


def _blob(data: bytes) -> _DATA_BLOB:
    buf = ctypes.create_string_buffer(data, len(data))
    return _DATA_BLOB(
        len(data),
        ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)),
    )


def dpapi_protect(plaintext: str) -> str:
    """Encrypt on Windows, or mark plaintext on non-Windows."""
    raw = plaintext.encode("utf-8")
    if not _is_windows():
        return PLAIN_PREFIX + plaintext
    try:
        crypt32 = ctypes.windll.crypt32
        in_blob = _blob(raw)
        out_blob = _DATA_BLOB()
        ok = crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            u"ssh-plugin",
            None,
            None,
            None,
            _CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out_blob),
        )
        if not ok:
            raise RuntimeError("Windows DPAPI encryption failed; credentials were not saved")
        try:
            enc = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)
        return ENCRYPTED_PREFIX + base64.b64encode(enc).decode("ascii")
    except Exception as exc:
        raise RuntimeError("Windows DPAPI encryption failed; credentials were not saved") from exc


def dpapi_unprotect(stored: str) -> str:
    """Decode a value written by :func:`dpapi_protect`."""
    if stored is None:
        return None
    if stored.startswith(PLAIN_PREFIX):
        return stored[len(PLAIN_PREFIX) :]
    if not stored.startswith(ENCRYPTED_PREFIX):
        # Legacy plaintext without prefix
        return stored
    b64 = stored[len(ENCRYPTED_PREFIX) :]
    raw = base64.b64decode(b64)
    if not _is_windows():
        raise RuntimeError("encrypted credentials require Windows DPAPI on this machine")
    try:
        crypt32 = ctypes.windll.crypt32
        in_blob = _blob(raw)
        out_blob = _DATA_BLOB()
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            _CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out_blob),
        )
        if not ok:
            raise RuntimeError("DPAPI unprotect failed (wrong user profile or corrupt data)")
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData).decode("utf-8")
        finally:
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"DPAPI unprotect error: {exc}") from exc


def is_encrypted(value: str | None) -> bool:
    return isinstance(value, str) and value.startswith(ENCRYPTED_PREFIX)


def encrypt_server_secrets(server: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with secret fields encoded for disk."""
    out = dict(server)
    for key in SECRET_FIELDS:
        val = out.get(key)
        if not val or is_encrypted(val):
            continue
        if isinstance(val, str) and val.startswith(PLAIN_PREFIX):
            if not _is_windows():
                continue
        out[key] = dpapi_protect(str(val))
    return out


def decrypt_server_secrets(server: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with secret fields usable in-process."""
    out = dict(server)
    for key in SECRET_FIELDS:
        val = out.get(key)
        if not val or not isinstance(val, str):
            continue
        if val.startswith(ENCRYPTED_PREFIX) or val.startswith(PLAIN_PREFIX):
            out[key] = dpapi_unprotect(val)
    return out
