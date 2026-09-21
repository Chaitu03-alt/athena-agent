"""Tests for Workspace Jail Sandbox and Sandboxed File Tools."""

import os
from pathlib import Path
import pytest

from app.tools.workspace import resolve_jail_path, ToolSecurityError, get_workspace_dir
from app.tools.builtin.file_ops import file_write, file_read


def test_path_traversal_prevention():
    """Verify that any path attempting to escape ./workspace/ raises ToolSecurityError."""
    traversal_attempts = [
        "../outside.txt",
        "../../etc/passwd",
        "..\\windows\\system32\\cmd.exe",
        "nested/../../secret.env",
        "/etc/shadow",
        "C:\\Windows\\System32\\calc.exe",
        "sub/../../../escaped.txt",
    ]

    for bad_path in traversal_attempts:
        with pytest.raises(ToolSecurityError):
            resolve_jail_path(bad_path)


def test_disallowed_extensions():
    """Verify that dangerous and executable file extensions are rejected."""
    bad_files = [
        "payload.exe",
        "install.bat",
        "setup.cmd",
        "script.sh",
        "deploy.ps1",
        "binary.dll",
        "lib.so",
        "run.vbs",
        "bytecode.pyc",
    ]

    for bad_file in bad_files:
        with pytest.raises(ToolSecurityError) as exc_info:
            resolve_jail_path(bad_file)
        assert "disallowed" in str(exc_info.value).lower()


def test_safe_file_write_and_read():
    """Verify safe write and read operations inside the workspace jail."""
    test_file = "test_data/notes.txt"
    content = "Athena Agent Phase 1: Hermes Upgrade Active."

    write_result = file_write(test_file, content)
    assert "Successfully wrote" in write_result

    read_content = file_read(test_file)
    assert read_content == content


def test_atomic_write_integrity():
    """Verify that file_write performs an atomic write and leaves no orphaned temp files."""
    test_file = "nested/atomic/state.json"
    content = '{"status": "ok", "phase": 1}'

    file_write(test_file, content)
    assert file_read(test_file) == content

    # Check that the file exists and content matches
    target_path = resolve_jail_path(test_file)
    assert target_path.exists()
    assert target_path.read_text(encoding="utf-8") == content

    # Verify no dangling temp files remain in directory
    parent_files = list(target_path.parent.iterdir())
    for f in parent_files:
        assert not f.name.endswith(".tmp") and ".tmp_" not in f.name


def test_file_read_nonexistent_raises():
    """Verify file_read on non-existent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        file_read("does_not_exist_12345.txt")


@pytest.mark.asyncio
async def test_tool_registry_and_web_search_spec():
    """Verify builtin tools are registered in TOOL_REGISTRY with valid OpenAI schemas."""
    from app.tools.registry import TOOL_REGISTRY, get_registered_tools
    from app.tools.builtin.web_search import web_search

    assert "web_search" in TOOL_REGISTRY
    assert "file_read" in TOOL_REGISTRY
    assert "file_write" in TOOL_REGISTRY

    specs = get_registered_tools()
    names = [s["function"]["name"] for s in specs]
    assert "web_search" in names
    assert "file_read" in names
    assert "file_write" in names

