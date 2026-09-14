---
feature: perf-loop-ssh
status: delivered
updated: 2026-09-14
branch: feature/ssh-deploy
commits: 2e6fa6a
---

# perf-loop-ssh：为外部性能插件提供稳定 SSH 与文件通道

## Report

**What was built** — 在既有 `ssh-plugin` 上增加进程内 SSH 连接池（keep-alive、失效探测、一次自动重连）、`ssh_health` 工具与 `/health/server`、`/conn/stats`；Skill `perf-loop` + Spec 内嵌 P0–P6/P-Fail 提示词计划表。本插件只做连接与文件通道，指标/出图由外部 Hermes 插件负责。

**Verification** — `py_compile` PASS；池复用/重试单测 PASS（mock）；`node --check` PASS。未对真实服务器联调。

**Journey log**
- 范围收窄：KPI/指标图不在本插件。
- 改参由外部插件驱动；本插件提供先读后写工具。
- 仍需 `plugins.enabled` 启用 + paramiko，否则 404。

## [S1] Problem

Hermes 侧后续会有**另一个插件**负责：跑代码、读性能、对「编写结果指标图」、汇总每轮迭代、驱动改参再跑。  
本 `ssh-plugin` **不负责**指标解析、达标判定或出图；它必须保证：

1. 与远程服务器的连接在 Agent 多轮工具调用中**尽量不断**（keep-alive + 断线重连）；  
2. Agent 能**稳定读到**远端文件/参数（以及在授权下写回参数）；  
3. 提供可复制的**提示词计划表**，供性能插件/用户在 Hermes 对话里按阶段调用本插件工具。

当前缺口：每次 REST/SFTP 大多短连接；长任务或网络抖动后易失败；缺少「探测连通 + 续跑」的 Agent 侧约定。

## [S2] Design

### 角色边界（务必遵守）

| 本插件负责 | 本插件不负责 |
|------------|--------------|
| SSH 连接配置、测试、保活、重连 | 解析训练日志 / 计算 KPI |
| SFTP 列表/读/写/删/传 | 判断是否「符合指标图」 |
| Agent 工具：读文件、写参数文件、远端受控执行 | 画图、汇总报表、迭代策略 |
| 连接健康与错误可诊断 | 性能插件内部算法 |

指标与验收由**外部 Hermes 插件**消费本插件读到的文件内容。

### 连接稳定性

1. **进程内连接池**（`ssh_session.py`）：按 `server.id` 复用 `paramiko` SSHClient + SFTP；  
2. **Keep-alive**：`keepalive_interval=15s`，降低空闲被防火墙掐断；  
3. **懒连接 + 重试**：请求时若连接失效则自动重连 1 次；  
4. **并发锁**：同一 server 的 SFTP 操作串行（paramiko 非线程安全）；  
5. **`ssh_health` 工具 / `GET /health/server?id=`**：探测主机、时延、是否需重连；  
6. **超时可配**：`connectionTimeoutMs` / `sftpTimeoutMs` 存于 server 配置（默认 30s / 120s）。

桌面 UI 状态胶囊显示最近健康状态（可选增强，非阻塞）。

### Agent 文件通道（给性能插件用）

已有能力保留，并明确推荐路径：

- 读参数/结果：`ssh_read_file` / `ssh_ls`  
- 大文件：`ssh_download`（受 `allowedLocalPaths`）  
- 写回参数：`ssh_write_file`（整文件覆盖；外部插件应先读后写）  
- 远端跑一轮：`ssh_exec`（`allow_exec` + 建议 `commandWhitelist`）

### 提示词计划表

见下方 [S2.1]。交付形态：**写在本 Spec**，并同步一份到 `skills/perf-loop/SKILL.md` 便于 Agent 加载。

#### [S2.1] 阶段提示词计划表

