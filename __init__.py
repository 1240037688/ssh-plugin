"""ssh-plugin — Hermes unified package registration (agent half)."""

from __future__ import annotations

import logging
from pathlib import Path

from . import schemas, tools

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    """Wire schemas to handlers and bundle the skill."""
    pairs = [
        (schemas.SSH_LIST_SERVERS, tools.ssh_list_servers),
        (schemas.SSH_HEALTH, tools.ssh_health),
        (schemas.SSH_LS, tools.ssh_ls),
        (schemas.SSH_READ_FILE, tools.ssh_read_file),
        (schemas.SSH_WRITE_FILE, tools.ssh_write_file),
        (schemas.SSH_MAP_PATH, tools.ssh_map_path),
        (schemas.SSH_MKDIR, tools.ssh_mkdir),
        (schemas.SSH_DELETE, tools.ssh_delete),
        (schemas.SSH_UPLOAD, tools.ssh_upload),
        (schemas.SSH_DOWNLOAD, tools.ssh_download),
        (schemas.SSH_SYNC, tools.ssh_sync),
        (schemas.SSH_EXEC, tools.ssh_exec),
    ]
    for schema, handler in pairs:
        ctx.register_tool(
            name=schema["name"],
            toolset="ssh_plugin",
            schema=schema,
            handler=handler,
        )

    skills_dir = Path(__file__).parent / "skills"
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            skill_md = child / "SKILL.md"
            if child.is_dir() and skill_md.exists():
                try:
                    ctx.register_skill(child.name, skill_md)
                except Exception as exc:  # non-fatal
                    logger.warning("failed to register skill %s: %s", child.name, exc)
