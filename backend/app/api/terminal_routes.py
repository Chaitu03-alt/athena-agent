from typing import Dict, Any
from fastapi import APIRouter
from pydantic import BaseModel
import structlog
import uuid

from app.orchestrator.turn import AgentTurn
from app.providers.llm_provider import get_llm_provider
from app.memory.checkpoints import CheckpointManager
from app.memory.soul import SoulPromptManager
from app.api.telemetry_routes import set_agent_state
from app.api.telemetry_bus import telemetry_bus

logger = structlog.get_logger(__name__)

router = APIRouter()

class TerminalRequest(BaseModel):
    text: str

class TerminalResponse(BaseModel):
    content: str
    tool_calls_count: int

@router.post("/execute", response_model=TerminalResponse, tags=["Terminal"])
async def execute_terminal_command(req: TerminalRequest) -> TerminalResponse:
    """
    Executes a web terminal command through the identical sandboxed AgentTurn pipeline as Telegram.
    Broadcasts live events to the telemetry bus.
    """
    session_id = "hud-terminal"
    prompt = req.text
    
    set_agent_state("thinking", task=prompt)
    await telemetry_bus.publish("turn_start", {"session_id": session_id, "prompt": prompt})
    
    try:
        # 1. Append user turn
        await CheckpointManager.append_turn(session_id, "user", prompt)
        
        # 2. Retrieve history context
        history = await CheckpointManager.get_recent_checkpoints(session_id)
        messages = [{"role": h["role"], "content": h["content"]} for h in history]
        
        # 3. Execute
        provider = get_llm_provider()
        turn = AgentTurn(provider=provider)
        
        active_soul = await SoulPromptManager.get_active_soul(default_if_none=True)
        system_prompt = active_soul["prompt_text"] if active_soul else None
        
        result = await turn.execute(messages, system_prompt=system_prompt)
        assistant_content = result.get("content", "Task completed without output.")
        tool_calls_count = result.get("tool_calls_count", 0)
        
        # 4. Append assistant turn
        await CheckpointManager.append_turn(session_id, "assistant", assistant_content)
        
        # 5. Compaction
        await CheckpointManager.compact_overflow_turns(session_id, provider)
        
        await telemetry_bus.publish("turn_complete", {
            "session_id": session_id, 
            "content": assistant_content,
            "tool_calls_count": tool_calls_count
        })
        
        return TerminalResponse(
            content=assistant_content,
            tool_calls_count=tool_calls_count
        )
        
    except Exception as e:
        logger.error("Terminal execution failed", error=str(e))
        error_msg = f"Terminal Error: {str(e)}"
        await telemetry_bus.publish("turn_error", {"session_id": session_id, "error": error_msg})
        return TerminalResponse(
            content=error_msg,
            tool_calls_count=0
        )
    finally:
        set_agent_state("idle")
