# Security Policy

## What this plugin can do

`ssh-plugin` is a **local-first** Hermes unified package. When enabled, it can:

- Hold SSH connection settings (including passwords / key paths) under `$HERMES_HOME/plugin-data/ssh-plugin/deployments.json` (**plaintext** today — see known limitations)
- Perform SFTP list/read/write/delete/upload/download against configured hosts
- Optionally run remote commands when `allow_exec` is true (default **false**)

Desktop plugins and Python gateway plugins in Hermes run with **full trust** in the host process. This is not a sandbox.

## Hardening built in

| Control | Default |
|---------|---------|
| Secrets in REST / `ssh_list_servers` | Masked (`***`) |
| Agent-facing host/username | Masked (`***`) unless `unmask: true` |
| `allowedRemotePaths` | Optional prefix allowlist; empty = unrestricted (warns via `securityWarnings`) |
| `allowedLocalPaths` | Limits local upload/download (plus process cwd) |
| `commandWhitelist` / `commandBlacklist` | Optional; whitelist enables full-match + shell-metachar rejection |
| `ssh_exec` | Disabled unless `allow_exec` |
| Write path | Dry-run / unified diff before overwrite (Desktop confirm; API `dryRun`) |
| Host header | Loopback check on plugin API routes |
| Host keys | `known_hosts` + RejectPolicy when the file exists |

## Known limitations

1. **Credentials at rest are not encrypted.** Do not commit `deployments.json`. Prefer key auth without storing passphrases, or restrict OS file ACLs.
2. **In-process SSH (paramiko).** A compromised gateway process can use stored credentials. For higher isolation, keep secrets in a dedicated vault product and avoid long-lived passwords here.
3. **No remote-source plugin loading.** Only install this package from a source you trust.

## Reporting a vulnerability

Please open a **private** security advisory on the GitHub repository, or email the maintainers listed in the repo profile. Do not file public issues that include live credentials, host IPs, or exploit details against third-party systems.

Include:

- Plugin commit SHA / version
- Hermes Desktop / gateway version
- Minimal reproduction without real secrets
- Impact assessment

We will acknowledge as soon as practical and coordinate a fix before disclosure.
