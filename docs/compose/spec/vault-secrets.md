---
feature: vault-secrets
status: in-progress
updated: 2026-09-16
branch: main
commits: pending
---

# vault 托管密钥（可选）

## Report

## [S1] Problem

HANDOFF 列 vault 为可选：SSH 口令/口令短语可不落 `deployments.json`，而在连接时从 hermes-vault 解析。

## [S2] Design

- 服务器字段 `password` / `passphrase` / `privateKeyContent` / `privateKey` 可写成 `hv://service` 或 `hv://service?alias=name`。
- `vault_secrets.resolve_server_secrets` 在 **连接时** 解析；明文只进内存，不回写 store、不进 audit（audit 只记 ref）。
- 钩子：`sftp_client.session_server` 与 `ssh_session.get_session`。
- 未安装 `hermes_vault` 时抛 `VaultRefError`（文案说明回退到 DPAPI 字面量）。
- `privateKey` 为 ref 时改为 inline `privateKeyContent` + `auth=key`。

## [S3] Out of Scope

- 不实现完整 vault 安装/轮换 UI
- 不强制依赖 hermes_vault
- 不改 Desktop 表单（可手工写入 hv:// 字符串）

## Tasks

- [ ] T1: vault_secrets + session 钩子 — acceptance: hv:// 在连接时解析
- [ ] T2: 单测 — acceptance: unittest 全绿
