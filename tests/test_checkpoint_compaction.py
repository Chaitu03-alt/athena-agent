import pytest
from app.db.connection import init_db
from app.memory.checkpoints import CheckpointManager
from app.providers.base import LLMProvider, LLMResponse

class MockLLMProvider(LLMProvider):
    async def complete(self, messages, tools=None, **kwargs) -> LLMResponse:
        return LLMResponse(content="Mocked summary of older turns.")

@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch, tmp_path):
    test_db_path = tmp_path / "test_athena_checkpoints.db"
    monkeypatch.setenv("SQLITE_DB_PATH", str(test_db_path))
    init_db()
    
    yield
    
    if test_db_path.exists():
        test_db_path.unlink()

@pytest.mark.asyncio
async def test_checkpoint_append_and_get():
    """
    Test basic append and retrieve functionality.
    """
    session_id = "sess-123"
    await CheckpointManager.append_turn(session_id, "user", "Hello")
    await CheckpointManager.append_turn(session_id, "assistant", "Hi there")
    
    recent = await CheckpointManager.get_recent_checkpoints(session_id, limit=10)
    assert len(recent) == 2
    assert recent[0]["role"] == "user"
    assert recent[1]["role"] == "assistant"

@pytest.mark.asyncio
async def test_checkpoint_compaction_trigger():
    """
    Test that when turns exceed MAX_TURNS, the oldest are summarized and pruned.
    """
    session_id = "sess-compact"
    
    # MAX_TURNS is 20. We will insert 25.
    for i in range(25):
        await CheckpointManager.append_turn(session_id, "user", f"Message {i}")
        
    mock_llm = MockLLMProvider()
    
    # Trigger compaction
    await CheckpointManager.compact_overflow_turns(session_id, mock_llm)
    
    # We expect: 25 total - 15 pruned = 10 kept pristine + 1 summary = 11 rows total
    recent = await CheckpointManager.get_recent_checkpoints(session_id, limit=50)
    
    assert len(recent) == 11
    
    # First row should be the summary
    assert recent[0]["is_summary"] == 1
    assert recent[0]["content"] == "Mocked summary of older turns."
    assert recent[0]["role"] == "system"
    
    # Next rows should be Message 15 to Message 24
    assert recent[1]["content"] == "Message 15"
    assert recent[-1]["content"] == "Message 24"
