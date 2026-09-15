/**
 * ssh-plugin — Hermes desktop UI: PyCharm-style SSH deployment & remote files.
 *
 * Disk plugin constraints:
 *   - No JSX syntax; use jsx()/jsxs() only.
 *   - Imports limited to @hermes/plugin-sdk, react, react/jsx-runtime.
 *   - Theme via var(--ui-*); secrets never rendered.
 *   - All remote I/O through ctx.rest('/…') → /api/plugins/ssh-plugin/.
 */
import {
  atom,
  host,
  useValue,
  Button,
  Input,
  Textarea,
  Badge,
  EmptyState,
  ScrollArea,
  Separator,
  Skeleton,
  StatusDot,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  ConfirmDialog,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  icons,
  PANES_AREA,
  ROUTES_AREA,
  SIDEBAR_NAV_AREA,
  PALETTE_AREA,
  STATUSBAR_AREAS
} from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'
import { useEffect, useState } from 'react'

const ID = 'ssh-plugin'
const ROUTE = '/ssh-deploy'

// ── i18n ─────────────────────────────────────────────────────────────────────
const LOCALES = {
  zh: {
    nav: 'SSH 部署',
    pane: 'SSH 部署',
    title: 'SSH 部署',
    subtitle: '可视化远程文件 · 对标 PyCharm Deployment',
    servers: '服务器',
    addServer: '添加服务器',
    editServer: '编辑服务器',
    showSidebar: '显示侧栏',
    hideSidebar: '隐藏侧栏',
    remoteFiles: '远程文件',
    rename: '重命名',
    test: '测试连接',
    testing: '测试中…',
    setDefault: '设为默认',
    delete: '删除',
    refresh: '刷新',
    newFile: '新建文件',
    newFolder: '新建目录',
    breadcrumb: '路径',
    up: '上一级',
    editor: '编辑器',
    preview: '预览',
    save: '保存',
    saveUpload: '保存',
    saving: '保存中…',
    noServer: '还没有服务器',
    noServerHint: '点「添加服务器」配置 SSH 连接（主机/用户/密码或私钥）',
    noFile: '选择左侧文件进行编辑或预览',
    emptyDir: '空目录',
    type: '类型',
    size: '大小',
    mtime: '修改时间',
    dir: '目录',
    file: '文件',
    cancel: '取消',
    ok: '确定',
    create: '创建',
    name: '名称',
    fileName: '文件名',
    folderName: '目录名',
    host: '主机',
    port: '端口',
    username: '用户名',
    auth: '认证方式',
    password: '密码',
    privateKey: '私钥路径',
    passphrase: '私钥口令',
    serverName: '显示名称',
    mappings: '路径映射 (local ↔ remote)',
    exclusions: '排除模式 (glob, 每行一条)',
    allowedPaths: '允许的远程路径前缀 (可选)',
    allowedLocal: '允许的本地路径 (上传/下载, 可选, 每行一条)',
    whitelist: '命令白名单正则 (每行一条, 全匹配)',
    blacklist: '命令黑名单正则 (每行一条)',
    allowExec: '允许 ssh_exec 命令',
    connection: '连接',
    mappingTab: '映射 / 排除',
    localRoot: '本地根目录',
    remoteRoot: '远程根目录',
    addMapping: '添加映射',
    remove: '移除',
    statusOnline: '后端可用',
    statusOffline: '后端未就绪',
    backendHint: '需在 config.yaml 启用 plugins entries ssh-plugin 并重启 gateway',
    confirmDeleteFile: '确认删除该路径？',
    confirmDeleteServer: '确认删除该服务器？',
    notFound: '未找到',
    error: '错误',
    open: '打开',
    download: '下载',
    imageUnsupported: '不支持的图片或文件过大',
    textTooLarge: '文件过大，仅显示前缀',
    enterPath: '输入远程绝对路径',
    placeholderHost: '例如 192.168.1.10',
    placeholderUser: 'root',
    placeholderPass: '仅保存在 gateway 本地，或 hv://service[?alias=]',
    placeholderKey: '~/.ssh/id_rsa 或 hv://service',
    vaultHint: '可选：填 hv://service[?alias=]（需本机安装 hermes_vault；未安装则忽略该引用）',
    placeholderLocal: 'E:/project',
    placeholderRemote: '/var/www/html',
    saved: '已保存',
    pendingWrite: '确认写入远端？',
    pendingWriteDesc: '将覆盖远端文件。请检查 diff：',
    writeStats: '+{added} / -{removed}',
    created: '已创建',
    deleted: '已删除',
    renamed: '已重命名',
    testOk: '连接成功',
    testFail: '连接失败',
    operations: '同步 / 审计', previewSync: '预览同步', confirmSync: '确认批量上传？',
    syncNow: '执行同步', auditRefresh: '刷新审计', syncLocalRoot: '本地根目录（留空使用首条映射）',
    syncResult: '待上传 {count} 个文件', auditEmpty: '暂无审计记录'
  },
  en: {
    nav: 'SSH Deploy',
    pane: 'SSH Deploy',
    title: 'SSH Deploy',
    subtitle: 'Visual remote files · PyCharm Deployment-style',
    servers: 'Servers',
    addServer: 'Add server',
    editServer: 'Edit server',
    showSidebar: 'Show sidebar',
    hideSidebar: 'Hide sidebar',
    remoteFiles: 'Remote files',
    rename: 'Rename',
    test: 'Test',
    testing: 'Testing…',
    setDefault: 'Set default',
    delete: 'Delete',
    refresh: 'Refresh',
    newFile: 'New file',
    newFolder: 'New folder',
    breadcrumb: 'Path',
    up: 'Up',
    editor: 'Editor',
    preview: 'Preview',
    save: 'Save',
    saveUpload: 'Save',
    saving: 'Saving…',
    noServer: 'No servers yet',
    noServerHint: 'Click Add server to configure SSH (host / user / password or key)',
    noFile: 'Select a file on the left to edit or preview',
    emptyDir: 'Empty directory',
    type: 'Type',
    size: 'Size',
    mtime: 'Modified',
    dir: 'Dir',
    file: 'File',
    cancel: 'Cancel',
    ok: 'OK',
    create: 'Create',
    name: 'Name',
    fileName: 'File name',
    folderName: 'Folder name',
    host: 'Host',
    port: 'Port',
    username: 'Username',
    auth: 'Auth',
    password: 'Password',
    privateKey: 'Private key path',
    passphrase: 'Key passphrase',
    serverName: 'Display name',
    mappings: 'Mappings (local ↔ remote)',
    exclusions: 'Exclusions (one glob per line)',
    allowedPaths: 'Allowed remote prefixes (optional)',
    allowedLocal: 'Allowed local paths for upload/download (optional, one per line)',
    whitelist: 'Command whitelist regexes (one per line, full match)',
    blacklist: 'Command blacklist regexes (one per line)',
    allowExec: 'Allow ssh_exec',
    connection: 'Connection',
    mappingTab: 'Mappings / Excluded',
    localRoot: 'Local root',
    remoteRoot: 'Remote root',
    addMapping: 'Add mapping',
    remove: 'Remove',
    statusOnline: 'Backend ready',
    statusOffline: 'Backend not ready',
    backendHint: 'Enable plugins entries ssh-plugin in config.yaml and restart the gateway',
    confirmDeleteFile: 'Delete this path?',
    confirmDeleteServer: 'Delete this server?',
    notFound: 'Not found',
    error: 'Error',
    open: 'Open',
    download: 'Download',
    imageUnsupported: 'Unsupported image or too large',
    textTooLarge: 'File too large — showing prefix',
    enterPath: 'Absolute remote path',
    placeholderHost: 'e.g. 192.168.1.10',
    placeholderUser: 'root',
    placeholderPass: 'Stored on gateway only, or hv://service[?alias=]',
    placeholderKey: '~/.ssh/id_rsa or hv://service',
    vaultHint: 'Optional: hv://service[?alias=] if hermes_vault is installed; otherwise the ref is ignored',
    placeholderLocal: 'E:/project',
    placeholderRemote: '/var/www/html',
    saved: 'Saved',
    pendingWrite: 'Write to remote?',
    pendingWriteDesc: 'This overwrites the remote file. Review the diff:',
    writeStats: '+{added} / -{removed}',
    created: 'Created',
    deleted: 'Deleted',
    renamed: 'Renamed',
    testOk: 'Connected',
    testFail: 'Connection failed',
    operations: 'Sync / Audit', previewSync: 'Preview sync', confirmSync: 'Upload these files?',
    syncNow: 'Run sync', auditRefresh: 'Refresh audit', syncLocalRoot: 'Local root (blank: first mapping)',
    syncResult: '{count} files to upload', auditEmpty: 'No audit entries'
  }
}

