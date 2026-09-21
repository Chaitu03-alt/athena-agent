from telegram import Update
from telegram.ext import ContextTypes

from app.telegram.handlers import drop_unauthorized, chunk_and_send
from app.memory.checkpoints import CheckpointManager
from app.db.connection import execute_write_async

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command."""
    if await drop_unauthorized(update, context):
        return
        
    await update.message.reply_text("Athena Agent initialized and ready. Ghost Mode active.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /status command."""
    if await drop_unauthorized(update, context):
        return
        
    await update.message.reply_text("Status: Online.\nPhase: 3 - Telegram Gateway Active.")


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /reset command to clear the current chat's checkpoint memory."""
    if await drop_unauthorized(update, context):
        return
        
    chat_id = update.effective_chat.id
    session_id = f"tg-sess-{chat_id}"
    
    # Simple hard reset: delete all checkpoints for this session
    query = "DELETE FROM checkpoints WHERE session_id = ?"
    await execute_write_async(query, (session_id,))
    
    await update.message.reply_text("Session memory has been reset.")


async def memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /memory command to print out the current checkpoint size."""
    if await drop_unauthorized(update, context):
        return
        
    chat_id = update.effective_chat.id
    session_id = f"tg-sess-{chat_id}"
    
    history = await CheckpointManager.get_recent_checkpoints(session_id, limit=50)
    
    count = len(history)
    summaries = sum(1 for h in history if h.get("is_summary") == 1)
    
    text = f"Current Session Memory:\n- Total Turns: {count}\n- Summaries: {summaries}"
    await update.message.reply_text(text)
