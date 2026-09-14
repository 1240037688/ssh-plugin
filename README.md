# ssh-plugin — Hermes SSH Deploy

[![CI](https://github.com/1240037688/ssh-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/1240037688/ssh-plugin/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Hermes **unified package** plugin: visual SSH/SFTP file manager (PyCharm-style mappings) + keep-alive sessions + Agent tools.

Repository: https://github.com/1240037688/ssh-plugin

## Features

| Surface | What you get |
|---------|----------------|
| **Desktop** | Route `/ssh-deploy`（侧栏 SSH 部署）：服务器列表、远程树、编辑器、图片预览、连接测试、Mappings/Exclusions、**写前 Diff 确认**、批量同步预览与审计记录 |
| **Backend** | FastAPI router at `/api/plugins/ssh-plugin/` |
| **Agent tools** | `ssh_list_servers` `ssh_health` `ssh_ls` `ssh_read_file` `ssh_write_file` `ssh_map_path` `ssh_mkdir` `ssh_delete` `ssh_upload` `ssh_download` `ssh_download_tree` `ssh_glob` `ssh_tail` `ssh_sync` `ssh_exec` |
| **Security** | Secret masking, host mask for agents, path allowlists, command whitelist, dry-run writes |

## Layout

```text
ssh-plugin/
├── plugin.yaml                 # agent manifest + python_dependencies
├── __init__.py                 # register tools + skills
├── schemas.py / tools.py
├── deployment_store.py         # servers / mappings (local data dir)
├── deploy_paths.py             # host mask + mapping + unified diff
├── security.py / ssh_session.py / sftp_client.py
├── dashboard/
│   ├── manifest.json
│   └── plugin_api.py           # REST for Desktop
├── desktop/plugin.js           # Hermes Desktop UI (no JSX build step)
├── skills/perf-loop/SKILL.md
├── preview/                    # offline UI mock (browser)
├── tests/                      # offline unit tests
└── docs/compose/spec/          # design notes
```

## Install

1. **Dependencies** (Hermes does **not** auto-install):

```bash
python -m pip install "paramiko>=3.0.0"
```

2. **Install package** into the active Hermes profile's plugin root. Use the profile selected by Hermes; the `code` profile on this machine uses `D:\hermes\profiles\code\plugins\ssh-plugin`.

```bash
# Linux / macOS (replace the profile path as needed)
git clone https://github.com/1240037688/ssh-plugin "$HOME/.hermes/plugins/ssh-plugin"

# Windows (PowerShell) — replace with the active profile path
git clone https://github.com/1240037688/ssh-plugin "D:\hermes\profiles\code\plugins\ssh-plugin"
```

3. **Enable Python half** in `$HERMES_HOME/config.yaml`:

```yaml
plugins:
  enabled:
    - ssh-plugin
```

4. **Restart** Hermes gateway / Desktop. Enable **Capabilities → Plugins → ssh-plugin** (unified packages ship opt-in).

5. Configure servers in **SSH 部署** UI. Secrets stay under `$HERMES_HOME/plugin-data/ssh-plugin/` — **never commit** that file.

## Agent tools (summary)

- `ssh_list_servers` — host/username **masked** by default (`unmask: true` to reveal, still no passwords)
- `ssh_write_file` — set `dryRun: true` to get a unified diff first
- `ssh_map_path` — PyCharm-style local ↔ remote mapping
- `ssh_upload` — optional `remotePath` (auto-mapped from local when omitted)
- `ssh_download_tree` — bounded directory download to an allowed local path; dry-run by default
- `ssh_glob` / `ssh_tail` — bounded remote result search and log tail
- `ssh_sync` — batch upload via mappings; dry-run by default
- `ssh_exec` — only if `allow_exec`; prefer `commandWhitelist`

See `skills/perf-loop/SKILL.md` for a staged prompt plan (P0–P6) used with external performance plugins.

## Security

Read [SECURITY.md](SECURITY.md). Highlights:

- Credentials at rest are protected with **Windows DPAPI** (CurrentUser) in `deployments.json` (`enc:dpapi:v1:…`); same OS account can still decrypt — protect your login
- Prefer key auth; set `allowedRemotePaths` and leave `allow_exec` off unless required
- Desktop/API writes support dry-run + confirm

## Development

```bash
node --check desktop/plugin.js
python -m unittest discover -s tests -v
```

Contributions: [CONTRIBUTING.md](CONTRIBUTING.md).

## Browser preview (no Hermes)

Open `preview/index.html` for an offline mock of the three-pane UI (mock filesystem only).

## Acknowledgments

See [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md).

## License

[MIT](LICENSE)
