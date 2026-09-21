"""Workspace sandbox jailing and path traversal defense."""

import os
from pathlib import Path
from typing import Set, Union
from app.config import settings


class ToolSecurityError(Exception):
    """Raised when a tool operation violates sandbox constraints or attempts path traversal."""
    pass


# Disallowed extensions: executables, binary blobs, and script execution vectors
DISALLOWED_EXTENSIONS: Set[str] = {
    ".exe", ".dll", ".so", ".dylib", ".bin",
    ".bat", ".cmd", ".sh", ".bash", ".zsh", ".ps1", ".vbs",
    ".com", ".scr", ".msi", ".jar", ".app",
    ".pyc", ".pyd",
}


def get_workspace_dir() -> Path:
    """Return canonical path to the workspace directory."""
    workspace = settings.resolved_workspace_dir.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def resolve_jail_path(relative_path: Union[str, Path]) -> Path:
    """
    Canonicalize and validate that the requested path strictly resides within WORKSPACE_DIR.

    Raises:
        ToolSecurityError: If the path attempts traversal, escapes the jail,
                           contains null bytes, or has a disallowed extension.
    """
    raw_str = str(relative_path).strip()
    if not raw_str:
        raise ToolSecurityError("Path cannot be empty.")

    # Guard against null-byte injection
    if "\0" in raw_str:
        raise ToolSecurityError("Path contains illegal null bytes.")

    workspace = get_workspace_dir()

    # Reject traversal tokens
    parts = Path(raw_str).parts
    if ".." in parts:
        raise ToolSecurityError(f"Access denied: path traversal attempt detected in '{raw_str}'.")

    # Resolve target
    target = Path(raw_str)
    if not target.is_absolute():
        target = (workspace / target).resolve()
    else:
        target = target.resolve()

    # Canonical check: target must be strictly relative to workspace
    try:
        target.relative_to(workspace)
    except ValueError:
        raise ToolSecurityError(
            f"Access denied: path '{raw_str}' resolves outside workspace jail ('{workspace}')."
        )

    # Disallowed extension check
    suffix = target.suffix.lower()
    if suffix in DISALLOWED_EXTENSIONS:
        raise ToolSecurityError(
            f"Access denied: file extension '{suffix}' is disallowed in sandbox."
        )

    return target
