---
feature: ssh-bridge
status: in-progress
updated: 2026-09-16
branch: feat/ssh-bridge
commits: pending
---

# 子进程 SSH Bridge 隔离

## Report

## [S1] Problem

REST 已用线程池避免阻塞事件循环，但 paramiko 仍在 gateway 进程内：崩溃与凭据内存与 Hermes 共享。HANDOFF P2。

## [S2] Design

- `ssh_bridge.py` + `ssh_bridge_worker.py`（stdin/stdout JSON 行）。
- 开关：`SSH_PLUGIN_BRIDGE` ∈ {1,true,yes,on}；**默认关闭**。
- `plugin_api._remote(op, payload)`：关→进程内线程池；开→短生命周期 worker。
- ops：list_dir/read_text/write_text/mkdir/delete/rename/upload/download/preview/test/health/download_tree/sync_plan/exec。
- download 在 bridge 下返回 base64 信封，REST 兼容。

## [S3] Out of Scope

- 跨进程 keepalive 连接池、vault 密钥、Desktop 开关 UI。

## Tasks

- [ ] T1: bridge + REST 分发 — acceptance: 默认行为不变；开启后经子进程
- [ ] T2: 单测 — acceptance: unittest 全绿