const $servers = atom([])
const $defaultId = atom(null)
const $selectedId = atom(null)
const $openFile = atom(null) // { path, content, truncated, kind: 'text'|'image'|'binary', dataUrl? }
const $backendOk = atom(null)
const $editorDirty = atom(false)
const $pendingWrite = atom(null) // { id, path, content, diff, addedLines, removedLines, identical, emptyRemote }
// IDE tree state (object maps so useValue re-renders on replace)
const $expanded = atom({}) // path -> true
const $treeNodes = atom({}) // path -> entries[]
const $treeLoading = atom({}) // path -> true
const $showServerSidebar = atom(false)
const $createParent = atom('/')
// Bumped on every server switch; in-flight tree responses from an older epoch are dropped.
let treeEpoch = 0
// Pending server deletion ({ id, name }) — DeployPage owns the ConfirmDialog.
const $confirmDeleteServer = atom(null)
// Dual-mount (route + pane) each run a selected-effect; only the first loads the tree.
let treeLoadedFor = null
let bootstrapped = false

function tOf(locale, key) {
  const dict = LOCALES[locale] || LOCALES.zh
  const fallback = LOCALES.zh
  return dict[key] ?? fallback[key] ?? key
}

async function rest(path, opts) {
  try {
    return await ctxRest(path, opts)
  } catch (e) {
    throw e
  }
}

// Injected at register time
let ctxRest = async () => {
  throw new Error('ctx not ready')
}

function notify(kind, message) {
  host.notify({ kind, message })
}

function joinPath(dir, name) {
  if (!dir || dir === '/') return '/' + name
  return dir.replace(/\/+$/, '') + '/' + name
}

function parentOf(p) {
  if (!p || p === '/') return '/'
  const i = p.lastIndexOf('/')
  if (i <= 0) return '/'
  return p.slice(0, i) || '/'
}

function crumbs(p) {
  const parts = (p || '/').split('/').filter(Boolean)
  const out = [{ label: '/', path: '/' }]
  let cur = ''
  for (const part of parts) {
    cur += '/' + part
    out.push({ label: part, path: cur })
  }
  return out
}

function isImagePath(path) {
  return /\.(png|jpe?g|gif|webp|bmp|svg|ico)$/i.test(path || '')
}

function isLikelyText(path) {
  return /\.(txt|md|json|ya?ml|toml|ini|cfg|conf|py|js|ts|tsx|jsx|css|html?|xml|sh|env|log|csv|go|rs|java|c|h|cpp|sql)$/i.test(
    path || ''
  )
}

function fmtSize(n) {
  if (n == null) return '—'
  if (n < 1024) return n + ' B'
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB'
  if (n < 1024 * 1024 * 1024) return (n / 1024 / 1024).toFixed(1) + ' MB'
  return (n / 1024 / 1024 / 1024).toFixed(2) + ' GB'
}

async function probeBackend() {
  try {
    const r = await ctxRest('/health')
    $backendOk.set(!!(r && r.ok))
  } catch {
    $backendOk.set(false)
  }
}

async function loadServers() {
  try {
    const r = await ctxRest('/servers')
    $servers.set(r?.servers || [])
    $defaultId.set(r?.defaultServerId || null)
    const sel = $selectedId.get()
    const list = r?.servers || []
    if (!list.find(s => s.id === sel)) {
      $selectedId.set(r?.defaultServerId || list[0]?.id || null)
    }
    $backendOk.set(true)
  } catch (e) {
    $backendOk.set(false)
  }
}

async function deleteServerById(id) {
  if (!id) return
  await ctxRest('/servers/' + encodeURIComponent(id), { method: 'DELETE' })
  if ($pendingWrite.get()?.id === id) $pendingWrite.set(null)
  notify('success', tOf(localeCache, 'deleted'))
  if ($selectedId.get() === id) {
    treeLoadedFor = null
    treeEpoch += 1
    $selectedId.set(null)
    $openFile.set(null)
    $treeNodes.set({})
    $treeLoading.set({})
    $expanded.set({})
    $editorDirty.set(false)
  }
  await loadServers()
}

async function ensureTreeForSelected(selected) {
  if (!selected) {
    treeLoadedFor = null
    return
  }
  if (treeLoadedFor === selected) return
  // Claim before await so the sibling DeployPage mount cannot double-fetch.
  treeLoadedFor = selected
  try {
    await resetTreeForServer()
  } catch (e) {
    if (treeLoadedFor === selected) treeLoadedFor = null
    throw e
  }
}

async function loadTreeDir(path) {
  const id = $selectedId.get()
  if (!id) return false
  const epoch = treeEpoch
  $treeLoading.set({ ...$treeLoading.get(), [path]: true })
  try {
    const r = await ctxRest(
      '/fs/ls?id=' + encodeURIComponent(id) + '&path=' + encodeURIComponent(path)
    )
    if (epoch !== treeEpoch) return false
    $treeNodes.set({ ...$treeNodes.get(), [path]: r?.entries || [] })
    return true
  } catch (e) {
    if (epoch === treeEpoch) notify('error', String(e?.message || e))
    return false
  } finally {
    if (epoch === treeEpoch) {
      const l = { ...$treeLoading.get() }
      delete l[path]
      $treeLoading.set(l)
    }
  }
}

async function toggleDir(path) {
  const exp = { ...$expanded.get() }
  if (exp[path]) {
    delete exp[path]
    $expanded.set(exp)
    return
  }
  exp[path] = true
  $expanded.set(exp)
  if (!$treeNodes.get()[path]) await loadTreeDir(path)
}

async function resetTreeForServer() {
  const selected = $selectedId.get()
  treeLoadedFor = selected
  treeEpoch += 1
  $expanded.set({ '/': true })
  $treeNodes.set({})
  $treeLoading.set({})
  $openFile.set(null)
  $editorDirty.set(false)
  const ok = await loadTreeDir('/')
  // Allow remount/pane to retry after a failed load.
  if (!ok && treeLoadedFor === selected) treeLoadedFor = null
  return ok
}

async function refreshTreePath(path) {
  const parent = parentOf(path)
  await loadTreeDir(parent || '/')
}

