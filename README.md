# ssh-plugin — Hermes SSH Deploy

统一包插件：可视化 SSH/SFTP 文件管理 + PyCharm Deployment 风格配置。

## 功能

- **Desktop**：路由 `/ssh-deploy`（侧栏「SSH 部署」）。服务器列表、远程目录浏览、新建/删除/重命名、文本编辑保存、图片预览、连接测试、Mappings/Exclusions。
- **Backend**：`dashboard/plugin_api.py` 挂载到 `/api/plugins/ssh-plugin/`。
- **Agent 工具**：`ssh_list_servers` / `ssh_ls` / `ssh_read_file` / `ssh_write_file` / `ssh_mkdir` / `ssh_delete` / `ssh_upload` / `ssh_download` / `ssh_exec`。

## 安装（开发机）

1. 复制本目录到 Hermes 插件根：

```powershell
Copy-Item -Recurse -Force E:\hermes_plugin\ssh\ssh-plugin $env:USERPROFILE\.hermes\plugins\ssh-plugin
```

2. 在 `~/.hermes/config.yaml` 启用 Python 半边：

```yaml
plugins:
  enabled:
    - ssh-plugin
```

3. 重启 Hermes gateway。Desktop 侧在 **Capabilities → Plugins** 打开 `ssh-plugin`（统一包默认关闭）。

4. 依赖：gateway 环境需 `paramiko`：

```powershell
# 使用 Hermes 自带 venv 时
& "$env:LOCALAPPDATA\hermes\hermes-agent\venv\Scripts\python.exe" -m pip install paramiko
```

## 配置数据

`~/.hermes/plugin-data/ssh-plugin/deployments.json`（由 UI 写入，含密码/私钥路径，勿提交 git）。

## 浏览器预览（无 Hermes）

打开 `preview/index.html` 可离线体验 UI（mock 文件系统，不连真实 SSH）。

## 开发源

本仓库为开发根：`E:\hermes_plugin\ssh\ssh-plugin`。设计见 `docs/compose/spec/ssh-deploy.md`。参考能力来源：`../ssh-mcp-server`（只读）。
