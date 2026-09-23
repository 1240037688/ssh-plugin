# Security Policy

## What this plugin can do

`ssh-plugin` is a **local-first** Hermes unified package. When enabled, it can:

- Hold SSH connection settings under `$HERMES_HOME/plugin-data/ssh-plugin/deployments.json` (**Windows DPAPI** protects secret fields at rest; see limitations)
- Perform SFTP list/read/write/delete/upload/download against configured hosts
- Optionally run remote commands when `allow_exec` is true (default **false**)

Desktop plugins and Python gateway plugins in Hermes run with **full trust** in the host process. This is not a sandbox.

## Hardening built in

| Control | Default |
|---------|---------|
| Secrets in REST / `ssh_list_servers` | Masked (`***`) |
| Agent-facing host/username | Default `ssh_list_servers` returns only `name` / `configured` / `allow_exec`. `unmask: true` may show real host/user/port — never passwords, never derived `endpoint` / `connectionString` / `userHost` / `host:port` when masked |
| `allowedRemotePaths` | Optional prefix allowlist; empty = unrestricted (warns via `securityWarnings`) |
| `allowedLocalPaths` | Limits local upload/download (plus process cwd) |
| `commandWhitelist` / `commandBlacklist` | Optional; whitelist enables full-match + shell-metachar rejection |
| `ssh_exec` | Disabled unless `allow_exec` |
| Write path | Dry-run / unified diff before overwrite (Desktop confirm; API `dryRun`) |
| Host header | Loopback check on plugin API routes |
| Host keys | `known_hosts` + RejectPolicy when the file exists |
| Secrets at rest | **Windows DPAPI (CurrentUser)** — `enc:dpapi:v1:…` in `deployments.json` |
| Subprocess bridge | Optional: `SSH_PLUGIN_BRIDGE=1` runs REST SSH/SFTP in a **persistent** worker (`ssh_bridge_worker.py`) so the child's SSH pool/keepalive can survive across requests. `SSH_PLUGIN_BRIDGE_ONESHOT=1` forces a fresh process per call. Default **off**. |
| Vault secret refs | Optional: `hv://service[?alias=]` in password fields. Resolved **only when `hermes_vault` is installed**; if not installed the vault path is skipped (field unset) — connect does not fail due to a missing package. |

## Known limitations

1. **DPAPI is user-scoped, not machine-isolated.** Any process running as the same Windows account can decrypt. Non-Windows stores `plain:` prefixes. Never commit `deployments.json`.
2. **In-process SSH (paramiko) by default.** A compromised gateway process can use stored credentials. Set `SSH_PLUGIN_BRIDGE=1` to keep crashes/paramiko in a child process (still same OS user; not a full sandbox). For higher isolation, keep secrets in a dedicated vault product and avoid long-lived passwords here.
3. **Bridge worker is per-request.** No cross-process connection pool/keepalive; isolation trades off reconnect latency.
4. **No remote-source plugin loading.** Only install this package from a source you trust.

## Reporting a vulnerability

Please open a **private** security advisory on the GitHub repository, or email the maintainers listed in the repo profile. Do not file public issues that include live credentials, host IPs, or exploit details against third-party systems.

Include:

- Plugin commit SHA / version
- Hermes Desktop / gateway version
- Minimal reproduction without real secrets
- Impact assessment

We will acknowledge as soon as practical and coordinate a fix before disclosure.
