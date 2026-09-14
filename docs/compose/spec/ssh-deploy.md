---
feature: ssh-deploy
status: delivered
updated: 2026-09-14
branch: feature/ssh-deploy
commits: 8a07fb9..HEAD
---

# SSH Deploy（可视化 SSH 部署与文件管理）

## Report

**What was built** — Hermes 统一包 `ssh-plugin`：对标 PyCharm Deployment 的可视化 SSH/SFTP 管理。Desktop 半边提供路由 `/ssh-deploy` 三栏 UI（服务器 / 远程文件树 / 编辑与图片预览），并含 Connection + Mappings/Exclusions 配置；Python 半边经 `paramiko` 暴露 `/api/plugins/ssh-plugin/*` 与 9 个 Agent 工具（`ssh_*`）。另附 `preview/index.html` 离线 mock 便于浏览器验收。

**Verification** — `node --check desktop/plugin.js` PASS；`node --check preview/app.js` PASS；`MIMO_PYTHON -m py_compile` 全部 py PASS；路径安全 / 排除 glob / 密码保留单测 PASS。未在本机 Hermes 内做真实 SSH 联调（无目标机）。

**Journey log**
- 统一包桌面半边默认 opt-in，安装后需在 Capabilities 打开。
- 密码字段 UI 传空表示「保留原密」；仅非空覆盖。
- `dir/**` 排除同时隐藏目录本身。
- rename API 接受 `src/dst` 与 `from/to` 双别名。

## [S1] Problem

Hermes 用户需要在桌面里可视化管理远程服务器文件：连接、浏览目录、创建/编辑/删除文件、上传下载，并参考 PyCharm Deployment 的 Connection / Mappings / Excluded Paths 模型配置部署映射。`ssh-mcp-server` 已提供 MCP 工具面（execute-command / upload / download / list-servers），但没有桌面可视化 UI；本插件以 Hermes **统一包**形式补齐可视化层，并复用同类能力（SFTP 文件操作 + 连接配置）。

## [S2] Design

### 包形态

统一包，安装目录（开发根 `E:\hermes_plugin\ssh\ssh-plugin`）：

```
ssh-plugin/                    # 插件 id = ssh-plugin
├── plugin.yaml                # Agent 半边清单
├── __init__.py                # register(ctx)：工具 + 可选 skill
├── schemas.py                 # LLM 工具 schema
├── tools.py                   # SFTP/SSH 处理器
├── sftp_client.py             # paramiko 封装 + 连接配置
├── deployment_store.py        # 服务器/映射/排除路径持久化
├── dashboard/
│   ├── manifest.json
│   └── plugin_api.py          # /api/plugins/ssh-plugin/*
├── desktop/
│   └── plugin.js              # Desktop 可视化 UI（无构建、无 JSX）
├── preview/
│   ├── index.html             # 浏览器可交互 UI 预览（mock 后端）
│   ├── app.css
│   └── app.js
├── skills/ssh-deploy/SKILL.md
└── docs/compose/spec/ssh-deploy.md
```

### 概念模型（对标 PyCharm Deployment）

| PyCharm | 本插件 |
|---------|--------|
| Server access configuration | Server：`id, name, host, port, username, auth(password\|key\|agent), privateKey, passphrase` |
| Connection tab | 连接参数 + Test Connection |
| Mappings tab | Mapping：`localRoot, remoteRoot`（每服务器可多条） |
| Excluded Paths | Exclusions：glob 列表（如 `.git/**`, `node_modules/**`） |
| Automatic upload | 桌面保存文件时可选「保存后上传」（v1 手动 + 单文件上传按钮；映射供批量后续） |
| Remote host 工具窗口 | Desktop 路由页 `/ssh-deploy` + 侧栏入口 |

凭据只存 gateway 侧 `deployment_store`（`HERMES_HOME` 插件数据目录），**不进** `ctx.storage`、不进 git、不回传明文到 UI（UI 只提交，不读回 password）。

### Desktop UI（`desktop/plugin.js`）

- `id: 'ssh-plugin'`（与文件夹一致）
- 贡献：
  - `ROUTES_AREA` path `/ssh-deploy`：主工作区全页
  - `SIDEBAR_NAV_AREA`：label「SSH 部署」，codicon `remote`
  - `PALETTE_AREA`：`SSH 部署: 打开`
  - `STATUSBAR_AREAS.right`：当前连接状态胶囊（可选）
- 页面结构（三栏，仿 IDE Remote Host）：
  1. **左：服务器列表** — 添加/编辑/测试连接/设为默认
  2. **中：远程文件树** — 面包屑、刷新、新建文件/文件夹、重命名、删除、双击进入
  3. **右：编辑器/预览** — 文本编辑 + 保存；图片（png/jpg/gif/webp/svg）本地 data URL 预览；二进制只读元信息
- **Mappings / Exclusions** 在服务器编辑对话框（PyCharm 三 Tab 简化为一组表单）
- 数据：一律 `ctx.rest('/…')`；socket 作可选增强，失败则轮询/手动刷新
- UI 组件：`Button, Input, Textarea, Dialog*, Badge, EmptyState, ScrollArea, Separator, Skeleton, StatusDot, icons.*`
- 样式：仅 `var(--ui-*)`，禁止硬编码色
- 写法：`jsx()/jsxs()`，仅 import `@hermes/plugin-sdk` / `react` / `react/jsx-runtime`

