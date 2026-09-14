# Changelog

## 0.2.0

- Desktop: server switcher via SDK DropdownMenu; delete-server with confirm dialog; dual-mount tree bootstrap dedupe; OperationsPanel for batch sync + audit.
- Backend: SSH REST off the event loop (`_ssh_call` thread pool); default connect timeout 10s; `treeEpoch` drops stale tree responses.
- Agent: bounded `ssh_download_tree` / `/fs/download-tree` (open-time remote path re-guard + entry cap); `ssh_glob` and `ssh_tail`.
- Security: download open path re-checks allowlist (TOCTOU); write dry-run; path allowlists; allow_exec gating unchanged.
- Tests: 34 unit tests including download TOCTOU and entry-limit regressions.

## Unreleased

- Fixed SSH connection lock release after failed handshakes, sync path checks and nested exclusions, and write-preview error handling.
- Prevented Windows credential saves when DPAPI encryption fails.
- Added bounded `ssh_download_tree` / `/fs/download-tree` for remote directory downloads into allowed local paths.
- Added `ssh_glob` and `ssh_tail` Agent tools for result discovery and log reading.
- Added Desktop batch-sync preview/confirmation and audit history panel.
