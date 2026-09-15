---
feature: vault-secrets
status: delivered
updated: 2026-09-16
branch: main
commits: fb2fb5d..e139093
---

# vault 托管密钥（可选）

## Report

**What was built** — 服务器 `password` / `passphrase` / `privateKeyContent` / `privateKey` 支持写成 `hv://service` 或 `hv://service?alias=name`。连接时经 `vault_secrets.resolve_server_secrets` 调用 `hermes_vault.Vault.resolve_credential`；明文只进内存，audit 只记 ref。未安装 vault 包时抛出可读的 `VaultRefError`。`privateKey` 为 ref 时转为 inline key content。

**Verification** — `unittest discover` 51 PASS（含 parse / resolve / session_server 钩子 / 缺包错误）；`py_compile` 通过。

**Journey log**
- DPAPI 落盘的 `hv://` 字符串解密后仍是 ref，连接时再解析，无需改 store。
- 不要把解析结果写回 `deployments.json`。
- Desktop 表单可手填 `hv://…`，无需本轮改 UI。

## [S1] Problem

HANDOFF 列 vault 为可选：SSH 口令/口令短语可不落 `deployments.json`，而在连接时从 hermes-vault 解析。

## [S2] Design

- 服务器字段可写 `hv://service` 或 `hv://service?alias=name`。
- `vault_secrets.resolve_server_secrets` 在连接时解析；明文只进内存。
- 钩子：`sftp_client.session_server` 与 `ssh_session.get_session`。
- 未安装 `hermes_vault` 时抛 `VaultRefError`。

## [S3] Out of Scope

- 完整 vault 安装/轮换 UI；强制依赖；Desktop 表单改造。

## Tasks

- [x] T1: vault_secrets + session 钩子 — acceptance: hv:// 在连接时解析
- [x] T2: 单测 — acceptance: unittest 全绿
