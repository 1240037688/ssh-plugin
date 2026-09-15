---
feature: ssh-bridge
status: delivered
updated: 2026-09-16
branch: feat/ssh-bridge
commits: 3e33199..ab9b3fa
---

# 子进程 SSH Bridge 隔离

## Report

**What was built** — 可选子进程隔离：`SSH_PLUGIN_BRIDGE=1` 时，REST SSH/SFTP 经长驻 `ssh_bridge_worker.py` 执行（可跨请求复用 SSH 池/keepalive）；`SSH_PLUGIN_BRIDGE_ONESHOT=1` 可退回每请求新进程。默认仍走 `_remote` + 线程池。download/upload 使用 JSON 安全信封。

**Verification** — `unittest discover` 42 PASS；`py_compile` bridge/api PASS；默认 `SSH_PLUGIN_BRIDGE` 未设时 `bridge_enabled()` 为 False；`call("no_such_op")` 返回结构化 `unknown op` 错误。

**Journey log**
- 未提交就 `worktree remove --force` 会丢文件；必须先 commit 再删 worktree。
- REST 用命名 op + payload，而不是传函数对象，才能跨进程。
- download 在 bridge 下不能返回 raw bytes，需 base64 信封并在 REST 归一。

## [S1] Problem

REST 已用线程池避免阻塞事件循环，但 paramiko 仍在 gateway 进程内：崩溃与凭据内存与 Hermes 共享。HANDOFF P2。

## [S2] Design

- `ssh_bridge.py` + `ssh_bridge_worker.py`（stdin/stdout JSON 行）。
- 开关：`SSH_PLUGIN_BRIDGE` ∈ {1,true,yes,on}；**默认关闭**。
- `plugin_api._remote(op, payload)`：关→进程内线程池；开→bridge worker。
- ops：list_dir/read_text/write_text/mkdir/delete/rename/upload/download/preview/test/health/download_tree/sync_plan/exec。
- download 在 bridge 下返回 base64 信封，REST 兼容。
- Worker lifetime：默认 **长驻复用**（跨请求保留子进程 SSH 池/keepalive）；`SSH_PLUGIN_BRIDGE_ONESHOT=1` 每请求新进程；崩溃/超时后下次自动重启。

## [S3] Out of Scope

- 跨进程 keepalive 连接池、vault 密钥、Desktop 开关 UI。

## Tasks

- [x] T1: bridge + REST 分发 — acceptance: 默认行为不变；开启后经子进程
- [x] T2: 单测 — acceptance: unittest 全绿
