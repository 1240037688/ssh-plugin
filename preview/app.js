/* SSH Deploy browser preview — offline mock of the Hermes desktop UI. */
(function () {
  const mockFS = {
    "/": [
      { name: "var", type: "dir", path: "/var", size: 0 },
      { name: "etc", type: "dir", path: "/etc", size: 0 },
      { name: "home", type: "dir", path: "/home", size: 0 }
    ],
    "/var": [
      { name: "www", type: "dir", path: "/var/www", size: 0 },
      { name: "log", type: "dir", path: "/var/log", size: 0 }
    ],
    "/var/www": [
      { name: "html", type: "dir", path: "/var/www/html", size: 0 },
      { name: "README.md", type: "file", path: "/var/www/README.md", size: 128 }
    ],
    "/var/www/html": [
      { name: "index.html", type: "file", path: "/var/www/html/index.html", size: 420 },
      { name: "app.js", type: "file", path: "/var/www/html/app.js", size: 1024 },
      { name: "logo.png", type: "file", path: "/var/www/html/logo.png", size: 2048, isImage: true },
      { name: "assets", type: "dir", path: "/var/www/html/assets", size: 0 }
    ],
    "/etc": [
      { name: "nginx", type: "dir", path: "/etc/nginx", size: 0 },
      { name: "hosts", type: "file", path: "/etc/hosts", size: 220 }
    ]
  };

  const mockFiles = {
    "/var/www/README.md": "# Deploy root\n\nMapped from E:/project\n",
    "/var/www/html/index.html":
      "<!DOCTYPE html>\n<html>\n  <body>\n    <h1>Hello from remote</h1>\n  </body>\n</html>\n",
    "/var/www/html/app.js": "console.log('remote app');\n",
    "/etc/hosts": "127.0.0.1 localhost\n"
  };

  const state = {
    servers: [
      {
        id: "srv_demo",
        name: "demo-prod",
        host: "10.0.0.8",
        port: 22,
        username: "deploy",
        auth: "password",
        default: true,
        mappings: [{ localRoot: "E:/project", remoteRoot: "/var/www/html" }],
        exclusions: [".git/**", "node_modules/**"],
        allow_exec: false
      }
    ],
    selectedId: "srv_demo",
    cwd: "/",
    open: null
  };

  const $ = (id) => document.getElementById(id);
  const serverList = $("serverList");
  const fileList = $("fileList");
  const crumbs = $("crumbs");
  const editor = $("editor");
  const imagePreview = $("imagePreview");
  const openPath = $("openPath");
  const btnSave = $("btnSave");
  const dlg = $("serverDlg");
  const form = $("serverForm");

  function toast(msg, err) {
    const el = $("toast");
    el.textContent = msg;
    el.classList.toggle("err", !!err);
    el.classList.remove("hidden");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.add("hidden"), 2200);
  }

  function fmtSize(n) {
    if (!n) return "";
    if (n < 1024) return n + " B";
    return (n / 1024).toFixed(1) + " KB";
  }

  function parentOf(p) {
    if (!p || p === "/") return "/";
    const i = p.lastIndexOf("/");
    return i <= 0 ? "/" : p.slice(0, i) || "/";
  }

  function renderServers() {
    serverList.innerHTML = "";
    state.servers.forEach((s) => {
      const li = document.createElement("li");
      li.className = s.id === state.selectedId ? "active" : "";
      li.innerHTML =
        '<span class="dot"></span><div><div>' +
        escapeHtml(s.name) +
        "</div><div class='server-meta'>" +
        escapeHtml(s.username + "@" + s.host + ":" + s.port) +
        (s.default ? " · D" : "") +
        "</div></div>";
      li.onclick = () => {
        state.selectedId = s.id;
        state.cwd = "/";
        state.open = null;
        render();
      };
      serverList.appendChild(li);
    });
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    })[c]);
  }

  function renderCrumbs() {
    crumbs.innerHTML = "";
    const parts = state.cwd.split("/").filter(Boolean);
    let cur = "";
    const items = [{ label: "/", path: "/" }];
    parts.forEach((p) => {
      cur += "/" + p;
      items.push({ label: p, path: cur });
    });
    items.forEach((c, i) => {
      const b = document.createElement("button");
      b.textContent = c.label;
      if (i === items.length - 1) b.className = "cur";
      b.onclick = () => {
        state.cwd = c.path;
        state.open = null;
        render();
      };
      crumbs.appendChild(b);
      if (i < items.length - 1) {
        const sep = document.createElement("span");
        sep.textContent = "/";
        crumbs.appendChild(sep);
      }
    });
  }

  function renderFiles() {
    const entries = (mockFS[state.cwd] || []).slice().sort((a, b) => {
      if (a.type !== b.type) return a.type === "dir" ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    fileList.innerHTML = "";
    if (!entries.length) {
      fileList.innerHTML = "<li style='color:var(--muted)'>空目录</li>";
      return;
    }
    entries.forEach((e) => {
      const li = document.createElement("li");
      li.className = state.open && state.open.path === e.path ? "active" : "";
      li.innerHTML =
        "<span>" +
        (e.type === "dir" ? "📁" : e.isImage ? "🖼" : "📄") +
        "</span><span>" +
        escapeHtml(e.name) +
        "</span><span class='size'>" +
        (e.type === "file" ? fmtSize(e.size) : "") +
        "</span>";
      li.onclick = () => openEntry(e);
      fileList.appendChild(li);
    });
  }

  function openEntry(e) {
    if (e.type === "dir") {
      state.cwd = e.path;
      state.open = null;
      render();
      return;
    }
    if (e.isImage) {
      // 1x1 png placeholder
      state.open = {
        path: e.path,
        kind: "image",
        dataUrl:
          "data:image/svg+xml," +
          encodeURIComponent(
            "<svg xmlns='http://www.w3.org/2000/svg' width='240' height='120'><rect width='100%' height='100%' fill='#1c2230'/><text x='50%' y='50%' fill='#8b95a8' font-size='14' text-anchor='middle' dominant-baseline='middle'>remote image · " +
              e.path +
              "</text></svg>"
          )
      };
    } else {
      state.open = {
        path: e.path,
        kind: "text",
        content: mockFiles[e.path] != null ? mockFiles[e.path] : "// " + e.path + "\n"
      };
    }
    renderEditor();
    renderFiles();
  }

  function renderEditor() {
    const file = state.open;
    if (!file) {
      openPath.textContent = "选择左侧文件进行编辑或预览";
      editor.classList.add("hidden");
      imagePreview.classList.add("hidden");
      editor.disabled = true;
      btnSave.disabled = true;
      return;
    }
    openPath.textContent = file.path;
    if (file.kind === "image") {
      editor.classList.add("hidden");
      imagePreview.classList.remove("hidden");
      imagePreview.innerHTML = "<img alt='' src='" + file.dataUrl + "' />";
      editor.disabled = true;
      btnSave.disabled = true;
      return;
    }
    imagePreview.classList.add("hidden");
    editor.classList.remove("hidden");
    editor.disabled = false;
    editor.value = file.content;
    btnSave.disabled = false;
  }

  function render() {
    renderServers();
    renderCrumbs();
    renderFiles();
    renderEditor();
  }

  editor.addEventListener("input", () => {
    if (state.open && state.open.kind === "text") {
      state.open.content = editor.value;
      openPath.textContent = state.open.path + " •";
    }
  });

  btnSave.onclick = () => {
    if (!state.open || state.open.kind !== "text") return;
    mockFiles[state.open.path] = editor.value;
    openPath.textContent = state.open.path;
    toast("已保存（mock）");
  };

  $("btnUp").onclick = () => {
    state.cwd = parentOf(state.cwd);
    state.open = null;
    render();
  };
  $("btnRefresh").onclick = () => {
    render();
    toast("已刷新");
  };

  function promptName(title, def) {
    const v = window.prompt(title, def || "");
    return v == null ? null : v.trim();
  }

  $("btnNewFile").onclick = () => {
    const name = promptName("文件名", "untitled.txt");
    if (!name) return;
    const path = (state.cwd === "/" ? "" : state.cwd) + "/" + name;
    mockFS[state.cwd] = mockFS[state.cwd] || [];
    mockFS[state.cwd].push({ name, type: "file", path, size: 0 });
    mockFiles[path] = "";
    render();
    toast("已创建 " + path);
  };

  $("btnNewFolder").onclick = () => {
    const name = promptName("目录名", "folder");
    if (!name) return;
    const path = (state.cwd === "/" ? "" : state.cwd) + "/" + name;
    mockFS[state.cwd] = mockFS[state.cwd] || [];
    mockFS[state.cwd].push({ name, type: "dir", path, size: 0 });
    mockFS[path] = [];
    render();
    toast("已创建目录 " + path);
  };

  function fillForm(s) {
    form.name.value = s?.name || "";
    form.host.value = s?.host || "";
    form.port.value = s?.port || 22;
    form.username.value = s?.username || "";
    form.auth.value = s?.auth || "password";
    form.password.value = "";
    form.localRoot.value = s?.mappings?.[0]?.localRoot || "";
    form.remoteRoot.value = s?.mappings?.[0]?.remoteRoot || "";
    form.exclusions.value = (s?.exclusions || []).join(", ");
    form.allow_exec.checked = !!s?.allow_exec;
    $("serverDlgTitle").textContent = s ? "编辑服务器" : "添加服务器";
    form.dataset.id = s?.id || "";
  }

  $("btnAddServer").onclick = () => {
    fillForm(null);
    dlg.showModal();
  };
  $("btnEditServer").onclick = () => {
    const s = state.servers.find((x) => x.id === state.selectedId);
    if (!s) return toast("请先选择服务器", true);
    fillForm(s);
    dlg.showModal();
  };

  form.addEventListener("submit", (e) => {
    const action = e.submitter && e.submitter.value;
    if (action !== "save") return;
    e.preventDefault();
    const id = form.dataset.id || "srv_" + Date.now();
    const payload = {
      id,
      name: form.name.value || form.host.value,
      host: form.host.value,
      port: Number(form.port.value) || 22,
      username: form.username.value,
      auth: form.auth.value,
      default: form.dataset.id ? state.servers.find((s) => s.id === id)?.default : state.servers.length === 0,
      mappings:
        form.localRoot.value && form.remoteRoot.value
          ? [{ localRoot: form.localRoot.value, remoteRoot: form.remoteRoot.value }]
          : [],
      exclusions: form.exclusions.value
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      allow_exec: form.allow_exec.checked
    };
    const idx = state.servers.findIndex((s) => s.id === id);
    if (idx >= 0) state.servers[idx] = { ...state.servers[idx], ...payload };
    else state.servers.push(payload);
    state.selectedId = id;
    dlg.close();
    render();
    toast("服务器已保存（mock）");
  });

  $("btnTest").onclick = () => {
    toast("连接成功 · hostname demo-prod（mock）");
  };
  $("btnDefault").onclick = () => {
    state.servers.forEach((s) => {
      s.default = s.id === state.selectedId;
    });
    render();
    toast("已设为默认");
  };

  render();
})();
