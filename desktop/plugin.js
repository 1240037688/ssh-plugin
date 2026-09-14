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
    placeholderPass: '仅保存在 gateway 本地',
    placeholderKey: '~/.ssh/id_rsa',
    placeholderLocal: 'E:/project',
    placeholderRemote: '/var/www/html',
    saved: '已保存',
    created: '已创建',
    deleted: '已删除',
    renamed: '已重命名',
    testOk: '连接成功',
    testFail: '连接失败'
  },
  en: {
    nav: 'SSH Deploy',
    pane: 'SSH Deploy',
    title: 'SSH Deploy',
    subtitle: 'Visual remote files · PyCharm Deployment-style',
    servers: 'Servers',
    addServer: 'Add server',
    editServer: 'Edit server',
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
    placeholderPass: 'Stored on gateway only',
    placeholderKey: '~/.ssh/id_rsa',
    placeholderLocal: 'E:/project',
    placeholderRemote: '/var/www/html',
    saved: 'Saved',
    created: 'Created',
    deleted: 'Deleted',
    renamed: 'Renamed',
    testOk: 'Connected',
    testFail: 'Connection failed'
  }
}

const $servers = atom([])
const $defaultId = atom(null)
const $selectedId = atom(null)
const $cwd = atom('/')
const $entries = atom([])
const $loadingList = atom(false)
const $listError = atom(null)
const $openFile = atom(null) // { path, content, truncated, kind: 'text'|'image'|'binary', dataUrl? }
const $backendOk = atom(null)
const $editorDirty = atom(false)

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

async function loadList() {
  const id = $selectedId.get()
  if (!id) {
    $entries.set([])
    return
  }
  $loadingList.set(true)
  $listError.set(null)
  try {
    const path = $cwd.get() || '/'
    const r = await ctxRest('/fs/ls?id=' + encodeURIComponent(id) + '&path=' + encodeURIComponent(path))
    $entries.set(r?.entries || [])
  } catch (e) {
    $listError.set(String(e?.message || e))
    $entries.set([])
  } finally {
    $loadingList.set(false)
  }
}

async function openEntry(entry) {
  const id = $selectedId.get()
  if (!id || !entry) return
  if (entry.type === 'dir') {
    $cwd.set(entry.path)
    $openFile.set(null)
    await loadList()
    return
  }
  try {
    if (entry.isImage || isImagePath(entry.path)) {
      const r = await ctxRest('/fs/preview?id=' + encodeURIComponent(id) + '&path=' + encodeURIComponent(entry.path))
      $openFile.set({ path: entry.path, kind: 'image', dataUrl: r?.dataUrl, content: '' })
    } else if (entry.isText !== false && (entry.isText || isLikelyText(entry.path))) {
      const r = await ctxRest('/fs/read?id=' + encodeURIComponent(id) + '&path=' + encodeURIComponent(entry.path))
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
    notify('error', String(e?.message || e))
  }
}

async function saveOpenFile() {
  const id = $selectedId.get()
  const file = $openFile.get()
  if (!id || !file || file.kind !== 'text') return
  try {
    await ctxRest('/fs/write', { method: 'POST', body: { id, path: file.path, content: file.content } })
    $editorDirty.set(false)
    notify('success', tOf(localeCache, 'saved'))
    await loadList()
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
                        $cwd.set('/')
                        $openFile.set(null)
                        void loadList()
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
          })
        ]
      })
    ]
  })
}

