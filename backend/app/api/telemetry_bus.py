import asyncio
import json
import uuid
import structlog
from typing import AsyncGenerator, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime, timezone

from app.db.connection import execute_write_async

logger = structlog.get_logger(__name__)

class TelemetryEvent(BaseModel):
    id: str
    event_type: str
    payload: Dict[str, Any]
    timestamp: str

class TelemetryBus:
    """In-process pub/sub manager using asyncio.Queue for broadcasting events to WebSocket clients."""
    
    def __init__(self):
        self._queues: List[asyncio.Queue] = []
        
    async def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Publishes an event to all connected subscribers and persists it to the database."""
        event = TelemetryEvent(
            id=uuid.uuid4().hex,
            event_type=event_type,
            payload=payload,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        # 1. Distribute to in-memory queues (WebSocket clients)
        for q in self._queues:
            try:
                # non-blocking put, discard if client queue is full to avoid blocking agent turns
                q.put_nowait(event.model_dump_json())
            except asyncio.QueueFull:
                logger.warning("Subscriber queue is full, dropping telemetry event.")
        
        # 2. Persist to DB for history
        try:
            await execute_write_async(
                "INSERT INTO telemetry_events (id, event_type, event_data) VALUES (?, ?, ?)",
                (event.id, event.event_type, json.dumps(payload))
            )
        except Exception as e:
            logger.error("Failed to persist telemetry event", error=str(e))

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """Yields events from a newly created queue. Used by WebSocket handlers."""
        q = asyncio.Queue(maxsize=100)
        self._queues.append(q)
        try:
            while True:
                # wait for events
                event_json = await q.get()
                yield event_json
                q.task_done()
        except asyncio.CancelledError:
            pass
        finally:
            self._queues.remove(q)

# Global singleton
telemetry_bus = TelemetryBus()
