"""LLM-facing tool schemas for ssh-plugin."""

SSH_LIST_SERVERS = {
    "name": "ssh_list_servers",
    "description": (
        "List configured SSH deployment servers. "
        "By default host/username are masked (***); set unmask=true only when the operator explicitly needs the real endpoint."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "unmask": {
                "type": "boolean",
                "description": "If true, return real host/username (still no passwords). Default false.",
            }
        },
        "required": [],
    },
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
    "description": (
        "Create or overwrite a remote text file over SFTP. "
        "Pass dryRun=true to preview a unified diff without writing. Prefer dryRun before production overwrites."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "server": {"type": "string"},
            "path": {"type": "string"},
            "content": {"type": "string", "description": "Full file content (UTF-8)"},
            "dryRun": {"type": "boolean", "description": "If true, only compute the diff"},
        },
        "required": ["server", "path", "content"],
    },
}

SSH_MAP_PATH = {
    "name": "ssh_map_path",
    "description": (
        "Translate a path using the server's PyCharm-style mappings. "
        "direction=local_to_remote or remote_to_local."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "server": {"type": "string"},
            "path": {"type": "string"},
            "direction": {
                "type": "string",
                "description": "local_to_remote | remote_to_local",
            },
        },
        "required": ["server", "path"],
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
        "Upload a local file over SFTP. remotePath optional if the local path sits under a mapping. "
        "dryRun=true returns the resolved remote path without writing."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "server": {"type": "string"},
            "localPath": {"type": "string"},
            "remotePath": {"type": "string"},
            "dryRun": {"type": "boolean"},
        },
        "required": ["server", "localPath"],
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

SSH_HEALTH = {
    "name": "ssh_health",
    "description": (
        "Probe SSH connectivity for a server (keep-alive pool, latency). "
        "Call this before a long iteration loop and after connection errors."
    ),
    "parameters": {
        "type": "object",
        "properties": {"server": {"type": "string", "description": "Server name or id"}},
        "required": ["server"],
    },
}

ALL_SCHEMAS = [
    SSH_LIST_SERVERS,
    SSH_HEALTH,
    SSH_LS,
    SSH_READ_FILE,
    SSH_WRITE_FILE,
    SSH_MAP_PATH,
    SSH_MKDIR,
    SSH_DELETE,
    SSH_UPLOAD,
    SSH_DOWNLOAD,
    SSH_EXEC,
]