async function openEntry(entry) {
  const id = $selectedId.get()
  if (!id || !entry) return
  if (entry.type === 'dir') {
    await toggleDir(entry.path)
    return
  }
  const epoch = treeEpoch
  try {
    if (entry.isImage || isImagePath(entry.path)) {
      const r = await ctxRest('/fs/preview?id=' + encodeURIComponent(id) + '&path=' + encodeURIComponent(entry.path))
      if (epoch !== treeEpoch) return
      $openFile.set({ path: entry.path, kind: 'image', dataUrl: r?.dataUrl, content: '' })
    } else if (entry.isText !== false && (entry.isText || isLikelyText(entry.path))) {
      const r = await ctxRest('/fs/read?id=' + encodeURIComponent(id) + '&path=' + encodeURIComponent(entry.path))
      if (epoch !== treeEpoch) return
      $openFile.set({
        path: entry.path,
        kind: 'text',
        content: r?.content || '',
        truncated: !!r?.truncated
      })
    } else {
      $openFile.set({ path: entry.path, kind: 'binary', content: '', bytes: entry.size })
    }
    $editorDirty.set(false)
  } catch (e) {
    if (epoch === treeEpoch) notify('error', String(e?.message || e))
  }
}

async function saveOpenFile() {
  const id = $selectedId.get()
  const file = $openFile.get()
  if (!id || !file || file.kind !== 'text') return
  try {
    const preview = await ctxRest('/fs/write', {
      method: 'POST',
      body: { id, path: file.path, content: file.content, dryRun: true }
    })
    if (preview?.identical) {
      $editorDirty.set(false)
      notify('success', tOf(localeCache, 'saved'))
      return
    }
    $pendingWrite.set({
      id,
      path: file.path,
      content: file.content,
      diff: preview?.diff || '',
      addedLines: preview?.addedLines || 0,
      removedLines: preview?.removedLines || 0,
      emptyRemote: !!preview?.emptyRemote
    })
  } catch (e) {
    notify('error', String(e?.message || e))
  }
}

async function commitPendingWrite() {
  const pending = $pendingWrite.get()
  if (!pending) return
  $pendingWrite.set(null)
  try {
    if (!$servers.get().some(s => s.id === pending.id)) throw new Error('Server no longer exists')
    await ctxRest('/fs/write', {
      method: 'POST',
      body: { id: pending.id, path: pending.path, content: pending.content, dryRun: false }
    })
    $editorDirty.set(false)
    notify('success', tOf(localeCache, 'saved'))
    await refreshTreePath(pending.path)
  } catch (e) {
    notify('error', String(e?.message || e))
  }
}

let localeCache = 'zh'

// ── Components ───────────────────────────────────────────────────────────────

function Icon({ name, className }) {
  const C = icons?.[name]
  if (!C) {
    return jsx('span', { className: className || '', children: '·' })
  }
  return jsx(C, { className: className || 'h-4 w-4' })
}

function ServerList({ t, onEdit, onChanged }) {
  const servers = useValue($servers)
  const selected = useValue($selectedId)
  const defaultId = useValue($defaultId)

  return jsxs('div', {
    className: 'flex h-full w-56 shrink-0 flex-col border-r border-(--ui-stroke-secondary)',
    children: [
      jsxs('div', {
        className: 'flex items-center justify-between gap-1 px-2 py-1.5',
        children: [
          jsx('div', {
            className: 'text-[0.6875rem] font-medium text-(--ui-text-tertiary)',
            children: t('servers')
          }),
          jsx(Button, {
            size: 'sm',
            variant: 'ghost',
            onClick: () => onEdit(null),
            children: t('addServer')
          })
        ]
      }),
      jsx(Separator, {}),
      jsx(ScrollArea, {
        className: 'flex-1',
        children: jsx('div', {
          className: 'flex flex-col gap-0.5 p-1',
          children:
            servers.length === 0
              ? jsx(EmptyState, {
                  className: 'px-2 py-6',
                  title: t('noServer'),
                  description: t('noServerHint')
                })
              : servers.map(s =>
                  jsx(
                    'button',
                    {
                      type: 'button',
                      className:
                        'flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs ' +
                        (s.id === selected
                          ? 'bg-(--ui-fill-secondary) text-(--ui-text-primary)'
                          : 'text-(--ui-text-secondary) hover:bg-(--ui-fill-secondary)'),
                      onClick: () => {
                        $selectedId.set(s.id)
                        $openFile.set(null)
                        // Tree reload is owned by DeployPage's selected-effect (epoch-safe).
                      },
                      children: [
                        jsx(StatusDot, {
                          key: 'dot',
                          variant: s.id === defaultId ? 'success' : 'neutral'
                        }),
                        jsxs('span', {
                          key: 'body',
                          className: 'min-w-0 flex-1',
                          children: [
                            jsx('div', {
                              className: 'truncate font-medium',
                              children: s.name || s.id
                            }),
                            jsx('div', {
                              className: 'truncate text-[0.625rem] text-(--ui-text-tertiary)',
                              children: (s.username || '') + '@' + (s.host || '') + ':' + (s.port || 22)
                            })
                          ]
                        }),
                        jsx(Badge, {
                          key: 'def',
                          variant: s.id === defaultId ? 'default' : 'outline',
                          className: 'shrink-0 text-[0.5625rem]',
                          children: s.id === defaultId ? 'D' : s.auth || 'password'
                        })
                      ]
                    },
                    s.id
                  )
                )
        })
      }),
      jsxs('div', {
        className: 'flex flex-col gap-1 border-t border-(--ui-stroke-secondary) p-1.5',
        children: [
          jsx(Button, {
            size: 'sm',
            variant: 'outline',
            disabled: !selected,
            onClick: () => {
              const s = servers.find(x => x.id === selected)
              if (s) onEdit(s)
            },
            children: t('editServer')
          }),
          jsx(Button, {
            size: 'sm',
            variant: 'ghost',
            disabled: !selected,
            onClick: async () => {
              if (!selected) return
              try {
                const r = await ctxRest('/servers/' + encodeURIComponent(selected) + '/test', {
                  method: 'POST',
                  body: {}
                })
                if (r?.ok) notify('success', t('testOk') + (r.hostname ? ': ' + r.hostname : ''))
                else notify('error', t('testFail') + ': ' + (r?.error || ''))
              } catch (e) {
                notify('error', String(e?.message || e))
              }
            },
            children: t('test')
          }),
          jsx(Button, {
            size: 'sm',
            variant: 'ghost',
            disabled: !selected,
            onClick: async () => {
              if (!selected) return
              await ctxRest('/servers/default', { method: 'POST', body: { id: selected } })
              await onChanged()
            },
            children: t('setDefault')
          }),
          jsx(Button, {
            size: 'sm',
            variant: 'ghost',
            disabled: !selected,
            className: 'text-(--ui-text-secondary)',
            onClick: () => {
              const s = servers.find(x => x.id === selected)
              if (s) $confirmDeleteServer.set({ id: s.id, name: s.name || s.id })
            },
            children: t('delete')
          })
        ]
      })
    ]
  })
}

