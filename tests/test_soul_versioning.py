import os
import pytest
import sqlite3
from pathlib import Path
from app.db.connection import get_connection, init_db, execute_write_async
from app.memory.soul import SoulPromptManager

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch, tmp_path):
    """
    Sets up a temporary SQLite database for testing to avoid polluting real data.
    """
    test_db_path = tmp_path / "test_athena.db"
    monkeypatch.setenv("SQLITE_DB_PATH", str(test_db_path))
    
    # Initialize schema
    init_db()
    
    yield
    
    # Teardown logic
    if test_db_path.exists():
        test_db_path.unlink()

@pytest.mark.asyncio
async def test_soul_versioning_transaction():
    """
    Test that setting a new soul prompt flips the old one to inactive and sets the new to active.
    """
    id1 = await SoulPromptManager.set_soul_prompt("First prompt")
    active1 = await SoulPromptManager.get_active_soul()
    
    assert active1 is not None
    assert active1["prompt_text"] == "First prompt"
    assert active1["id"] == id1

    # Set new
    id2 = await SoulPromptManager.set_soul_prompt("Second prompt")
    active2 = await SoulPromptManager.get_active_soul()
    
    assert active2 is not None
    assert active2["prompt_text"] == "Second prompt"
    assert active2["id"] == id2
    assert id1 != id2
    
    # Verify history
    history = await SoulPromptManager.get_version_history()
    assert len(history) == 2
    
    # Check states in history
    for item in history:
        if item["id"] == id2:
            assert item["is_active"] == 1
        elif item["id"] == id1:
            assert item["is_active"] == 0

@pytest.mark.asyncio
async def test_soul_partial_unique_index(monkeypatch):
    """
    Verify the SQLite partial unique index prevents two active rows via raw SQL insert.
    """
    # Insert one active row manually
    await execute_write_async("INSERT INTO soul_prompts (id, prompt_text, is_active) VALUES ('123', 'raw text', 1)")
    
    # Attempting to insert a second active row should fail with IntegrityError
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        await execute_write_async("INSERT INTO soul_prompts (id, prompt_text, is_active) VALUES ('456', 'raw text 2', 1)")
