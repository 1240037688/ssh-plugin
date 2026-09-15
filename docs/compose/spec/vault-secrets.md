---
feature: vault-secrets
status: delivered
updated: 2026-09-16
branch: main
commits: fb2fb5d..e139093
---

# vault 托管密钥（可选）

## Report

**What was built** — 服务器 `password` / `passphrase` / `privateKeyContent` / `privateKey` 支持写成 `hv://service` 或 `hv://service?alias=name`。**可选集成**：仅当环境中能 `import hermes_vault` 时在连接时解析；若未安装，**完全跳过 vault 路径**（`hv://` 字段清为 `None`，字面量凭据不受影响），**不会**因缺包导致连接失败。解析成功时 audit 只记 ref。

**Verification** — `unittest discover` 全绿；无 vault 时 `resolve_server_secrets` 不调用 `resolve_ref`、不抛错。

**Journey log**
- 可选依赖必须「有则用、无则跳过」，不能在缺包时抛错阻断 SSH。
- DPAPI 落盘的 `hv://` 解密后仍是 ref；无 vault 时按未配置口令处理。
- 不要把解析结果写回 `deployments.json`。

## [S1] Problem

HANDOFF 列 vault 为可选：SSH 口令/口令短语可不落 `deployments.json`，而在连接时从 hermes-vault 解析。

## [S2] Design

- 服务器字段可写 `hv://service` 或 `hv://service?alias=name`。
- `vault_secrets.resolve_server_secrets`：`vault_available()` 为真才解析；为假则跳过（ref 清空），不抛错。
- 钩子：`sftp_client.session_server` 与 `ssh_session.get_session`。

## [S3] Out of Scope

- 完整 vault 安装/轮换 UI；强制依赖；Desktop 表单改造。

## Tasks

- [x] T1: vault_secrets + session 钩子 — acceptance: hv:// 在连接时解析
- [x] T2: 单测 — acceptance: unittest 全绿