function TreeRow({ t, entry, depth, onMenu }) {
  const expanded = useValue($expanded)
  const nodes = useValue($treeNodes)
  const loadingMap = useValue($treeLoading)
  const openPath = useValue($openFile)?.path
  const isDir = entry.type === 'dir'
  const isOpen = !!expanded[entry.path]
  const kids = isDir && isOpen ? nodes[entry.path] || [] : []
  const isLoading = !!loadingMap[entry.path]

  return jsxs('div', { children: [
    jsxs('div', {
      className:
        'flex cursor-pointer items-center gap-1.5 rounded-sm px-1 py-[3px] text-xs hover:bg-(--ui-fill-secondary)' +
        (openPath === entry.path ? ' bg-(--ui-fill-secondary) text-(--ui-text-primary)' : ' text-(--ui-text-secondary)'),
      style: { paddingLeft: 8 + depth * 12 },
      onClick: () => void openEntry(entry),
      children: [
        isDir
          ? jsx('span', {
              className: 'w-3 shrink-0 text-center text-[0.625rem] text-(--ui-text-quaternary)',
              children: isLoading ? '…' : isOpen ? 'v' : '>'
            })
          : jsx('span', { className: 'w-3 shrink-0' }),
        jsx(Icon, {
          name: isDir ? (isOpen ? 'FolderOpen' : 'Folder') : entry.isImage ? 'Image' : 'File',
          className: 'h-3.5 w-3.5 shrink-0 text-(--ui-text-tertiary)'
        }),
        jsx('span', { className: 'min-w-0 flex-1 truncate', children: entry.name }),
        !isDir
          ? jsx('span', {
              className: 'shrink-0 text-[0.625rem] text-(--ui-text-quaternary)',
              children: fmtSize(entry.size)
            })
          : null,
        jsx(Button, {
          size: 'sm',
          variant: 'ghost',
          className: 'h-5 px-1 opacity-0 hover:opacity-100',
          onClick: ev => {
            ev?.stopPropagation?.()
            onMenu?.(entry)
          },
          children: '⋯'
        })
      ]
    }),
    isDir && isOpen && !isLoading && kids.length === 0
      ? jsx('div', {
          className: 'px-2 py-0.5 text-[0.625rem] text-(--ui-text-quaternary)',
          style: { paddingLeft: 8 + (depth + 1) * 12 },
          children: t('emptyDir')
        })
      : null,
    isDir && isOpen
      ? kids.map(k => jsx(TreeRow, { t, entry: k, depth: depth + 1, onMenu }, k.path))
      : null
  ] })
}

function FileTree({ t }) {
  const nodes = useValue($treeNodes)
  const expanded = useValue($expanded)
  const loadingMap = useValue($treeLoading)
  const [prompt, setPrompt] = useState(null)
  const [confirmDelete, setConfirmDelete] = useState(null)
  const [menuEntry, setMenuEntry] = useState(null)
  const rootKids = nodes['/'] || []
  const rootOpen = !!expanded['/']
  const rootLoading = !!loadingMap['/']

  const createParent = () => {
    const open = $openFile.get()
    if (open?.path) return parentOf(open.path)
    // deepest expanded dir with children
    let best = '/'
    for (const p of Object.keys($expanded.get())) {
      if ($expanded.get()[p] && p.length >= best.length) best = p
    }
    return best
  }

  return jsxs('div', {
    className: 'flex h-full min-w-0 flex-1 flex-col border-r border-(--ui-stroke-secondary)',
    children: [
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-1 border-b border-(--ui-stroke-secondary) px-2 py-1.5',
        children: [
          jsx('div', {
            className: 'mr-auto text-[0.6875rem] font-medium text-(--ui-text-tertiary)',
            children: t('remoteFiles') || 'Remote'
          }),
          jsx(Button, {
            size: 'sm',
            variant: 'ghost',
            onClick: () => void resetTreeForServer(),
            children: t('refresh')
          }),
          jsx(Button, {
            size: 'sm',
            variant: 'outline',
            onClick: () => {
              $createParent.set(createParent())
              setPrompt({ kind: 'file' })
            },
            children: t('newFile')
          }),
          jsx(Button, {
            size: 'sm',
            variant: 'outline',
            onClick: () => {
              $createParent.set(createParent())
              setPrompt({ kind: 'folder' })
            },
            children: t('newFolder')
          })
        ]
      }),
      rootLoading && rootKids.length === 0
        ? jsx('div', {
            className: 'flex flex-col gap-2 p-3',
            children: [0, 1, 2, 3].map(i => jsx(Skeleton, { className: 'h-6' }, i))
          })
        : jsx(ScrollArea, {
            className: 'flex-1 py-1',
            children: jsxs('div', { children: [
              jsxs('div', {
                className:
                  'flex cursor-pointer items-center gap-1.5 rounded-sm px-2 py-[3px] text-xs font-medium hover:bg-(--ui-fill-secondary)',
                onClick: () => void toggleDir('/'),
                children: [
                  jsx('span', {
                    className: 'w-3 shrink-0 text-center text-[0.625rem]',
                    children: rootLoading ? '…' : rootOpen ? 'v' : '>'
                  }),
                  jsx(Icon, { name: 'Server', className: 'h-3.5 w-3.5 text-(--ui-text-tertiary)' }),
                  jsx('span', { children: '/' })
                ]
              }),
              rootOpen
                ? rootKids.map(e => jsx(TreeRow, { t, entry: e, depth: 1, onMenu: setMenuEntry }, e.path))
                : null
            ] })
          }),
      prompt
        ? jsx(PathPrompt, {
            t,
            mode: prompt.kind,
            parent: $createParent.get(),
            onClose: () => setPrompt(null)
          })
        : null,
      menuEntry
        ? jsx(Dialog, {
            open: true,
            onOpenChange: o => { if (!o) setMenuEntry(null) },
            children: jsxs(DialogContent, {
              className: 'sm:max-w-sm',
              children: [
                jsx(DialogHeader, {
                  children: jsx(DialogTitle, { children: menuEntry.name })
                }),
                jsx('div', {
                  className: 'text-[0.6875rem] text-(--ui-text-tertiary)',
                  children: menuEntry.path
                }),
                jsx(DialogFooter, {
                  className: 'flex-col gap-1 sm:flex-col',
                  children: [
                    jsx(Button, {
                      size: 'sm',
                      variant: 'outline',
                      onClick: async () => {
                        const id = $selectedId.get()
                        const e = menuEntry
                        setMenuEntry(null)
                        if (!id || !e) return
                        const nextName = window.prompt(t('fileName'), e.name)
                        if (!nextName || nextName === e.name) return
                        const next = joinPath(parentOf(e.path), nextName.trim())
                        try {
                          await ctxRest('/fs/rename', {
                            method: 'POST',
                            body: { id, src: e.path, dst: next, from: e.path, to: next }
                          })
                          notify('success', t('renamed'))
                          if ($openFile.get()?.path === e.path) $openFile.set(null)
                          await refreshTreePath(e.path)
                          await refreshTreePath(next)
                        } catch (err2) {
                          notify('error', String(err2?.message || err2))
                        }
                      },
                      children: t('rename') || 'Rename'
                    }, 'r'),
                    jsx(Button, {
                      size: 'sm',
                      variant: 'ghost',
                      onClick: () => {
                        setConfirmDelete(menuEntry)
                        setMenuEntry(null)
                      },
                      children: t('delete')
                    }, 'd')
                  ]
                })
              ]
            })
          })
        : null,
      confirmDelete
        ? jsx(ConfirmDialog, {
            open: true,
            title: t('confirmDeleteFile'),
            description: confirmDelete.path,
            confirmLabel: t('delete'),
            cancelLabel: t('cancel'),
            onConfirm: async () => {
              const id = $selectedId.get()
              const target = confirmDelete
              setConfirmDelete(null)
              if (!id || !target) return
              try {
                await ctxRest('/fs/delete', {
                  method: 'POST',
                  body: { id, path: target.path, recursive: target.type === 'dir' }
                })
                notify('success', t('deleted'))
                if ($openFile.get()?.path === target.path) $openFile.set(null)
                await refreshTreePath(target.path)
              } catch (err2) {
                notify('error', String(err2?.message || err2))
              }
            },
            onCancel: () => setConfirmDelete(null)
          })
        : null
    ]
  })
}

