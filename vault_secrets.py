"""Optional hermes-vault secret references for SSH server credentials.

A server may store password / passphrase / privateKeyContent as a vault ref:

    hv://service
    hv://service?alias=name

**Optional integration** — if ``hermes_vault`` is installed, refs are resolved
at connect time (secrets stay in memory only; never written back to
``deployments.json``; audit records the ref, not the secret).

If ``hermes_vault`` is **not** installed, this path is skipped entirely:
``hv://`` fields are treated as unset (cleared to ``None``) so the plugin
continues with DPAPI literals / key auth and does **not** fail the connect
with a missing-package error.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

try:
    from .audit_log import record as audit_record
except ImportError:
    from audit_log import record as audit_record  # type: ignore


class VaultRefError(RuntimeError):
    """Raised only when vault is available but a ref cannot be resolved."""


def is_vault_ref(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower().startswith("hv://")


def vault_available() -> bool:
    """True when hermes_vault can be imported in this environment."""
    try:
        from hermes_vault.vault import Vault  # noqa: F401
    except ImportError:
        return False
    return True


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
    """Resolve one hv:// reference. Caller must ensure vault_available()."""
    service, alias = parse_ref(raw)
    try:
        from hermes_vault.vault import Vault
    except ImportError as exc:
        raise VaultRefError(
            "hermes_vault is not installed; resolve_ref requires the optional package"
        ) from exc
    try:
        vault = Vault()
        record = vault.resolve_credential(service, alias)
    except Exception as exc:  # noqa: BLE001
        raise VaultRefError(f"vault resolve failed for {service}/{alias or '-'}: {exc}") from exc
    secret = getattr(record, "secret", None) or getattr(record, "value", None)
    if not secret:
        raise VaultRefError(f"vault credential {service}/{alias or '-'} has empty secret")
    return str(secret)


def _resolve_field(field: str, value: Any, server_id: str | None) -> str:
    secret = resolve_ref(value)
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
    """Copy *server*, resolving hv:// refs when vault is installed.

    No vault package → skip the vault path: clear refs to None (do not send
    ``hv://…`` as a password) and leave literal credentials untouched.
    """
    if not server:
        return server
    out = dict(server)
    ref_fields = [f for f in ("password", "passphrase", "privateKeyContent", "privateKey") if is_vault_ref(out.get(f))]
    if not ref_fields:
        return out
    if not vault_available():
        for field in ref_fields:
            out[field] = None
        if is_vault_ref(server.get("privateKey")):
            out["privateKey"] = None
        return out
    sid = out.get("id") or out.get("name")
    for field in ("password", "passphrase", "privateKeyContent"):
        if is_vault_ref(out.get(field)):
            out[field] = _resolve_field(field, out[field], sid)
    if is_vault_ref(out.get("privateKey")):
        content = _resolve_field("privateKey", out["privateKey"], sid)
        out["privateKeyContent"] = content
        out["privateKey"] = None
        out["auth"] = "key"
    return out
