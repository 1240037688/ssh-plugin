"""Optional hermes-vault secret references for SSH server credentials.

A server may store password / passphrase / privateKeyContent as a vault ref:

    hv://service
    hv://service?alias=name

When the ref is seen at connect time, ``hermes_vault.Vault.resolve_credential``
is used if the package is importable. Resolved secrets stay in memory only and
are never written back to ``deployments.json`` or audit logs.

If ``hermes_vault`` is not installed, resolution raises a clear error so the
operator can fall back to DPAPI-stored literals.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

try:
    from .audit_log import record as audit_record
except ImportError:
    from audit_log import record as audit_record  # type: ignore


class VaultRefError(RuntimeError):
    pass


def is_vault_ref(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower().startswith("hv://")


def parse_ref(raw: str) -> tuple[str, str | None]:
    """Return (service, alias) from hv://service[?alias=name]."""
    text = (raw or "").strip()
    if not text.lower().startswith("hv://"):
        raise VaultRefError(f"not a vault ref: {text[:40]}")
    parsed = urlparse(text)
    service = (parsed.netloc or parsed.path.lstrip("/")).strip()
    if not service:
        raise VaultRefError("vault ref missing service")
    alias = None
    if parsed.query:
        qs = parse_qs(parsed.query)
        vals = qs.get("alias") or []
        if vals:
            alias = vals[0].strip() or None
    return service, alias


def resolve_ref(raw: str) -> str:
    """Resolve one hv:// reference to a secret string (never logged)."""
    service, alias = parse_ref(raw)
    try:
        from hermes_vault.vault import Vault
    except ImportError as exc:
        raise VaultRefError(
            "hermes_vault is not installed in this gateway environment; "
            "cannot resolve hv:// secret refs"
        ) from exc
    try:
        vault = Vault()
        record = vault.resolve_credential(service, alias)
    except Exception as exc:  # noqa: BLE001 — map vault errors to a single type
        raise VaultRefError(f"vault resolve failed for {service}/{alias or '-'}: {exc}") from exc
    secret = getattr(record, "secret", None) or getattr(record, "value", None)
    if not secret:
        raise VaultRefError(f"vault credential {service}/{alias or '-'} has empty secret")
    return str(secret)


def _maybe_resolve(field: str, value: Any, server_id: str | None) -> Any:
    if not is_vault_ref(value):
        return value
    try:
        secret = resolve_ref(value)
    except VaultRefError:
        raise
    audit_record(
        "vault_resolve",
        server_id=server_id,
        path=None,
        ok=True,
        source="connect",
        detail={"field": field, "ref": value},
    )
    return secret


def resolve_server_secrets(server: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *server* with hv:// refs replaced by in-memory secrets."""
    if not server:
        return server
    out = dict(server)
    sid = out.get("id") or out.get("name")
    for field in ("password", "passphrase", "privateKeyContent"):
        if is_vault_ref(out.get(field)):
            out[field] = _maybe_resolve(field, out[field], sid)
    # privateKey path may also be a ref (inline key content via vault)
    if is_vault_ref(out.get("privateKey")):
        content = _maybe_resolve("privateKey", out["privateKey"], sid)
        out["privateKeyContent"] = content
        out["privateKey"] = None
        out["auth"] = "key"
    return out
