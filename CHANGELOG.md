# Changelog

## Unreleased

- Fixed SSH connection lock release after failed handshakes, sync path checks and nested exclusions, and write-preview error handling.
- Prevented Windows credential saves when DPAPI encryption fails.
- Added bounded `ssh_download_tree` / `/fs/download-tree` for remote directory downloads into allowed local paths.
- Added `ssh_glob` and `ssh_tail` Agent tools for result discovery and log reading.
- Added Desktop batch-sync preview/confirmation and audit history panel.