### Backend API（`dashboard/plugin_api.py` → `/api/plugins/ssh-plugin/`）

| Method | Path | 说明 |
|--------|------|------|
| GET | `/servers` | 列表（无密码） |
| POST | `/servers` | 新建/更新 |
| DELETE | `/servers/{id}` | 删除 |
| POST | `/servers/{id}/test` | 测试连接，返回可达性/主机名 |
| GET | `/fs/ls?id=&path=` | 列目录 |
| GET | `/fs/read?id=&path=` | 读文本（超限截断） |
| GET | `/fs/download?id=&path=` | 下载二进制 |
| GET | `/fs/preview?id=&path=` | 图片预览（限大小） |
| POST | `/fs/write` | `{id, path, content}` 创建/覆盖 |
| POST | `/fs/mkdir` | `{id, path}` |
| POST | `/fs/rename` | `{id, src, dst}`（兼容别名 `from`/`to`） |
| POST | `/fs/delete` | `{id, path, recursive?}` |
| POST | `/fs/upload` | `{id, path\|remotePath, contentBase64}` |
| GET | `/mappings?id=` | 映射列表 |
| PUT | `/mappings` | 整表替换该服务器 mappings+exclusions |

实现：`paramiko`（依赖缺失时返回明确错误 JSON）。路径规范化，拒绝 `..` 穿越；按服务器 `allowedRemotePaths`（可选配置）做前缀约束。

### Agent 工具（Python 半边）

| 工具 | 参数 | 作用 |
|------|------|------|
| `ssh_list_servers` | — | 列出配置名/主机 |
| `ssh_ls` | server, path | 列目录 |
| `ssh_read_file` | server, path | 读文本 |
| `ssh_write_file` | server, path, content | 写文件 |
| `ssh_mkdir` | server, path | 建目录 |
| `ssh_delete` | server, path, recursive? | 删除 |
| `ssh_exec` | server, command | 远程命令（默认关闭，需 `allow_exec`） |
| `ssh_upload` / `ssh_download` | … | 与 ssh-mcp-server 工具对齐 |

Handler 签名 `def f(args: dict, **kwargs) -> str`，始终返回 JSON 字符串。

### 配置存储

`deployment_store.py`：`<HERMES_HOME>/plugin-data/ssh-plugin/deployments.json`

```json
{
  "servers": [
    {
      "id": "srv_1",
      "name": "prod",
      "host": "1.2.3.4",
      "port": 22,
      "username": "root",
      "auth": "password",
      "password": "…",
      "privateKey": null,
      "passphrase": null,
      "mappings": [{ "localRoot": "E:/proj", "remoteRoot": "/var/www" }],
      "exclusions": [".git/**", "node_modules/**"],
      "allowedRemotePaths": ["/var/www"],
      "allow_exec": false
    }
  ],
  "defaultServerId": "srv_1"
}
```

### 安全边界

- 密钥/密码仅在 gateway 进程内使用；REST 响应剥离 secret
- 默认 `allow_exec: false`，Agent 不暴露任意 shell，除非用户显式打开
- SFTP 路径 canonicalize；可选 `allowedRemotePaths` 白名单
- 上传大小上限（默认 20MB preview / 50MB write）

### 验证边界

- 静态：`node --check desktop/plugin.js`；`python -m py_compile` 全部 py
- 浏览器：`preview/index.html` 可离线打开完成 mock 交互（列表→进入目录→编辑→保存 toast）
- 运行时：需本机 Hermes 启用 `ssh-plugin`（`plugins.enabled` + Capabilities 开关）；无真实服务器时至少 `/servers` 与错误路径可用

## [S3] Out of Scope

- 真实 SSH 隧道/跳板机链、Socks 代理完整实现（v1 仅直连 host:port）
- 文件同步 diff、双向 watch、自动上传监听文件系统
- FTP/SFTP 多协议（仅 SSH/SFTP）
- 修改 `ssh-mcp-server` 本体（只读参考）
- Web Dashboard 额外 Tab（统一包已含 `plugin_api`，Dashboard UI 不做）

## Tasks

- [x] T1: 脚手架 + plugin.yaml + deployment_store + sftp_client — acceptance: 模块可 import，配置读写往返正确 (covers: S2)
- [x] T2: plugin_api.py 全部 REST 路由 — acceptance: 路由齐全，错误为 JSON，无 secret 泄漏 (covers: S2; depends: T1)
- [x] T3: Agent 工具 schemas + tools + register — acceptance: 工具名与 handler 一一对应，返回 JSON 字符串 (covers: S2; depends: T1)
- [x] T4: desktop/plugin.js 可视化三栏 UI — acceptance: 无 JSX、仅允许 import、theme vars、调用 ctx.rest (covers: S2; depends: T2)
- [x] T5: preview/index.html 交互预览 — acceptance: 浏览器打开可走通 mock 流程 (covers: S2)
- [x] T6: SKILL.md + README + 静态校验 — acceptance: node --check 与 py_compile 通过 (covers: S2)