function FileTree({ t }) {
  const entries = useValue($entries)
  const cwd = useValue($cwd)
  const loading = useValue($loadingList)
  const err = useValue($listError)
  const path = useValue($openFile)?.path
  const [prompt, setPrompt] = useState(null) // { kind: 'file'|'folder'|'path' }

  return jsxs('div', {
    className: 'flex h-full min-w-0 flex-1 flex-col',
    children: [
      jsxs('div', {
        className: 'flex flex-wrap items-center gap-1 border-b border-(--ui-stroke-secondary) px-2 py-1.5',
        children: [
          jsx(Button, {
            size: 'sm',
            variant: 'ghost',
            onClick: () => {
              $cwd.set(parentOf(cwd))
              $openFile.set(null)
              void loadList()
            },
            children: t('up')
          }),
          jsx(ScrollArea, {
            className: 'min-w-0 flex-1',
            children: jsx('div', {
              className: 'flex items-center gap-0.5 overflow-x-auto whitespace-nowrap text-[0.6875rem] text-(--ui-text-secondary)',
              children: crumbs(cwd).map((c, i, arr) =>
                jsxs(
                  'span',
                  {
                    className: 'inline-flex items-center',
                    children: [
                      jsx(
                        'button',
                        {
                          type: 'button',
                          className:
                            'rounded px-1 hover:text-(--ui-text-primary)' +
                            (i === arr.length - 1 ? ' font-medium text-(--ui-text-primary)' : ''),
                          onClick: () => {
                            $cwd.set(c.path)
                            $openFile.set(null)
                            void loadList()
                          },
                          children: c.label
                        },
                        c.path
                      ),
                      i < arr.length - 1
                        ? jsx('span', { className: 'text-(--ui-text-quaternary)', children: '/' }, 'sep')
                        : null
                    ]
                  },
                  'c' + i
                )
              )
            })
          }),
          jsx(Button, {
            size: 'sm',
            variant: 'ghost',
            onClick: () => void loadList(),
            children: t('refresh')
          }),
          jsx(Button, {
            size: 'sm',
            variant: 'outline',
            onClick: () => setPrompt({ kind: 'file' }),
            children: t('newFile')
          }),
          jsx(Button, {
            size: 'sm',
            variant: 'outline',
            onClick: () => setPrompt({ kind: 'folder' }),
            children: t('newFolder')
          })
        ]
      }),
      err
        ? jsx('div', {
            className: 'px-2 py-1 text-[0.6875rem] text-(--ui-text-secondary)',
            children: err
          })
        : null,
      loading
        ? jsx('div', {
            className: 'flex flex-col gap-2 p-3',
            children: [0, 1, 2, 3].map(i => jsx(Skeleton, { className: 'h-6' }, i))
          })
        : jsx(ScrollArea, {
            className: 'flex-1',
            children:
              entries.length === 0
                ? jsx('div', {
                    className: 'px-3 py-6 text-xs text-(--ui-text-tertiary)',
                    children: t('emptyDir')
                  })
                : jsx('ul', {
                    className: 'divide-y divide-(--ui-stroke-secondary)',
                    children: entries.map(e =>
                      jsxs(
                        'li',
                        {
                          className:
                            'flex cursor-pointer items-center gap-2 px-2 py-1.5 text-xs hover:bg-(--ui-fill-secondary)' +
                            (path === e.path ? ' bg-(--ui-fill-secondary)' : ''),
                          onClick: () => void openEntry(e),
                          children: [
                            jsx(Icon, {
                              name: e.type === 'dir' ? 'Folder' : e.isImage ? 'Image' : 'File',
                              className: 'h-3.5 w-3.5 shrink-0 text-(--ui-text-tertiary)'
                            }),
                            jsx('span', {
                              className: 'min-w-0 flex-1 truncate text-(--ui-text-primary)',
                              children: e.name
                            }),
                            jsx('span', {
                              className: 'shrink-0 text-[0.625rem] text-(--ui-text-quaternary)',
                              children: e.type === 'dir' ? '' : fmtSize(e.size)
                            }),
                            jsx(Button, {
                              size: 'sm',
                              variant: 'ghost',
                              className: 'h-6 px-1 opacity-70',
                              onClick: ev => {
                                ev?.stopPropagation?.()
                                void (async () => {
                                  const id = $selectedId.get()
                                  if (!id) return
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
                                    await loadList()
                                  } catch (err2) {
                                    notify('error', String(err2?.message || err2))
                                  }
                                })()
                              },
                              children: '✎'
                            }),
                            jsx(Button, {
                              size: 'sm',
                              variant: 'ghost',
                              className: 'h-6 px-1 opacity-70',
                              onClick: ev => {
                                ev?.stopPropagation?.()
                                void (async () => {
                                  const id = $selectedId.get()
                                  if (!id) return
                                  if (!window.confirm(t('confirmDeleteFile') + '\n' + e.path)) return
                                  try {
                                    await ctxRest('/fs/delete', {
                                      method: 'POST',
                                      body: { id, path: e.path, recursive: e.type === 'dir' }
                                    })
                                    notify('success', t('deleted'))
                                    if ($openFile.get()?.path === e.path) $openFile.set(null)
                                    await loadList()
                                  } catch (err2) {
                                    notify('error', String(err2?.message || err2))
                                  }
                                })()
                              },
                              children: '×'
                            })
                          ]
                        },
                        e.path
                      )
                    )
                  })
          }),
      prompt
        ? jsx(PathPrompt, {
            t,
            mode: prompt.kind,
            onClose: () => setPrompt(null)
          })
        : null
    ]
  })
}

