---
name: ssh-deploy
description: Visual SSH deployment & remote file management for Hermes (list/read/write/delete SFTP files; PyCharm-style servers & mappings)
---

# SSH Deploy skill

Use the `ssh_*` tools from the `ssh-plugin` package to manage remote servers.

## Before using tools

1. Call `ssh_list_servers` to see configured servers (name or id).
2. If the list is empty, tell the user to open **SSH 部署** in Hermes Desktop and add a server, or write `deployments.json` under `HERMES_HOME/plugin-data/ssh-plugin/`.

## Common flows

- Browse: `ssh_ls` with absolute path (default `/`).
- Read config: `ssh_read_file`.
- Create/update file: `ssh_write_file` (full content; parent dirs auto-created).
- Create folder: `ssh_mkdir`.
- Delete: `ssh_delete`; directories need `recursive: true`.
- Transfer: `ssh_upload` / `ssh_download` (local ↔ remote paths).
- Shell: `ssh_exec` only if the server has `allow_exec: true`.

## Safety

- Paths must stay absolute; `..` is rejected.
- If the server defines `allowedRemotePaths`, operations outside those prefixes fail.
- Never invent credentials. Secrets live only on the gateway host.

## Desktop UI

The same package ships a desktop pane at route `/ssh-deploy` (sidebar **SSH 部署**): server list, remote tree, editor, image preview, mappings/exclusions.
