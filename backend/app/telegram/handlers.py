import json
import uuid
import structlog
from telegram import Update
from telegram.ext import ContextTypes

from app.telegram.whitelist import WhitelistGuard
from app.db.connection import execute_write_async
from app.providers.llm_provider import get_llm_provider
from app.memory.checkpoints import CheckpointManager

logger = structlog.get_logger(__name__)

async def drop_unauthorized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Checks the whitelist guard. If unauthorized, logs to dropped_messages and returns True (indicating handled/dropped).
    """
    user_id = update.effective_user.id if update.effective_user else 0
    if not WhitelistGuard.is_authorized(user_id):
        # Ghost mode: silent drop, log it
        payload = json.dumps(update.to_dict()) if update else ""
        reason = f"Unauthorized user_id: {user_id}"
        drop_id = uuid.uuid4().hex
        
        query = """
        INSERT INTO dropped_messages (id, reason, raw_payload)
        VALUES (?, ?, ?)
        """
        try:
            await execute_write_async(query, (drop_id, reason, payload))
            logger.warning("Ghost mode drop", user_id=user_id, drop_id=drop_id)
        except Exception as e:
            logger.error("Failed to log dropped message", error=str(e))
            
        return True
    return False


async def chunk_and_send(chat_id: int, text: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Safely splits LLM output > 4096 chars by newlines/paragraphs and sends chunks.
    """
    if not text:
        return
        
    MAX_LENGTH = 4096
    
    # Simple chunking by paragraphs/newlines
    paragraphs = text.split('\n')
    current_chunk = ""
    
    for p in paragraphs:
        # If a single paragraph is larger than MAX_LENGTH, we forcefully chunk it (edge case)
        if len(p) > MAX_LENGTH:
            if current_chunk:
                await context.bot.send_message(chat_id=chat_id, text=current_chunk.strip())
                current_chunk = ""
            # Force chunk the giant paragraph
            for i in range(0, len(p), MAX_LENGTH):
                await context.bot.send_message(chat_id=chat_id, text=p[i:i+MAX_LENGTH])
        else:
            if len(current_chunk) + len(p) + 1 > MAX_LENGTH:
                await context.bot.send_message(chat_id=chat_id, text=current_chunk.strip())
                current_chunk = p + "\n"
            else:
                current_chunk += p + "\n"
                
    if current_chunk.strip():
        await context.bot.send_message(chat_id=chat_id, text=current_chunk.strip())


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Main entrypoint for regular text messages.
    """
    if await drop_unauthorized(update, context):
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text
    session_id = f"tg-sess-{chat_id}"
    
    # 1. Save user turn
    await CheckpointManager.append_turn(session_id, "user", user_text)
    
    # 2. Get history
    history = await CheckpointManager.get_recent_checkpoints(session_id)
    
    # 3. Format for LLM
    messages = []
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
        
    # 4. Agent pipeline
    from app.orchestrator.turn import AgentTurn
    provider = get_llm_provider()
    turn = AgentTurn(provider=provider)
    
    try:
        # Show typing indicator
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
        result = await turn.execute(messages)
        assistant_content = result.get("content", "Error: No content returned")
        
        # 5. Save assistant turn
        await CheckpointManager.append_turn(session_id, "assistant", assistant_content)
        
        # 6. Send chunked reply
        await chunk_and_send(chat_id, assistant_content, context)
        
        # 7. Check if we need to compact
        await CheckpointManager.compact_overflow_turns(session_id, provider)
        
    except Exception as e:
        logger.error("Agent pipeline failed", error=str(e))
        await context.bot.send_message(chat_id=chat_id, text=f"Pipeline Error: {str(e)}")
