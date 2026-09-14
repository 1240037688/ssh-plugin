"""LLM-facing tool schemas for ssh-plugin."""

SSH_LIST_SERVERS = {
    "name": "ssh_list_servers",
    "description": "List configured SSH deployment servers (no secrets). Use before other ssh_* tools to pick a server name or id.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}

SSH_LS = {
    "name": "ssh_ls",
    "description": "List a remote directory over SFTP. Returns names, types, sizes, mtimes.",
    "parameters": {
        "type": "object",
        "properties": {
            "server": {"type": "string", "description": "Server name or id from ssh_list_servers"},
            "path": {"type": "string", "description": "Absolute remote directory path, e.g. /var/www"},
        },
        "required": ["server", "path"],
    },
}

SSH_READ_FILE = {
    "name": "ssh_read_file",
    "description": "Read a remote text file over SFTP (UTF-8, size-capped).",
    "parameters": {
        "type": "object",
        "properties": {
            "server": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": ["server", "path"],
    },
}

SSH_WRITE_FILE = {
    "name": "ssh_write_file",
    "description": "Create or overwrite a remote text file over SFTP. Parent directories are created if missing.",
    "parameters": {
        "type": "object",
        "properties": {
            "server": {"type": "string"},
            "path": {"type": "string"},
            "content": {"type": "string", "description": "Full file content (UTF-8)"},
        },
        "required": ["server", "path", "content"],
    },
}

SSH_MKDIR = {
    "name": "ssh_mkdir",
    "description": "Create a remote directory over SFTP.",
    "parameters": {
        "type": "object",
        "properties": {"server": {"type": "string"}, "path": {"type": "string"}},
        "required": ["server", "path"],
    },
}

SSH_DELETE = {
    "name": "ssh_delete",
    "description": "Delete a remote file or directory over SFTP. Directories require recursive=true.",
    "parameters": {
        "type": "object",
        "properties": {
            "server": {"type": "string"},
            "path": {"type": "string"},
            "recursive": {"type": "boolean", "description": "Delete directory trees"},
        },
        "required": ["server", "path"],
    },
}

SSH_UPLOAD = {
    "name": "ssh_upload",
    "description": (
        "Upload a local file to a remote path over SFTP. "
        "Local path must stay under process cwd or the server's allowedLocalPaths."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "server": {"type": "string"},
            "localPath": {"type": "string"},
            "remotePath": {"type": "string"},
        },
        "required": ["server", "localPath", "remotePath"],
    },
}

SSH_DOWNLOAD = {
    "name": "ssh_download",
    "description": (
        "Download a remote file to a local path over SFTP. "
        "Local path must stay under process cwd or the server's allowedLocalPaths."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "server": {"type": "string"},
            "remotePath": {"type": "string"},
            "localPath": {"type": "string"},
        },
        "required": ["server", "remotePath", "localPath"],
    },
}

SSH_EXEC = {
    "name": "ssh_exec",
    "description": (
        "Run a shell command on a remote server. "
        "Requires allow_exec. When commandWhitelist is set, the full command must match "
        "and may not contain shell control characters (; & | ` < > $() or newlines). "
        "commandBlacklist rejects matching commands."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "server": {"type": "string"},
            "command": {"type": "string"},
            "timeout": {"type": "integer", "description": "Seconds, default 30"},
        },
        "required": ["server", "command"],
    },
}

ALL_SCHEMAS = [
    SSH_LIST_SERVERS,
    SSH_LS,
    SSH_READ_FILE,
    SSH_WRITE_FILE,
    SSH_MKDIR,
    SSH_DELETE,
    SSH_UPLOAD,
    SSH_DOWNLOAD,
    SSH_EXEC,
]