| 阶段 | 目标 | 建议提示词（可整段贴给 Hermes） | 本插件工具 | 完成判据（给外部性能插件） |
|------|------|--------------------------------|------------|---------------------------|
| P0 接入检查 | 确认插件与链路可用 | 「先调用 ssh_list_servers 与 ssh_health（目标 server）。若失败，报告是未启用插件、缺 paramiko、还是网络/认证问题，不要继续。」 | `ssh_list_servers`, `ssh_health` | health ok=true |
| P1 锁定目录 | 确认工作区与白名单 | 「列出远程实验根目录（server=…, path=…）。确认 params/config 与 results 目录存在；列出需要读写的文件名。」 | `ssh_ls` | 路径在 allowedRemotePaths 内且文件可见 |
| P2 读参数 | 取出可改参数 | 「读取参数文件全文（ssh_read_file）。只提取白名单参数键（如 lr、batch_size、阈值），禁止改其它字段。原样返回 JSON 草稿。」 | `ssh_read_file` | 键值列表完整、无密钥 |
| P3 触发一轮 | 远端跑实验 | 「用白名单命令启动一轮训练/评测（ssh_exec）。记录 run_id/输出路径。超时则报告，不要盲目重试危险命令。」 | `ssh_exec` | 进程启动或退出码可解释 |
| P4 读结果 | 拉性能文件 | 「读取/下载本轮 metrics 与日志路径（ssh_ls + ssh_read_file 或 ssh_download）。不要解析 KPI——交给性能插件；只要保证文件可读、未截断问题已说明。」 | `ssh_ls`, `ssh_read_file`, `ssh_download` | 文件内容完整或标明 truncated |
| P5 写参数 | 迭代改参 | 「按性能插件给出的新参数，先 ssh_read_file 再整文件写回 ssh_write_file；写后立刻再读校验 diff 仅限白名单键。」 | `ssh_read_file`, `ssh_write_file` | 写后校验一致 |
| P6 收尾 | 汇总路径清单 | 「汇总本轮读过的路径、写过的参数、exec 命令与退出码，输出结构化清单供性能插件存档。」 | （无写） | 清单可归档 |
| P-Fail 故障 | 连接/权限失败 | 「执行 ssh_health；若连接断开，重试一次列目录。仍失败则输出：server、path、错误串、是否 allow_exec/路径白名单问题。禁止猜测密码或改 config.yaml。」 | `ssh_health`, `ssh_ls` | 可诊断错误，不落密钥 |

**循环 SOP（外部性能插件驱动时）**

```text
P0 → P1 → [P2 → P3 → P4 →（性能插件判定）→ P5 → P3…] → P6
         └─ 失败则 P-Fail → 修复后回到 P0/P1
```

**提示词硬约束（写入 Skill）**

1. 不得读取或输出密码/私钥/`deployments.json`。  
2. 不得修改 Hermes 核心与本插件源码来「绕过」错误。  
3. 远端路径必须在 `allowedRemotePaths`；本地下载必须在 `allowedLocalPaths`。  
4. `ssh_exec` 仅白名单命令；禁止 `rm -rf`、反弹 shell、改 `/etc` 等。  
5. 大文件优先 download；`truncated=true` 必须声明。  
6. 写文件前必须先 read，禁止盲写。

### REST 增补

| Method | Path | 说明 |
|--------|------|------|
| GET | `/health/server?id=` | 单服务器连通/时延/是否复用连接 |
| GET | `/conn/stats` | 池内连接状态（不含密钥） |

### 错误行为

- 连接失败：返回明确 `detail`（认证/超时/拒连），不吞异常。  
- 自动重连失败：工具返回 JSON error，Agent 走 P-Fail。  
- 池化后单次操作仍失败：关闭该连接，下次新建。

## [S3] Out of Scope

- 性能指标解析、达标判定、指标图绘制、迭代策略（外部插件）  
- 修改 ssh-mcp-server 或 Hermes 核心  
- 读取/存储用户已有 ssh-mcp-server 密钥文件内容  
- 保证「永不掉线」（只做 keep-alive + 重连 + 可诊断）

## Tasks

- [x] T1: 实现连接池 `ssh_session.py` + keep-alive/重试 — acceptance: 同 server 连续两次 ls 不新建逻辑连接（stats 可见 reuse） (covers: S2)
- [x] T2: 接入 sftp_client/plugin_api 使用池；新增 `/health/server`、`ssh_health` — acceptance: 工具/路由存在且断连可自动恢复一次 (covers: S2; depends: T1)
- [x] T3: Skill `skills/perf-loop/SKILL.md` + Spec 同步提示词计划表 — acceptance: 表格与硬约束完整 (covers: S2)
- [x] T4: 静态校验与单测（池复用、重连、health） — acceptance: py_compile + 单测 PASS (covers: S2; depends: T2)
