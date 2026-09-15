# ssh-plugin — Hermes SSH Deploy

[![CI](https://github.com/1240037688/ssh-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/1240037688/ssh-plugin/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Visual SSH/SFTP file management for [Hermes](https://hermes-agent.nousresearch.com/docs/) — PyCharm Deployment-style mappings, keep-alive sessions, REST API, and Agent tools in one **unified package**.

**Current release: `0.2.1`** · [Changelog](CHANGELOG.md)

| | |
|--|--|
| **Desktop** | Three-pane remote host UI at `/ssh-deploy` |
| **REST** | `/api/plugins/ssh-plugin/*` |
| **Agent** | `ssh_*` tools (list, health, ls, read/write, sync, glob, tail, download tree, exec) |
| **Security** | DPAPI secrets (Windows), path allowlists, dry-run writes, optional process bridge, optional vault refs |

---

## Quick start

1. Install **paramiko** in the Hermes gateway environment (Hermes does not auto-pip-install plugin deps):

   ```bash
   python -m pip install "paramiko>=3.0.0"
   ```

2. Clone this repo into the **active profile** plugin root (paths vary by machine/profile):

   ```bash
   # Example: code profile on Windows
   git clone https://github.com/1240037688/ssh-plugin "D:/hermes/profiles/code/plugins/ssh-plugin"

   # Example: default layout on Linux/macOS
   git clone https://github.com/1240037688/ssh-plugin "$HOME/.hermes/plugins/ssh-plugin"
   ```

3. Enable the Python half in the profile `config.yaml`:

   ```yaml
   plugins:
     enabled:
       - ssh-plugin
   ```

4. Restart Hermes Desktop / gateway.

5. Open **Capabilities → Plugins** and turn **ssh-plugin** on (unified desktop half is opt-in).

6. Use **SSH 部署** / command palette to add servers. Credential file lives under the profile plugin-data directory — **never commit** it.

> After changing plugin files, pull/copy into the profile plugin folder and restart Hermes.

---

## Desktop UI

- Server switcher (dropdown), add / edit / **delete** (with confirm), test connection, set default
- Lazy remote file tree, text editor, image preview
- Write path: dry-run + unified-diff confirm before overwrite
- **Operations** panel: mapping-based batch sync preview/confirm + audit tail
- Server form accepts optional **`hv://service[?alias=]`** password refs (see Security)

Offline browser mock (no Hermes): open `preview/index.html`.

---

## Agent tools

| Tool | Notes |
|------|--------|
| `ssh_list_servers` | Host/username masked by default |
| `ssh_health` | Connectivity / latency probe |
| `ssh_ls` / `ssh_read_file` | Directory listing; chunked file read (`offset`/`limit`) |
| `ssh_write_file` | Prefer `dryRun: true` for unified diff first |
| `ssh_map_path` | Local ↔ remote mapping |
| `ssh_mkdir` / `ssh_delete` | Bounded remote mutations |
| `ssh_upload` / `ssh_download` | Local path allowlist applies |
| `ssh_download_tree` | Bounded tree download; dry-run default |
| `ssh_glob` / `ssh_tail` | Result discovery / log tail |
| `ssh_sync` | Mapping batch upload; dry-run default |
| `ssh_exec` | Only if server `allow_exec`; prefer `commandWhitelist` |

External performance-loop prompts: `skills/perf-loop/SKILL.md` (this plugin stays SSH + files only).

---

## Optional integrations

### Subprocess bridge (process isolation)

```bash
# Run REST SSH/SFTP in a persistent child worker (keepalive across requests)
SSH_PLUGIN_BRIDGE=1

# Or one process per call
SSH_PLUGIN_BRIDGE=1
SSH_PLUGIN_BRIDGE_ONESHOT=1
```

Default: **off** (in-process thread pool). See [SECURITY.md](SECURITY.md).

### hermes-vault secret refs

Password / passphrase / private key fields may be:

```text
hv://service
hv://service?alias=name
```

- **If `hermes_vault` is installed** — resolved at connect time (memory only; not written back to disk).
- **If not installed** — the vault path is **skipped** (ref treated as unset); the plugin continues with stored literals.

---

## Security (summary)

Full policy: [SECURITY.md](SECURITY.md).

- Secrets at rest: Windows **DPAPI** (`enc:dpapi:v1:…`); non-Windows uses explicit `plain:` (do not commit `deployments.json`)
- Agent host mask; REST masks secrets
- `allowedRemotePaths` / `allowedLocalPaths`; command whitelist/blacklist
- Writes: dry-run + confirm
- Host-key policy: `known_hosts` + RejectPolicy when available
- `allow_exec` default **false**

---

## Package layout

```text
ssh-plugin/
├── plugin.yaml                 # agent manifest
├── __init__.py                 # register tools
├── schemas.py / tools.py
├── deployment_store.py         # servers / mappings
├── deploy_paths.py             # mask, map, diff
├── security.py / ssh_session.py / sftp_client.py
├── download_plan.py / sync_plan.py
├── vault_secrets.py            # optional hv:// refs
├── ssh_bridge.py               # optional subprocess bridge
├── ssh_bridge_worker.py
├── dashboard/                  # REST adapter + manifest
├── desktop/plugin.js           # Desktop UI (no JSX build)
├── skills/
├── preview/                    # offline UI mock
├── tests/                      # offline unit tests
└── docs/compose/spec/          # feature notes
```

---

## What's new in 0.2.x

- Multi-server switch without freezing the UI; delete server with confirm
- Batch sync + audit in the Desktop **Operations** panel
- `ssh_download_tree` / `ssh_glob` / `ssh_tail` for pulling remote results
- Optional `SSH_PLUGIN_BRIDGE=1` process isolation (persistent worker + keepalive)
- Optional `hv://…` vault password refs when `hermes_vault` is installed

---

## Development

```bash
# Desktop syntax (Hermes loads as ESM — also check as .mjs)
node --check desktop/plugin.js
cp desktop/plugin.js /tmp/plugin.mjs && node --check /tmp/plugin.mjs

# Unit tests (needs fastapi/pydantic/paramiko in the env)
python -m unittest discover -s tests -v
```

Contributing: [CONTRIBUTING.md](CONTRIBUTING.md) · Changelog: [CHANGELOG.md](CHANGELOG.md) · Specs: `docs/compose/spec/`.

---

## License

[MIT](LICENSE)

Acknowledgments: [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md).
