import psutil
import time
import asyncio
from typing import Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.api.telemetry_bus import telemetry_bus
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter()

# Global state tracker
_AGENT_STATE = {
    "status": "idle",
    "last_activity": time.time(),
    "current_task": None
}

def set_agent_state(status: str, task: str = None):
    _AGENT_STATE["status"] = status
    _AGENT_STATE["current_task"] = task
    _AGENT_STATE["last_activity"] = time.time()

@router.get("/state", tags=["Telemetry"])
async def get_state() -> Dict[str, Any]:
    """Returns the current agent status."""
    return _AGENT_STATE

@router.get("/resources", tags=["Telemetry"])
async def get_resources() -> Dict[str, Any]:
    """Returns system resources (CPU and RAM) for the HUD."""
    mem = psutil.virtual_memory()
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "ram_mb_used": mem.used / (1024 * 1024),
        "ram_percent": mem.percent,
        "uptime_seconds": time.time() - psutil.boot_time()
    }

@router.websocket("/ws")
async def websocket_telemetry(websocket: WebSocket):
    """
    Live streaming WebSocket connection with auto-ping/pong.
    Subscribes to the TelemetryBus and streams events to the Cyberpunk HUD.
    """
    await websocket.accept()
    logger.info("WebSocket telemetry client connected.")
    
    subscription = telemetry_bus.subscribe()
    
    try:
        # We run a loop that waits for events from the subscription
        # and concurrently listens for messages from the client (for pings or disconnects).
        async for event_json in subscription:
            await websocket.send_text(event_json)
    except WebSocketDisconnect:
        logger.info("WebSocket telemetry client disconnected natively.")
    except Exception as e:
        logger.warning("WebSocket telemetry connection closed with error", error=str(e))
    finally:
        # The generator will cleanup the queue upon cancellation
        pass