function PathPrompt({ t, mode, parent, onClose }) {
  const [name, setName] = useState('')
  const base = parent || '/'
  return jsx(Dialog, {
    open: true,
    onOpenChange: open => {
      if (!open) onClose()
    },
    children: jsxs(DialogContent, {
      className: 'sm:max-w-md',
      children: [
        jsx(DialogHeader, {
          children: jsx(DialogTitle, {
            children: mode === 'folder' ? t('newFolder') : t('newFile')
          })
        }),
        jsx('div', {
          className: 'mb-2 text-[0.6875rem] text-(--ui-text-tertiary)',
          children: base
        }),
        jsx(Input, {
          value: name,
          placeholder: mode === 'folder' ? t('folderName') : t('fileName'),
          onChange: e => setName(e.target.value)
        }),
        jsx(DialogFooter, {
          children: [
            jsx(Button, { variant: 'ghost', onClick: onClose, children: t('cancel') }, 'c'),
            jsx(
              Button,
              {
                onClick: async () => {
                  const id = $selectedId.get()
                  const full = joinPath(base, name.trim())
                  if (!id || !name.trim()) return
                  try {
                    if (mode === 'folder') {
                      await ctxRest('/fs/mkdir', { method: 'POST', body: { id, path: full } })
                    } else {
                      await ctxRest('/fs/write', {
                        method: 'POST',
                        body: { id, path: full, content: '' }
                      })
                    }
                    notify('success', t('created'))
                    onClose()
                    // ensure parent expanded and refreshed
                    const exp = { ...$expanded.get() }
                    exp[base] = true
                    $expanded.set(exp)
                    await loadTreeDir(base)
                  } catch (e) {
                    notify('error', String(e?.message || e))
                  }
                },
                children: t('create')
              },
              'ok'
            )
          ]
        })
      ]
    })
  })
}

function EditorPanel({ t }) {
  const file = useValue($openFile)
  const dirty = useValue($editorDirty)
  const [busy, setBusy] = useState(false)

  if (!file) {
    return jsx('div', {
      className: 'flex h-full items-center justify-center text-xs text-(--ui-text-tertiary)',
      children: t('noFile')
    })
  }

  if (file.kind === 'image') {
    return jsxs('div', {
      className: 'flex h-full flex-col',
      children: [
        jsxs('div', {
          className: 'border-b border-(--ui-stroke-secondary) px-2 py-1 text-[0.6875rem] text-(--ui-text-tertiary)',
          children: [t('preview'), ' · ', file.path]
        }),
        jsx('div', {
          className: 'flex flex-1 items-center justify-center overflow-auto bg-(--ui-fill-secondary) p-3',
          children: file.dataUrl
            ? jsx('img', {
                src: file.dataUrl,
                alt: file.path,
                className: 'max-h-full max-w-full object-contain'
              })
            : jsx('div', { className: 'text-xs', children: t('imageUnsupported') })
        })
      ]
    })
  }

  if (file.kind === 'binary') {
    return jsx('div', {
      className: 'flex h-full flex-col items-center justify-center gap-2 text-xs text-(--ui-text-tertiary)',
      children: [
        jsx('div', { children: file.path }),
        jsx('div', { children: fmtSize(file.bytes) }),
        jsx('div', { children: t('type') + ': binary' })
      ]
    })
  }

  return jsxs('div', {
    className: 'flex h-full flex-col',
    children: [
      jsxs('div', {
        className: 'flex items-center gap-2 border-b border-(--ui-stroke-secondary) px-2 py-1',
        children: [
          jsx('div', {
            className: 'min-w-0 flex-1 truncate text-[0.6875rem] text-(--ui-text-tertiary)',
            children: file.path + (dirty ? ' •' : '')
          }),
          file.truncated
            ? jsx(Badge, { variant: 'outline', children: t('textTooLarge') })
            : null,
          jsx(Button, {
            size: 'sm',
            disabled: busy || !dirty,
            onClick: async () => {
              setBusy(true)
              try {
                await saveOpenFile()
              } finally {
                setBusy(false)
              }
            },
            children: busy ? t('saving') : t('save')
          })
        ]
      }),
      jsx('div', {
        className: 'min-h-0 flex-1 p-0',
        children: jsx(Textarea, {
          className: 'h-full min-h-[200px] resize-none rounded-none border-0 font-mono text-[0.75rem] leading-relaxed',
          value: file.content,
          spellCheck: false,
          onChange: e => {
            const v = e.target.value
            $openFile.set({ ...file, content: v })
            $editorDirty.set(true)
          }
        })
      })
    ]
  })
}