function PathPrompt({ t, mode, onClose }) {
  const [name, setName] = useState('')
  const cwd = useValue($cwd)
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
                  const full = joinPath(cwd, name.trim())
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
                    await loadList()
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
    allowedText: (server?.allowedRemotePaths || []).join('\n')
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
                      allowedRemotePaths: form.allowedText.split('\n').map(s => s.trim()).filter(Boolean)
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

function DeployPage({ t }) {
  const servers = useValue($servers)
  const backend = useValue($backendOk)
  const selected = useValue($selectedId)
  const [editing, setEditing] = useState(undefined) // undefined=hidden, null=create, obj=edit

  useEffect(() => {
    void probeBackend().then(() => loadServers())
  }, [])

  useEffect(() => {
    if (selected) void loadList()
  }, [selected])

  return jsxs('div', {
    className: 'flex h-full min-h-0 flex-col text-sm',
    children: [
      jsxs('div', {
        className: 'flex items-center gap-2 border-b border-(--ui-stroke-secondary) px-3 py-2',
        children: [
          jsx(Icon, { name: 'Remote', className: 'h-4 w-4 text-(--ui-text-tertiary)' }),
          jsxs('div', {
            className: 'min-w-0 flex-1',
            children: [
              jsx('div', {
                className: 'text-sm font-medium text-(--ui-text-primary)',
                children: t('title')
              }),
              jsx('div', {
                className: 'truncate text-[0.6875rem] text-(--ui-text-tertiary)',
                children: t('subtitle')
              })
            ]
          }),
          jsx(Badge, {
            variant: backend ? 'default' : 'outline',
            children: backend ? t('statusOnline') : t('statusOffline')
          })
        ]
      }),
      backend === false
        ? jsx('div', {
            className: 'border-b border-(--ui-stroke-secondary) px-3 py-1 text-[0.6875rem] text-(--ui-text-secondary)',
            children: t('backendHint')
          })
        : null,
      jsxs('div', {
        className: 'flex min-h-0 flex-1',
        children: [
          jsx(ServerList, {
            t,
            onEdit: s => setEditing(s),
            onChanged: async () => {
              await loadServers()
            }
          }),
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
                children: [jsx(FileTree, { t }), jsx('div', { className: 'w-px bg-(--ui-stroke-secondary)' }), jsx('div', { className: 'min-w-0 flex-1', children: jsx(EditorPanel, { t }) })]
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
              await loadList()
            }
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
      $servers.set([])
      $entries.set([])
      $openFile.set(null)
      $selectedId.set(null)
      $cwd.set('/')
      $backendOk.set(null)
      $editorDirty.set(false)
    })
  }
}
