---
feature: plugin-compliance
status: designed
updated: 2026-09-14
branch: feature/ssh-deploy
commits: pending
---

# 对照 hermes-vault 的规范审计与缺口修复

## Report

## [S1] Problem

用户要求：理解「用 hermes-vault 作模板」的需求 → 下载模板 → 分析工作流与编码规范 → 指出当前 `ssh-plugin` 的遗漏/错误。

**需求整理（可执行表述）**

1. 以 `https://github.com/asimons81/hermes-vault` 为 Hermes 插件工程规范样板（不是业务依赖）。  
2. 只读学习其：目录拆分、Desktop 插件写法、`dashboard/plugin_api.py` 安全模型、manifest、测试与安装文档。  
3. 输出差距清单，并修掉不改架构也能对齐的项；架构级差异（如密钥加密 vault）记为 out of scope。

## [S2] Design

### 模板学到的工作流（hermes-vault）

| 维度 | vault 做法 | 对我们的含义 |
|------|------------|--------------|
| 包拆分 | `hermes-vault-desktop`（UI+API）与 `hermes-vault-secret-source`（Agent）**分仓库目录** | 统一包合法，但桌面/后端/Agent 边界仍要清晰 |
| Desktop | `useQuery`/`queryClient`、`ConfirmDialog`、`ErrorState`、`Codicon`、超时常量、scoped CSS polyfill | 避免 `window.confirm`；UI 更接近 SDK 组件 |
| Backend | 模块 docstring 写清安全模型；Host 头校验；失败封闭；无密钥回传；mutation 默认关 | 补 Host 校验与错误信封；路径/mutation 策略写进文档 |
| manifest | `label/description/icon/version/api` | 补全 `dashboard/manifest.json` |
| 测试 | `plugins/*/tests/` pytest | 补最小单测目录 |
| 安装 | README 明确 copy 到 `plugins/` 与 `desktop-plugins/`、enable 列表 | README 对齐本机路径 |
| 密钥 | AES 落盘、不进日志 | 我们仍明文 `deployments.json`（已知风险，不在本任务加密） |

### 差距分级

**P0 已修（本任务）**

1. `manifest.json` 补 label/description/icon/version。  
2. `plugin_api.py`：Host 头 loopback 校验（对齐 vault R1）；统一错误 JSON。  
3. Desktop：删除 `window.confirm`，改用 `ConfirmDialog`。  
4. 增加 `tests/`：deployment_store 路径/密钥保留、security 白名单、ssh_session 池复用。  
5. README 增加「规范对照」与安装校验清单。

**P1 记录不修（架构）**

- 凭据改走 hermes-vault 加密 / secret-source（需另一设计）。  
- 子进程 bridge 替代 in-process paramiko。  
- 与 ssh-mcp-server 双栈统一。

### 本机安装注意

- 真实插件根：`D:\hermes\plugins\ssh-plugin`（Junction `%LOCALAPPDATA%\hermes\plugins`）。  
- 参考模板只读：`E:\hermes_plugin\refs\hermes-vault`，**不要**装进 Hermes。  
- 不读取用户服务器密钥文件。

## [S3] Out of Scope

- 把 SSH 密码迁入 hermes-vault。  
- 改 Hermes 核心 / vault 源码。  
- 重写 Desktop 为全套 useQuery（仅修 confirm 等明显不规范点）。

## Tasks

- [ ] T1: 写本审计 Spec — acceptance: 需求整理 + 差距表完整 (covers: S1/S2)
- [ ] T2: 修 P0 代码/manifest/README — acceptance: 文件变更可编译 (covers: S2)
- [ ] T3: tests + 跑通 — acceptance: pytest 或 _test 脚本 PASS (covers: S2)
- [ ] T4: 同步 D:\hermes\plugins 并 commit — acceptance: git 提交 (covers: S2)