function ServerDialog({ t, server, onClose, onSaved }) {
  const [tab, setTab] = useState('conn')
  const [form, setForm] = useState(() => ({
    id: server?.id || null,
    name: server?.name || '',
    host: server?.host || '',
    port: server?.port || 22,
    username: server?.username || '',
    auth: server?.auth || 'password',
    password: '',
    privateKey: server?.privateKey && server.privateKey !== '***' ? server.privateKey : '',
    passphrase: '',
    allow_exec: !!server?.allow_exec,
    mappings: (server?.mappings || []).map(m => ({ ...m })),
    exclusionsText: (server?.exclusions || []).join('\n'),
    allowedText: (server?.allowedRemotePaths || []).join('\n'),
    allowedLocalText: (server?.allowedLocalPaths || []).join('\n'),
    whitelistText: (server?.commandWhitelist || []).join('\n'),
    blacklistText: (server?.commandBlacklist || []).join('\n')
  }))
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  return jsx(Dialog, {
    open: true,
    onOpenChange: o => {
      if (!o) onClose()
    },
    children: jsxs(DialogContent, {
      className: 'max-h-[85vh] overflow-y-auto sm:max-w-lg',
      children: [
        jsx(DialogHeader, {
          children: jsx(DialogTitle, {
            children: server ? t('editServer') : t('addServer')
          })
        }),
        jsx(DialogDescription, {
          children: t('subtitle')
        }),
        jsxs('div', {
          className: 'mb-2 flex gap-1',
          children: [
            jsx(
              Button,
              {
                size: 'sm',
                variant: tab === 'conn' ? 'default' : 'ghost',
                onClick: () => setTab('conn'),
                children: t('connection')
              },
              'conn'
            ),
            jsx(
              Button,
              {
                size: 'sm',
                variant: tab === 'map' ? 'default' : 'ghost',
                onClick: () => setTab('map'),
                children: t('mappingTab')
              },
              'map'
            )
          ]
        }),
        tab === 'conn'
          ? jsxs('div', {
              className: 'grid gap-2',
              children: [
                jsxs('label', {
                  className: 'grid gap-1 text-xs',
                  children: [
                    t('serverName'),
                    jsx(Input, {
                      value: form.name,
                      onChange: e => set('name', e.target.value)
                    })
                  ]
                }),
                jsxs('div', {
                  className: 'grid grid-cols-3 gap-2',
                  children: [
                    jsxs('label', {
                      className: 'col-span-2 grid gap-1 text-xs',
                      children: [
                        t('host'),
                        jsx(Input, {
                          value: form.host,
                          placeholder: t('placeholderHost'),
                          onChange: e => set('host', e.target.value)
                        })
                      ]
                    }),
                    jsxs('label', {
                      className: 'grid gap-1 text-xs',
                      children: [
                        t('port'),
                        jsx(Input, {
                          type: 'number',
                          value: form.port,
                          onChange: e => set('port', Number(e.target.value) || 22)
                        })
                      ]
                    })
                  ]
                }),
                jsxs('label', {
                  className: 'grid gap-1 text-xs',
                  children: [
                    t('username'),
                    jsx(Input, {
                      value: form.username,
                      placeholder: t('placeholderUser'),
                      onChange: e => set('username', e.target.value)
                    })
                  ]
                }),
                jsxs('label', {
                  className: 'grid gap-1 text-xs',
                  children: [
                    t('auth'),
                    jsxs('select', {
                      className:
                        'h-8 rounded-md border border-(--ui-stroke-secondary) bg-transparent px-2 text-xs',
                      value: form.auth,
                      onChange: e => set('auth', e.target.value),
                      children: [
                        jsx('option', { value: 'password', children: 'password' }, 'p'),
                        jsx('option', { value: 'key', children: 'private key' }, 'k'),
                        jsx('option', { value: 'agent', children: 'agent' }, 'a')
                      ]
                    })
                  ]
                }),
                form.auth === 'password'
                  ? jsxs('label', {
                      className: 'grid gap-1 text-xs',
                      children: [
                        t('password'),
                        jsx(Input, {
                          type: 'password',
                          value: form.password,
                          placeholder: t('placeholderPass'),
                          onChange: e => set('password', e.target.value)
                        }),
                        jsx('div', {
                          className: 'text-[0.625rem] font-normal text-(--ui-text-tertiary)',
                          children: t('vaultHint')
                        })
                      ]
                    })
                  : null,
                form.auth === 'key'
                  ? jsxs('div', {
                      className: 'grid gap-2',
                      children: [
                        jsxs('label', {
                          className: 'grid gap-1 text-xs',
                          children: [
                            t('privateKey'),
                            jsx(Input, {
                              value: form.privateKey,
                              placeholder: t('placeholderKey'),
                              onChange: e => set('privateKey', e.target.value)
                            })
                          ]
                        }),
                        jsxs('label', {
                          className: 'grid gap-1 text-xs',
                          children: [
                            t('passphrase'),
                            jsx(Input, {
                              type: 'password',
                              value: form.passphrase,
                              onChange: e => set('passphrase', e.target.value)
                            })
                          ]
                        })
                      ]
                    })
                  : null,
                jsxs('label', {
                  className: 'flex items-center gap-2 text-xs',
                  children: [
                    jsx('input', {
                      type: 'checkbox',
                      checked: form.allow_exec,
                      onChange: e => set('allow_exec', e.target.checked)
                    }),
                    t('allowExec')
                  ]
                })
              ]
            })
          : jsxs('div', {
              className: 'grid gap-2',
              children: [
                jsx('div', { className: 'text-xs font-medium', children: t('mappings') }),
                form.mappings.map((m, i) =>
                  jsxs(
                    'div',
                    {
                      className: 'grid grid-cols-[1fr_1fr_auto] gap-1',
                      children: [
                        jsx(Input, {
                          value: m.localRoot,
                          placeholder: t('placeholderLocal'),
                          onChange: e => {
                            const next = form.mappings.map((x, j) =>
                              j === i ? { ...x, localRoot: e.target.value } : x
                            )
                            set('mappings', next)
                          }
                        }),
                        jsx(Input, {
                          value: m.remoteRoot,
                          placeholder: t('placeholderRemote'),
                          onChange: e => {
                            const next = form.mappings.map((x, j) =>
                              j === i ? { ...x, remoteRoot: e.target.value } : x
                            )
                            set('mappings', next)
                          }
                        }),
                        jsx(Button, {
                          size: 'sm',
                          variant: 'ghost',
                          onClick: () =>
                            set(
                              'mappings',
                              form.mappings.filter((_, j) => j !== i)
                            ),
                          children: t('remove')
                        })
                      ]
                    },
                    'm' + i
                  )
                ),
                jsx(Button, {
                  size: 'sm',
                  variant: 'outline',
                  onClick: () =>
                    set('mappings', [...form.mappings, { localRoot: '', remoteRoot: '' }]),
                  children: t('addMapping')
                }),
                jsxs('label', {
                  className: 'grid gap-1 text-xs',
                  children: [
                    t('exclusions'),
                    jsx(Textarea, {
                      rows: 3,
                      value: form.exclusionsText,
                      onChange: e => set('exclusionsText', e.target.value)
                    })
                  ]
                }),
                jsxs('label', {
                  className: 'grid gap-1 text-xs',
                  children: [
                    t('allowedPaths'),
                    jsx(Textarea, {
                      rows: 2,
                      value: form.allowedText,
                      onChange: e => set('allowedText', e.target.value)
                    })
                  ]
                }),
                jsxs('label', {
                  className: 'grid gap-1 text-xs',
                  children: [
                    t('allowedLocal'),
                    jsx(Textarea, {
                      rows: 2,
                      value: form.allowedLocalText,
                      onChange: e => set('allowedLocalText', e.target.value)
                    })
                  ]
                }),
                jsxs('label', {
                  className: 'grid gap-1 text-xs',
                  children: [
                    t('whitelist'),
                    jsx(Textarea, {
                      rows: 3,
                      value: form.whitelistText,
                      onChange: e => set('whitelistText', e.target.value)
                    })
                  ]
                }),
                jsxs('label', {
                  className: 'grid gap-1 text-xs',
                  children: [
                    t('blacklist'),
                    jsx(Textarea, {
                      rows: 2,
                      value: form.blacklistText,
                      onChange: e => set('blacklistText', e.target.value)
                    })
                  ]
                })
              ]
            }),
        jsx(DialogFooter, {
          children: [
            jsx(Button, { variant: 'ghost', onClick: onClose, children: t('cancel') }, 'c'),
            jsx(
              Button,
              {
                onClick: async () => {
                  try {
                    const body = {
                      id: form.id || undefined,
                      name: form.name || form.host || 'server',
                      host: form.host,
                      port: Number(form.port) || 22,
                      username: form.username,
                      auth: form.auth,
                      password: form.auth === 'password' ? form.password || undefined : undefined,
                      privateKey: form.auth === 'key' ? form.privateKey : undefined,
                      passphrase: form.auth === 'key' ? form.passphrase || undefined : undefined,
                      allow_exec: !!form.allow_exec,
                      mappings: form.mappings.filter(m => m.localRoot && m.remoteRoot),
                      exclusions: form.exclusionsText.split('\n').map(s => s.trim()).filter(Boolean),
                      allowedRemotePaths: form.allowedText.split('\n').map(s => s.trim()).filter(Boolean),
                      allowedLocalPaths: form.allowedLocalText.split('\n').map(s => s.trim()).filter(Boolean),
                      commandWhitelist: form.whitelistText.split('\n').map(s => s.trim()).filter(Boolean),
                      commandBlacklist: form.blacklistText.split('\n').map(s => s.trim()).filter(Boolean)
                    }
                    await ctxRest('/servers', { method: 'POST', body })
                    notify('success', t('saved'))
                    onClose()
                    await onSaved()
                  } catch (e) {
                    notify('error', String(e?.message || e))
                  }
                },
                children: t('save')
              },
              's'
            )
          ]
        })
      ]
    })
  })
}

