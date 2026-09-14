---
feature: server-switch-fix
status: in-progress
updated: 2026-09-16
branch: fix/server-switch-freeze
commits: db952da..WIP
---

# 修复：双服务器切换卡死 + 切换卡片布局错误

## Report

## [S1] Problem

用户配置两台 SSH 服务器后：

1. **切换服务器会卡死**，界面报「后端未就绪 / runtime not ready」，连不上。  
   根因：`dashboard/plugin_api.py` 的 `async def` 端点内直接调用 **阻塞的 paramiko**（connect / SFTP / exec）。SSH 握手或半开连接探测会卡住 **整个 FastAPI 事件循环**，`/health` 与后续请求全部超时，Desktop 判定 runtime 不可用。  
   次要放大因素：`DeployPage` 同时挂在 `ROUTES_AREA` 与 `PANES_AREA`，`selected` 变化时两个实例各自 `resetTreeForServer()`，并发阻塞 SSH；`get_session` 每次操作前 `listdir(".")` 探测也会阻塞。

2. **顶栏切换小卡片布局错误**（截图中多个「tdh」叠在一起）。  
   根因：自定义 `absolute` 浮层写在 `flex-wrap` 顶栏内，仅设 `top: 48`、无 `left/right`，未使用 SDK 的 `DropdownMenu`（`hermes-vault-desktop` 已验证可用），也无外部点击关闭。

## [S2] Design

### 2.1 后端：阻塞 SSH 移出事件循环

- 在 `dashboard/plugin_api.py` 增加有界线程池 + `asyncio` 包装：
  ```python
  _EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="ssh-plugin")
  async def _ssh_call(fn, /, *args, **kwargs):
      loop = asyncio.get_running_loop()
      return await loop.run_in_executor(_EXECUTOR, lambda: fn(*args, **kwargs))
  ```
- 所有触碰 paramiko / 连接池的 REST 端点改为经 `_ssh_call` 调用同步实现：
  `fs_ls` / `fs_read` / `fs_preview` / `fs_write` / `fs_mkdir` / `fs_delete` / `fs_rename` / `fs_upload` / `fs_download` / `fs_sync` / `test_server` / `health_server`。
- 纯本地端点（`health`、`servers` 列表、`audit`、`conn/stats`）保持同步或轻量 async，不进线程池。
- 默认 `connectionTimeoutMs` 从 30s 降到 **10s**（`ssh_session.py`），避免坏主机长时间占住 worker；仍允许服务器配置覆盖。
- 连接池逻辑本身不改语义；线程池 + 每 server `RLock` 保证同一连接串行。

### 2.2 Desktop：切换 UI 与竞态

- **`ServerTopBar`**：删除自定义 absolute 浮层与 `openSwitch` state；改用 SDK：
  - `DropdownMenu` + `DropdownMenuTrigger`（当前服务器名按钮）+ `DropdownMenuContent` + `DropdownMenuItem`。
  - 每项：StatusDot + 显示名 + `user@host:port`（truncate），当前项高亮。
  - 点击项：`$selectedId.set(id)` 后由 effect 拉树；菜单由 SDK 自动关闭。
- **树加载竞态**：模块级 `treeEpoch`；`resetTreeForServer` / `loadTreeDir` 在 await 后校验 epoch，过期结果丢弃，避免快速切换时旧服务器目录覆盖新树。
- **双挂载**：`ROUTES_AREA` 与 `PANES_AREA` 共享 atom；树加载只由 `selected` 的 effect 触发一次（epoch 去重即可），不在点击处理器里再调 `resetTreeForServer`。
- 切换后立刻清空 `$openFile` / `$treeNodes`，显示 Skeleton，不阻塞交互。

### 2.3 测试边界

- 单测：线程池包装后 `fs_ls` 等仍返回原结构（mock `sftp_client.list_dir`）；`test_api_async_does_not_block` 可验证 handler 协程可被并发 await（用 mock 短 sleep 模拟阻塞 fn）。
- 不强制真机 SSH；参数校验与 store 行为沿用现有测试。
- Desktop 无自动化 UI 测试；以代码审查 + 本地预览为准。

## [S3] Out of Scope

- 不改 Agent tools 的同步调用路径（tools 在 gateway worker 线程执行，不占 uvicorn loop）。
- 不做 vault 托管密钥、不引入新 UI 组件库。
- 不重做整页布局；仅修切换浮层与相关竞态。
- 不修改 Hermes 核心。

## Tasks

- [ ] T1: API 线程池包装 + 默认连接超时 10s — acceptance: 所有 SSH REST 经 `_ssh_call`；`connectionTimeoutMs` 默认 10000；现有单测通过 (covers: S2.1)
- [ ] T2: 回归测试「阻塞 mock 不卡事件循环」— acceptance: 新测试在未包装时会失败/或直接测 `_ssh_call` 并发完成 (covers: S2.1; depends: T1)
- [ ] T3: ServerTopBar 改用 DropdownMenu + 树 epoch 竞态 — acceptance: 无 custom absolute 浮层；切换仅改 selectedId；旧树结果被丢弃 (covers: S2.2)
- [ ] T4: 同步安装到 Hermes 目录并本地跑测试 — acceptance: `python -m pytest tests -q` 全绿；`desktop/plugin.js` 与 `plugins/ssh-plugin` 一致 (covers: S2.3; depends: T1,T3)
