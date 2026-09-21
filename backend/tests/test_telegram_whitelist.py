import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.db.connection import init_db, execute_read_async
from app.telegram.whitelist import WhitelistGuard
from app.telegram.handlers import handle_message, chunk_and_send

@pytest.fixture(autouse=True)
def setup_test_db_telegram(monkeypatch, tmp_path):
    test_db_path = tmp_path / "test_athena_telegram.db"
    monkeypatch.setenv("SQLITE_DB_PATH", str(test_db_path))
    init_db()
    
    yield
    
    if test_db_path.exists():
        test_db_path.unlink()

@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.bot = AsyncMock()
    ctx.bot.send_message = AsyncMock()
    ctx.bot.send_chat_action = AsyncMock()
    return ctx

@pytest.fixture
def build_update():
    def _builder(user_id: int, text: str = "Hello"):
        update = MagicMock()
        update.effective_user.id = user_id
        update.effective_chat.id = user_id * 10
        update.message.text = text
        update.to_dict.return_value = {"message": {"text": text}, "user_id": user_id}
        return update
    return _builder

@pytest.mark.asyncio
async def test_ghost_mode_unauthorized_drop(mock_context, build_update, monkeypatch):
    """
    Test that unauthorized user gets completely ignored and logged to dropped_messages.
    """
    with patch("app.telegram.whitelist.settings") as mock_settings:
        mock_settings.TELEGRAM_ALLOWED_USER_IDS = "1111,2222"
        await WhitelistGuard.initialize()
    
    # 9999 is unauthorized
    update = build_update(9999, "Sneaky prompt")
    
    await handle_message(update, mock_context)
    
    # Assert no messages were sent back (Ghost Mode)
    mock_context.bot.send_message.assert_not_called()
    mock_context.bot.send_chat_action.assert_not_called()
    
    # Assert logged to database
    rows = await execute_read_async("SELECT raw_payload, reason FROM dropped_messages")
    assert len(rows) == 1
    assert "9999" in rows[0]["reason"]
    assert "Sneaky prompt" in rows[0]["raw_payload"]

@pytest.mark.asyncio
async def test_authorized_user_allowed(mock_context, build_update, monkeypatch):
    """
    Test that an authorized user successfully passes the guard and triggers the AgentTurn.
    """
    with patch("app.telegram.whitelist.settings") as mock_settings:
        mock_settings.TELEGRAM_ALLOWED_USER_IDS = "1111,2222"
        await WhitelistGuard.initialize()
    
    update = build_update(1111, "Hello Athena")
    
    # We mock AgentTurn.execute to return a standard result
    with patch("app.orchestrator.turn.AgentTurn") as MockTurn:
        mock_turn_instance = AsyncMock()
        mock_turn_instance.execute.return_value = {"content": "Hello user, I am Athena."}
        MockTurn.return_value = mock_turn_instance
        
        await handle_message(update, mock_context)
        
        # Verify AgentTurn was executed
        mock_turn_instance.execute.assert_called_once()
        
        # Verify reply was sent
        mock_context.bot.send_message.assert_called_once()
        args, kwargs = mock_context.bot.send_message.call_args
        assert kwargs["text"] == "Hello user, I am Athena."
        assert kwargs["chat_id"] == 11110

@pytest.mark.asyncio
async def test_chunk_and_send(mock_context):
    """
    Test the >4096 character safety chunking.
    """
    # Create text exactly 5000 chars, made of 5 paragraphs of 1000 chars
    p = "A" * 1000
    long_text = f"{p}\n{p}\n{p}\n{p}\n{p}"  # 5004 chars roughly
    
    await chunk_and_send(1234, long_text, mock_context)
    
    # Expected chunks:
    # Chunk 1: p \n p \n p \n p -> 4003 chars
    # Chunk 2: p -> 1000 chars
    
    assert mock_context.bot.send_message.call_count == 2
    
    call_1 = mock_context.bot.send_message.call_args_list[0][1]["text"]
    call_2 = mock_context.bot.send_message.call_args_list[1][1]["text"]
    
    assert len(call_1) <= 4096
    assert len(call_2) <= 4096
    assert call_1.startswith("A")
    assert call_2.startswith("A")
    
@pytest.mark.asyncio
async def test_chunk_and_send_giant_paragraph(mock_context):
    """
    Test fallback chunking when a single paragraph is > 4096 characters without any newlines.
    """
    giant_text = "B" * 5000
    
    await chunk_and_send(1234, giant_text, mock_context)
    
    assert mock_context.bot.send_message.call_count == 2
    
    call_1 = mock_context.bot.send_message.call_args_list[0][1]["text"]
    call_2 = mock_context.bot.send_message.call_args_list[1][1]["text"]
    
    assert len(call_1) == 4096
    assert len(call_2) == 5000 - 4096
