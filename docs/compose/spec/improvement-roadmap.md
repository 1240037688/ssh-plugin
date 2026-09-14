---
feature: improvement-roadmap
status: designed
updated: 2026-09-14
branch: feature/ssh-deploy
commits: pending
---

# improvement-roadmap：竞品分析解读与改进学习方向

## Report

## [S1] Problem

用户提供一段「全网/GitHub 检索结论」：称本插件在 Hermes 生态中全栈闭环较独特，并点名 3 个近邻方案与 2 条可借鉴设计。需要：

1. **消化并校准**该结论（哪些可信、哪些需降调）；  
2. **整理出可执行的改进/学习方向**（不是空泛夸赞）；  
3. 明确与社区方案的关系（吸收什么、不做什么）。

## [S2] Design

### 对原文的校准

| 原文判断 | 评估 | 说明 |
|----------|------|------|
| 「尚无完全对标成熟项目」 | **基本可信（以本地知识 + 所述检索为限）** | Hermes 插件生态新且碎；「无完全对标」≠「无同类」，公开检索可能不全 |
| 「全栈闭环独创/领先」 | **部分成立** | Desktop + `plugin_api` + paramiko + Agent 工具 + Mappings 确为少见组合；但 vault 在「Desktop+后端+安全模型」上更工程化，不可过度自夸 |
| remote-hosts 最近 | **合理** | 纯 Gateway 工具、OpenSSH、无 GUI——差异真实 |
| `terminal.backend: ssh` 不是部署工具 | **正确** | 整环境迁移 ≠ 项目文件部署 |
| 纯前端 desktop 插件集 | **正确** | 无 SFTP 底座 |
| 别名保护 / Dry-Run Diff | **高价值、应吸收** | 直接增强安全与误操作防护 |

### 改进 / 学习方向（按优先级）

#### A. 安全与可审计（P0，建议先做）

| # | 方向 | 说明 | 验收 |
|---|------|------|------|
| A1 | **Host 别名对外暴露** | Agent 工具与部分 REST 默认返回 `alias`（如 `srv_prod`），**不回传**真实 `host`/`username`；Desktop 编辑界面可显示完整信息给操作者 | `ssh_list_servers` / `/servers` 在 `maskHosts: true`（默认）时无明文 IP |
| A2 | **写操作 Dry-Run / Diff** | `ssh_write_file` 与 Desktop 保存前：先 `read` 远端，生成 unified diff；需 `confirm` 或 `dryRun=true` 才真正写 | API：`POST /fs/write` 支持 `dryRun`；Desktop 显示 diff 对话框 |
| A3 | **凭据落盘加密（P1）** | 对齐 vault 思路：DPAPI/系统钥匙串或调用 hermes-vault，避免明文 `deployments.json` | 磁盘无明文 password |
| A4 | **审计日志** | 记录 who/when/server/path/op（不含密钥），可选 `plugin-data/audit.jsonl` | 一次 write 可在审计文件查到 |

#### B. 部署能力补全（P1，对标 PyCharm 更深）

| # | 方向 | 说明 |
|---|------|------|
| B1 | **Mappings 真正驱动同步** | 现在 Mappings 多为配置展示；应：本地选文件/目录 → 按 mapping 换算远端路径 → 上传；排除规则生效 |
| B2 | **批量上传 / 目录树同步** | `ssh_sync`：按 mapping 上传变更文件列表（先 dry-run） |
| B3 | **下载到工作区** | 对齐 `allowedLocalPaths`，把远端结果目录拉到本地供性能插件分析 |

#### C. Agent 自动化闭环（P1，服务性能迭代插件）

| # | 方向 | 说明 |
|---|------|------|
| C1 | **分块读大文件** | `ssh_read_file(offset, limit)`，避免 1MB 截断导致指标读不全 |
| C2 | **结果清单工具** | `ssh_glob` / `ssh_tail`（日志尾部），方便外部性能插件 |
| C3 | **会话亲和** | 同一 `run_id` 的 exec/读文件打同一服务器与 keep-alive 池（已有池，补文档与 `ssh_health` 心跳） |

#### D. 工程与生态（P2，开源/Catalog）

| # | 方向 | 说明 |
|---|------|------|
| D1 | **借鉴 remote-hosts 的工具面** | 保持我们 GUI；工具命名/错误码可对齐社区习惯，降低学习成本 |
| D2 | **hermes-vault 安全深度** | 子进程 bridge、Host 校验已部分对齐；mutation 默认关、错误信封可再收紧 |
| D3 | **发布准备** | README 英文、截图、`hermes://plugin/install`、CHANGELOG、CI 单测 |
| D4 | **不要做的** | 不把 `terminal.backend: ssh` 当竞争功能去「模仿」；不与纯前端小插件比数量 |

### 学习路径（给人和给 Agent）

```text
1) 读完本 Spec + ssh-deploy / perf-loop / plugin-compliance
2) 对照 hermes-vault：安全模型、tests、manifest
3) 对照 remote-hosts（若可克隆）：别名、路径沙箱、工具最小集
4) 按 A→B→C 顺序实现；每项带单测 + 手工 Desktop 验收
```

### 与原文「差异化壁垒」的务实表述

- **已具备**：Desktop UI、REST、paramiko 池化 SFTP、10 个 `ssh_*` 工具、Mappings/Exclusions 配置面。  
- **尚未做完**：Mappings 未真正驱动同步；写操作无 Diff；凭据仍明文；别名未做。  
- **结论**：「有特色」成立；「成熟全栈产品」需完成 A1–A2、B1 才站得住。

## [S3] Out of Scope

- 本 Spec 不在本回合实现全部 A/B/C（只定方向）。  
- 不修改 Hermes 核心 / 不读用户密钥。  
- 不把未核实的「全网第一」写进 README 当营销话术。

## Tasks

- [ ] T1: 本方向文档入库 — acceptance: 文件存在且结构完整 (covers: S1/S2)
- [ ] T2:（待选）实现 A1 Host 别名 — acceptance: 工具/REST 默认掩码 host (covers: S2)
- [ ] T3:（待选）实现 A2 Dry-Run Diff — acceptance: write 支持 dryRun + Desktop 确认 (covers: S2)
- [ ] T4:（待选）实现 B1 Mappings 驱动上传 — acceptance: 本地路径可映射上传 (covers: S2)
