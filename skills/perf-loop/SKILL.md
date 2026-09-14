---
name: perf-loop
description: Prompt plan for Hermes agent to keep SSH alive and read/write remote files for an external performance-iteration plugin
---

# perf-loop — 连接与文件通道（不负责指标判定）

性能指标、指标图、迭代策略由**另一个 Hermes 插件**处理。你只负责：连上服务器、读/写文件、（可选）白名单远端命令。

## 硬约束

1. 不读、不打印密码/私钥/`deployments.json`。
2. 不改 Hermes 核心或本插件源码来绕过错误。
3. 远端路径必须在 `allowedRemotePaths`；本地路径必须在 `allowedLocalPaths` 或进程 cwd。
4. `ssh_exec` 仅白名单命令；禁止 `rm -rf`、反弹 shell、改系统目录。
5. 写文件前必须先 `ssh_read_file`；写后再读校验。
6. 大文件用 `ssh_download`；`truncated=true` 必须向用户/外部插件声明。

## 阶段提示词（可直接复述）

### P0 接入检查
先 `ssh_list_servers`，再对目标 server 执行 `ssh_health`。失败则报告原因（未启用插件 / 缺 paramiko / 网络认证），不要继续。

### P1 锁定目录
`ssh_ls` 实验根目录，确认 params 与 results 可见且在白名单内。

### P2 读参数
`ssh_read_file` 参数文件；只提取白名单键（如 lr、batch_size），输出 JSON 草稿给外部性能插件。

### P3 触发一轮
用白名单 `ssh_exec` 启动训练/评测；记录输出路径与退出码。超时不要盲目重试危险命令。

### P4 读结果
`ssh_ls` + `ssh_read_file` 或 `ssh_download` 拉取 metrics/日志。**不要判定 KPI**——只保证文件可读。

### P5 写参数
按外部插件给出的新参数：先读 → `ssh_write_file` 整文件写回 → 再读校验仅白名单键变化。

### P6 收尾
输出本轮：路径清单、改过的参数、exec 命令与退出码。

### P-Fail 故障
`ssh_health` → 重试一次 `ssh_ls`。仍失败输出 server/path/错误与白名单问题。禁止猜密码。

## 循环

`P0 → P1 → (P2 → P3 → P4 → [外部判定] → P5 → P3…) → P6`  
失败走 P-Fail 后回 P0/P1。