function ServerTopBar({ t, onEdit, onAdd }) {
  const servers = useValue($servers)
  const selected = useValue($selectedId)
  const showSidebar = useValue($showServerSidebar)
  const cur = servers.find(s => s.id === selected) || null
  const defaultId = useValue($defaultId)

  return jsxs('div', {
    className:
      'flex flex-wrap items-center gap-2 border-b border-(--ui-stroke-secondary) bg-(--ui-panel-background) px-3 py-1.5',
    children: [
      jsx(StatusDot, { variant: cur ? 'success' : 'neutral' }),
      servers.length > 0
        ? jsx(DropdownMenu, {
            children: [
              jsx(
                DropdownMenuTrigger,
                {
                  asChild: true,
                  children: jsx(Button, {
                    size: 'sm',
                    variant: 'ghost',
                    className: 'max-w-[min(20rem,50vw)] min-w-0 gap-1 px-1.5 text-xs',
                    children: jsxs('span', {
                      className: 'flex min-w-0 items-center gap-1.5',
                      children: [
                        jsx('span', {
                          className: 'truncate font-medium text-(--ui-text-primary)',
                          children: cur ? cur.name || cur.id : t('noServer')
                        }),
                        cur
                          ? jsx('span', {
                              className:
                                'truncate text-[0.6875rem] font-normal text-(--ui-text-tertiary)',
                              children:
                                (cur.username || '') +
                                '@' +
                                (cur.host || '') +
                                ':' +
                                (cur.port || 22)
                            })
                          : null,
                        jsx('span', {
                          className: 'shrink-0 text-[0.625rem] text-(--ui-text-quaternary)',
                          children: '⌄'
                        })
                      ]
                    })
                  })
                },
                'trigger'
              ),
              jsx(
                DropdownMenuContent,
                {
                  align: 'start',
                  className: 'max-h-64 w-72 overflow-auto',
                  children: servers.map(s =>
                    jsx(
                      DropdownMenuItem,
                      {
                        className:
                          'flex items-center gap-2 text-xs ' +
                          (s.id === selected ? 'bg-(--ui-fill-secondary)' : ''),
                        onSelect: () => {
                          if (s.id !== $selectedId.get()) $selectedId.set(s.id)
                        },
                        children: [
                          jsx(StatusDot, {
                            key: 'd',
                            variant: s.id === selected ? 'success' : 'neutral'
                          }),
                          jsxs(
                            'span',
                            {
                              key: 'body',
                              className: 'flex min-w-0 flex-1 flex-col',
                              children: [
                                jsx('span', {
                                  className: 'truncate font-medium',
                                  children: s.name || s.id
                                }),
                                jsx('span', {
                                  className:
                                    'truncate text-[0.625rem] text-(--ui-text-tertiary)',
                                  children:
                                    (s.username || '') +
                                    '@' +
                                    (s.host || '') +
                                    ':' +
                                    (s.port || 22)
                                })
                              ]
                            },
                            'b'
                          ),
                          s.id === defaultId
                            ? jsx(
                                Badge,
                                {
                                  key: 'def',
                                  variant: 'outline',
                                  className: 'shrink-0 text-[0.5625rem]',
                                  children: 'D'
                                },
                                'def'
                              )
                            : null
                        ]
                      },
                      s.id
                    )
                  )
                },
                'content'
              )
            ]
          })
        : jsx('span', {
            className: 'text-xs text-(--ui-text-tertiary)',
            children: t('noServer')
          }),
      cur && cur.id === defaultId
        ? jsx(Badge, { variant: 'outline', className: 'text-[0.5625rem]', children: 'D' })
        : null,
      jsx('div', { className: 'flex-1' }),
      jsx(Button, {
        size: 'sm',
        variant: 'ghost',
        onClick: () => onAdd(),
        children: '+'
      }),
      jsx(Button, {
        size: 'sm',
        variant: 'outline',
        disabled: !cur,
        onClick: () => cur && onEdit(cur),
        children: t('editServer')
      }),
      jsx(Button, {
        size: 'sm',
        variant: 'ghost',
        disabled: !cur,
        onClick: async () => {
          if (!cur) return
          try {
            const r = await ctxRest('/servers/' + encodeURIComponent(cur.id) + '/test', {
              method: 'POST',
              body: {}
            })
            if (r?.ok) notify('success', t('testOk') + (r.hostname ? ': ' + r.hostname : ''))
            else notify('error', t('testFail') + ': ' + (r?.error || ''))
          } catch (e) {
            notify('error', String(e?.message || e))
          }
        },
        children: t('test')
      }),
      jsx(Button, {
        size: 'sm',
        variant: 'ghost',
        disabled: !cur,
        onClick: () => {
          if (cur) $confirmDeleteServer.set({ id: cur.id, name: cur.name || cur.id })
        },
        children: t('delete')
      }),
      jsx(Button, {
        size: 'sm',
        variant: 'ghost',
        onClick: () => $showServerSidebar.set(!showSidebar),
        children: showSidebar ? t('hideSidebar') : t('showSidebar')
      })
    ]
  })
}

function OperationsPanel({ t, selected }) {
  const [open, setOpen] = useState(false)
  const [localRoot, setLocalRoot] = useState('')
  const [preview, setPreview] = useState(null)
  const [audit, setAudit] = useState(null)
  const [busy, setBusy] = useState(false)

  async function loadAudit() {
    try {
      const result = await ctxRest('/audit?limit=30')
      setAudit(result?.entries || [])
    } catch (e) {
      notify('error', String(e?.message || e))
    }
  }

  async function previewUpload() {
    if (!selected) return
    setBusy(true)
    try {
      const result = await ctxRest('/fs/sync', {
        method: 'POST',
        body: { id: selected, localRoot: localRoot.trim() || null, dryRun: true }
      })
      if (!result?.ok) throw new Error(result?.error || 'Sync preview failed')
      setPreview({ ...result, serverId: selected })
    } catch (e) {
      notify('error', String(e?.message || e))
    } finally {
      setBusy(false)
    }
  }

  function confirmSync() {
    const plan = preview
    setPreview(null)
    if (!plan || plan.serverId !== $selectedId.get()) return
    void ctxRest('/fs/sync', {
      method: 'POST',
      body: {
        id: plan.serverId,
        localRoot: plan.localRoot,
        dryRun: false,
        maxFiles: plan.count || 500,
        expectedFiles: plan.files || []
      }
    })
      .then(result => {
        if (!result?.ok || result?.errors?.length) {
          throw new Error(result?.error || result.errors.join('\n'))
        }
        notify('success', t('saved'))
        void loadAudit()
      })
      .catch(e => notify('error', String(e?.message || e)))
  }

  return jsxs('div', {
    className: 'border-b border-(--ui-stroke-secondary) px-3 py-1 text-xs',
    children: [
      jsx(Button, {
        size: 'sm',
        variant: 'ghost',
        onClick: () => setOpen(!open),
        children: t('operations')
      }),
      open
        ? jsxs('div', {
            className: 'flex flex-wrap items-start gap-2 py-2',
            children: [
              jsx(Input, {
                className: 'max-w-sm',
                value: localRoot,
                placeholder: t('syncLocalRoot'),
                onChange: e => setLocalRoot(e.target.value)
              }),
              jsx(Button, {
                size: 'sm',
                disabled: !selected || busy,
                onClick: () => void previewUpload(),
                children: t('previewSync')
              }),
              jsx(Button, {
                size: 'sm',
                variant: 'outline',
                onClick: () => void loadAudit(),
                children: t('auditRefresh')
              }),
              audit
                ? jsx('div', {
                    className: 'max-h-28 w-full overflow-auto text-(--ui-text-secondary)',
                    children: audit.length
                      ? audit.map((entry, index) =>
                          jsx(
                            'div',
                            {
                              children:
                                (entry.ts || '') +
                                ' · ' +
                                (entry.op || '') +
                                ' · ' +
                                (entry.serverName || entry.serverId || '') +
                                ' · ' +
                                (entry.ok ? '✓' : '×') +
                                ' · ' +
                                (entry.path || '')
                            },
                            index
                          )
                        )
                      : t('auditEmpty')
                  })
                : null
            ]
          })
        : null,
      preview
        ? jsx(ConfirmDialog, {
            open: true,
            title: t('confirmSync'),
            description: t('syncResult').replace('{count}', String(preview.count || 0)),
            confirmLabel: t('syncNow'),
            cancelLabel: t('cancel'),
            onCancel: () => setPreview(null),
            onConfirm: () => void confirmSync(),
            children: jsx('pre', {
              className: 'max-h-40 overflow-auto text-[0.6875rem]',
              children: (preview.files || [])
                .map(f => f.remotePath)
                .join('\n')
                .slice(0, 8000)
            })
          })
        : null
    ]
  })
}

