# Changelog

## 0.2.1

### Added
- **Optional subprocess bridge** — `SSH_PLUGIN_BRIDGE=1` runs REST SSH/SFTP in a persistent worker (`SSH_PLUGIN_BRIDGE_ONESHOT=1` for per-call isolation). Default remains in-process.
- **Optional vault refs** — password / passphrase / key fields may use `hv://service[?alias=]`. Resolved only when `hermes_vault` is installed; otherwise the path is skipped (no connect failure).
- Desktop form hints for `hv://` refs; Operations panel extract for sync confirm.

### Fixed
- Desktop `plugin.js` missing `)` that prevented Hermes ESM load.
- `download_tree` re-checks remote allowlist at open time (symlink TOCTOU) and caps walk entry count.
- Dual-mount DeployPage no longer double-fetches `/fs/ls` or double-probes the backend.
- CI checks Desktop plugin as ESM (`.mjs`) in addition to script parse.
- Delete-server clears matching pending write; failed tree load can retry on remount.

### Docs
- README restructured for install / optional integrations / security summary.
- Feature specs: `server-switch-fix`, `ssh-bridge`, `vault-secrets`.

## 0.2.0

- Desktop: server switcher via SDK DropdownMenu; delete-server with confirm dialog; dual-mount tree bootstrap dedupe; OperationsPanel for batch sync + audit.
- Backend: SSH REST off the event loop (`_ssh_call` thread pool); default connect timeout 10s; `treeEpoch` drops stale tree responses.
- Agent: bounded `ssh_download_tree` / `/fs/download-tree` (open-time remote path re-guard + entry cap); `ssh_glob` and `ssh_tail`.
- Security: download open path re-checks allowlist (TOCTOU); write dry-run; path allowlists; allow_exec gating unchanged.
- Tests: 34 unit tests including download TOCTOU and entry-limit regressions.

## 0.1.x (earlier)

- Unified package: Desktop UI, REST, Agent tools, DPAPI secrets, audit log, mappings/exclusions, sync/chunked read.
- Server-switch freeze fix (thread pool + DropdownMenu) and delete-server UI.
