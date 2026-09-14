---
feature: gui-file-tree
status: designed
updated: 2026-09-14
branch: main
commits: pending
---

# GUI 改进：IDE 式文件树 + 服务器栏收纳

## Report

## [S1] Problem

当前 SSH 部署页交互不符合日常远程开发习惯：

1. **文件列表是「单层目录」**  
   只显示当前目录下一层条目；要看到上一级/兄弟目录必须点「上一级」再换目录，**没有**像 VS Code / PyCharm Remote Host 那样的**缩进树**：`/` → `data` → `data1` 同时可见，用 `>` 展开子目录。

2. **左侧服务器栏常驻占宽**  
   配置完服务器后列表栏仍一直占位；用户希望：
   - 能**收起**服务器栏，或  
   - 改成**顶部一条**显示当前服务器信息，用「添加/编辑」按钮打开填写对话框。

截图参考：典型 IDE 文件树——顶层 `cdrom` / `data` / `dev`，`dev` 展开后内嵌 `block`、`bus`…，带 `>` 箭头。

## [S2] Design

### 2.1 可折叠文件树（对标截图）

**目标形态**

```text
> /                    (或从 / 开始)
  > data
  > data1
  v dev                ← 已展开
      > block
      > bsg
      > bus
      …
  > etc
```

**行为**

| 交互 | 行为 |
|------|------|
| 点击目录名 | 切换展开/折叠；首次展开时懒加载 `ls` |
| 点击 `>` / 文件 | 目录切换展开；文件仍打开编辑器/预览 |
| 已展开路径 | 保存在组件 state（可选 `ctx.storage` 记住上次） |
| 面包屑 / 上一级 | 可保留；树内点目录不再强制「换 cwd 只显示一层」 |
| 选中文件 | 高亮路径；与右侧编辑器联动不变 |
| 新建/删除/重命名 | 刷新所在父节点的子列表 |

**实现要点（Desktop `plugin.js`）**

- 用 `expanded: Set<path>` + `treeCache: Map<path, entries[]>` 替代单一 `$cwd + $entries`。  
- 根节点可从 `/` 或 mapping 的 remoteRoot 开始。  
- 目录行：chevron（`>` / `v`）+ 文件夹图标 + 名称；缩进 `paddingLeft = depth * 12`。  
- 文件行：文件/图片图标 + 名称 + size。  
- 仍走现有 `ctx.rest('/fs/ls?id=&path=')`，**后端不必改**（可选后续加 `GET /fs/tree?depth=` 减请求）。  
- 约束不变：无 JSX、仅 SDK import、`var(--ui-*)`。

### 2.2 服务器栏收纳 + 顶栏信息

**目标布局**

```text
┌──────────────────────────────────────────────┐
│ [● prod]  user@***:22   [编辑] [+] [测试]  ⌄ │  ← 顶栏：当前服务器摘要
├──────────────────────────────────────────────┤
│ 文件树（IDE）                    │ 编辑器     │
└──────────────────────────────────────────────┘
```

| 元素 | 行为 |
|------|------|
| 顶栏 | 状态点、显示名、掩码后的 host/port（Agent 侧已掩码；桌面顶栏可显示真实 host 给操作者）、默认服务器标记 |
| `+` 添加 | 打开现有 ServerDialog（新建） |
| 编辑 | 打开 ServerDialog（当前服务器） |
| 测试 | `POST /servers/{id}/test` |
| `⌄` / 切换 | 打开服务器下拉，可切换当前服务器；可选「显示侧栏列表」展开旧列表 |
| 默认布局 | **不显示**左侧常驻服务器栏；设置里可「显示服务器侧栏」 |

**实现要点**

- `$showServerSidebar` 默认 `false`；顶栏 `DropdownMenu` 或 `Dialog` 列表切换。  
- 复用现有 `ServerList` 组件为可选面板。  
- 空服务器时顶栏仍显示「添加服务器」主按钮。

### 2.3 不在本次范围

- 本地文件树  
- 拖拽上传  
- 后端 tree API（可选增强）  
- 移动端布局

## [S3] Out of Scope

- 不改 SSH 协议/加密/审计  
- 不重写 Agent 工具  
- 不做 VS Code 插件形态

## 可直接粘贴的提示词（给实现 Agent）

```text
【任务】改进 Hermes ssh-plugin 的 Desktop UI（desktop/plugin.js，无 JSX，仅 @hermes/plugin-sdk / react / react/jsx-runtime）

【问题】
1) 文件区只有单层 ls，没有 IDE 式嵌套树。
2) 左侧服务器列表常驻占宽，应改为顶栏摘要 + 添加按钮。

【需求 A：文件树】
- 树形展示远程目录：顶层同时可见，目录用 > 展开/折叠，子级缩进（参考截图：/、data、dev 展开后 block/bsg/…）。
- 懒加载：首次展开某目录时调用 ctx.rest('/fs/ls?id=&path=')，缓存 children。
- 点击文件：逻辑与现有一致（读/预览/编辑）。
- 新建/删除/重命名后刷新父节点。
- 保留或简化面包屑/上一级均可，但树内导航为主。
- 仅用 var(--ui-*) 主题变量；禁止硬编码颜色；禁止 JSX 语法。

【需求 B：服务器栏】
- 默认隐藏左侧服务器栏。
- 顶部工具条：当前服务器（名称、状态、host 摘要）、切换下拉、编辑、测试连接、添加（+）按钮打开 ServerDialog。
- 可选：设置/按钮「显示服务器侧栏」恢复旧列表。

【验收】
- node --check desktop/plugin.js 通过。
- 安装到 HERMES_HOME 后：能从 / 展开多级目录；默认无左侧服务器栏；+ 能新建服务器。
- 不修改 plugin 后端路径契约（仍用 /fs/ls 等）。

【约束】
- 不读取用户 deployments.json 密钥内容。
- 不改 Hermes 核心。
```

## Tasks

- [ ] T1: 实现懒加载折叠文件树 — acceptance: 多级目录同屏可见、可展开折叠 (covers: S2.1)
- [ ] T2: 顶栏服务器摘要 + 收起侧栏 — acceptance: 默认无常驻侧栏，+/编辑/测试可用 (covers: S2.2)
- [ ] T3: node --check + 同步安装目录 + commit — acceptance: 静态检查通过并提交 (covers: S2)
