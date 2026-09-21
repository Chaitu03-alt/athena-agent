"""Sandboxed file operations with workspace jailing and atomic write semantics."""

import os
import uuid
from pathlib import Path
import structlog

from app.tools.registry import register_tool
from app.tools.workspace import resolve_jail_path, ToolSecurityError

logger = structlog.get_logger(__name__)


@register_tool(
    name="file_read",
    description="Read content from a file inside the sandboxed workspace.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative file path inside the workspace.",
            },
        },
        "required": ["path"],
    },
)
def file_read(path: str) -> str:
    """Safely read text content of a file located within the workspace jail."""
    target_path = resolve_jail_path(path)

    if not target_path.exists():
        raise FileNotFoundError(f"File not found: '{path}'")
    if not target_path.is_file():
        raise IsADirectoryError(f"Target '{path}' is a directory, not a file.")

    return target_path.read_text(encoding="utf-8")


@register_tool(
    name="file_write",
    description="Atomically write text content to a file inside the sandboxed workspace.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative file path inside the workspace.",
            },
            "content": {
                "type": "string",
                "description": "Text content to write into the file.",
            },
        },
        "required": ["path", "content"],
    },
)
def file_write(path: str, content: str) -> str:
    """Atomically write text content to a file inside the workspace jail."""
    target_path = resolve_jail_path(path)

    # Ensure parent directory exists within the workspace
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Temporary file inside the same parent directory to ensure atomic os.replace
    temp_filename = f".{target_path.name}.tmp_{uuid.uuid4().hex}"
    temp_path = target_path.parent / temp_filename

    try:
        temp_path.write_text(content, encoding="utf-8")
        # Atomic replace
        os.replace(temp_path, target_path)
    finally:
        # Cleanup temporary file if replace failed
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass

    return f"Successfully wrote {len(content)} characters to '{path}'."