function DeployPage({ t }) {
  const servers = useValue($servers)
  const backend = useValue($backendOk)
  const selected = useValue($selectedId)
  const pending = useValue($pendingWrite)
  const showSidebar = useValue($showServerSidebar)
  const confirmDelServer = useValue($confirmDeleteServer)
  const [editing, setEditing] = useState(undefined) // undefined=hidden, null=create, obj=edit

  useEffect(() => {
    if (bootstrapped) return
    bootstrapped = true
    void probeBackend().then(() => loadServers())
  }, [])

  useEffect(() => {
    void ensureTreeForSelected(selected)
  }, [selected])

  return jsxs('div', {
    className: 'relative flex h-full min-h-0 flex-col text-sm',
    children: [
      jsx(ServerTopBar, {
        t,
        onEdit: s => setEditing(s),
        onAdd: () => setEditing(null)
      }),
      backend === false
        ? jsx('div', {
            className: 'border-b border-(--ui-stroke-secondary) px-3 py-1 text-[0.6875rem] text-(--ui-text-secondary)',
            children: t('backendHint')
          })
        : null,
      jsx(OperationsPanel, { t, selected }),
      jsxs('div', {
        className: 'flex min-h-0 flex-1',
        children: [
          showSidebar
            ? jsx(ServerList, {
                t,
                onEdit: s => setEditing(s),
                onChanged: async () => {
                  await loadServers()
                }
              })
            : null,
          servers.length === 0
            ? jsx('div', {
                className: 'flex flex-1 items-center justify-center',
                children: jsx(EmptyState, {
                  title: t('noServer'),
                  description: t('noServerHint'),
                  action: jsx(Button, {
                    onClick: () => setEditing(null),
                    children: t('addServer')
                  })
                })
              })
            : jsxs('div', {
                className: 'flex min-w-0 flex-1',
                children: [
                  jsx(FileTree, { t }),
                  jsx('div', { className: 'w-px bg-(--ui-stroke-secondary)' }),
                  jsx('div', { className: 'min-w-0 flex-1', children: jsx(EditorPanel, { t }) })
                ]
              })
        ]
      }),
      editing !== undefined
        ? jsx(ServerDialog, {
            t,
            server: editing,
            onClose: () => setEditing(undefined),
            onSaved: async () => {
              await loadServers()
              await resetTreeForServer()
            }
          })
        : null,
      pending
        ? jsx(ConfirmDialog, {
            open: true,
            title: t('pendingWrite'),
            description:
              t('pendingWriteDesc') +
              '\n' +
              pending.path +
              '\n' +
              t('writeStats')
                .replace('{added}', String(pending.addedLines))
                .replace('{removed}', String(pending.removedLines)),
            confirmLabel: t('save'),
            cancelLabel: t('cancel'),
            onConfirm: () => void commitPendingWrite(),
            onCancel: () => $pendingWrite.set(null),
            children: jsx('pre', {
              className:
                'mt-2 max-h-48 overflow-auto rounded-md border border-(--ui-stroke-secondary) bg-(--ui-fill-secondary) p-2 text-[0.6875rem] text-(--ui-text-secondary)',
              children: (pending.diff || '(no textual diff / new file)').slice(0, 8000)
            })
          })
        : null,
      confirmDelServer
        ? jsx(ConfirmDialog, {
            open: true,
            title: t('confirmDeleteServer'),
            description: confirmDelServer.name,
            confirmLabel: t('delete'),
            cancelLabel: t('cancel'),
            onConfirm: () => {
              const target = confirmDelServer
              $confirmDeleteServer.set(null)
              void deleteServerById(target.id).catch(e => {
                notify('error', String(e?.message || e))
              })
            },
            onCancel: () => $confirmDeleteServer.set(null)
          })
        : null
    ]
  })
}

function StatusChip() {
  const ok = useValue($backendOk)
  return jsx('button', {
    type: 'button',
    className: 'px-1.5 text-[0.6875rem] text-(--ui-text-tertiary)',
    onClick: () => host.navigate(ROUTE),
    children: ok ? 'SSH' : 'SSH·'
  })
}

export default {
  id: ID,
  name: 'SSH Deploy',
  defaultEnabled: true,
  register(ctx) {
    ctxRest = (path, opts) => ctx.rest(path, opts)
    localeCache = 'zh'
    try {
      ctx.i18n?.register?.({ en: LOCALES.en, zh: LOCALES.zh })
    } catch {
      /* optional */
    }

    const t = key => tOf(localeCache, key)

    ctx.registerMany([
      {
        id: 'page',
        area: ROUTES_AREA,
        data: { path: ROUTE },
        render: () => jsx(DeployPage, { t })
      },
      {
        id: 'nav',
        area: SIDEBAR_NAV_AREA,
        data: { path: ROUTE, label: t('nav'), codicon: 'remote' }
      },
      {
        id: 'open',
        area: PALETTE_AREA,
        data: {
          id: 'ssh-plugin.open',
          label: t('nav') + ' · ' + t('open'),
          keywords: ['ssh', 'sftp', 'deploy', 'remote'],
          run: () => host.navigate(ROUTE)
        }
      },
      {
        id: 'status',
        area: STATUSBAR_AREAS.right,
        order: 160,
        render: () => jsx(StatusChip, {})
      },
      {
        id: 'pane',
        area: PANES_AREA,
        title: t('pane'),
        data: { placement: 'right', width: '360px' },
        render: () => jsx(DeployPage, { t })
      }
    ])

    ctx.onDispose?.(() => {
      bootstrapped = false
      treeLoadedFor = null
      $servers.set([])
      $treeNodes.set({})
      $expanded.set({})
      $openFile.set(null)
      $selectedId.set(null)
      $backendOk.set(null)
      $editorDirty.set(false)
      $showServerSidebar.set(false)
      $confirmDeleteServer.set(null)
    })
  }
}
