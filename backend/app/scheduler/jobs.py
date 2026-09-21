import structlog

from app.telegram.bot import get_telegram_app
from app.providers.llm_provider import get_llm_provider
from app.memory.checkpoints import CheckpointManager
from app.api.telemetry_bus import telemetry_bus

logger = structlog.get_logger(__name__)

async def execute_alert_job(chat_id: int, message: str) -> None:
    """
    Sends a direct text notification to the user without invoking the LLM.
    """
    logger.info("Executing alert job", chat_id=chat_id)
    await telemetry_bus.publish("cron_alert", {"chat_id": chat_id, "message": message})
    
    app = get_telegram_app()
    if not app:
        logger.info("Telegram App is not initialized, alert recorded to telemetry only.")
        return
        
    try:
        await app.bot.send_message(chat_id=chat_id, text=f"🔔 *Automated Alert*\n\n{message}", parse_mode="Markdown")
    except Exception as e:
        logger.error("Failed to send alert job", error=str(e), chat_id=chat_id)


async def execute_agent_task_job(chat_id: int, label: str, task_prompt: str) -> None:
    """
    Bootstraps an AgentTurn for a background task, leveraging tools and memory, 
    and sends the final result back to the user.
    """
    logger.info("Executing agent task job", chat_id=chat_id, label=label)
    await telemetry_bus.publish("cron_task_start", {"chat_id": chat_id, "label": label, "task_prompt": task_prompt})
    
    app = get_telegram_app()
    session_id = f"tg-sess-{chat_id}" if chat_id else f"cron-sess-{label}"
    
    # 1. Provide task prompt as 'user' turn but tagged with cron logic in text
    injected_prompt = f"[CRON INVOCATION: {label}]\n{task_prompt}"
    
    # 2. Append to memory natively
    await CheckpointManager.append_turn(session_id, "user", injected_prompt)
    
    # 3. Retrieve history context
    history = await CheckpointManager.get_recent_checkpoints(session_id)
    messages = [{"role": h["role"], "content": h["content"]} for h in history]
    
    try:
        from app.orchestrator.turn import AgentTurn
        provider = get_llm_provider()
        turn = AgentTurn(provider=provider)
        
        result = await turn.execute(messages)
        assistant_content = result.get("content", "Task completed without output.")
        
        # Tag response appropriately
        await CheckpointManager.append_turn(session_id, "assistant", assistant_content)
        
        await telemetry_bus.publish("cron_task_complete", {
            "chat_id": chat_id,
            "label": label,
            "content": assistant_content
        })
        
        # Send to user if Telegram is active
        if app and chat_id:
            await app.bot.send_message(chat_id=chat_id, text=f"🤖 *Task Update:* {label}\n\n{assistant_content}", parse_mode="Markdown")
        
        # Checkpoint compaction
        await CheckpointManager.compact_overflow_turns(session_id, provider)

    except Exception as e:
        logger.error("Agent task job failed", label=label, error=str(e))
        await telemetry_bus.publish("cron_task_error", {"label": label, "error": str(e)})
        # Degraded failure mode alert
        if app and chat_id:
            try:
                degraded_msg = f"⚠️ *Scheduled task '{label}' failed: brain offline*\nError: {str(e)}"
                await app.bot.send_message(chat_id=chat_id, text=degraded_msg, parse_mode="Markdown")
            except Exception as inner_e:
                logger.error("Failed to send degraded mode alert", error=str(inner_e))
