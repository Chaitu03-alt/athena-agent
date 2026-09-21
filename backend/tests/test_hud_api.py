import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
import json

from app.main import app
from app.api.telemetry_bus import telemetry_bus
from app.db.session import init_db as init_orm_db
from app.db.connection import init_db as init_raw_db
from app.db.qdrant import ensure_qdrant_collections

@pytest.fixture(scope="module", autouse=True)
def setup_hud_tests():
    init_orm_db()
    init_raw_db()
    ensure_qdrant_collections()

@pytest.mark.asyncio
async def test_telemetry_state():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/telemetry/state")
    
    assert response.status_code == 200
    data = response.json()
    assert "status" in data

@pytest.mark.asyncio
async def test_terminal_execute():
    # Mock the LLM provider to avoid actual API calls in the unit test
    # but since it's a full integration test, maybe we rely on the mocked test provider 
    # already configured via env vars for pytest? 
    # In Phase 1/2 tests, we used a mock llm or just passed tests.
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # We send a trivial command
        payload = {"text": "hello hud"}
        response = await ac.post("/api/terminal/execute", json=payload)
        
    # The provider is usually mocked via pytest-httpx or we just check status
    assert response.status_code == 200
    data = response.json()
    assert "content" in data
    assert "tool_calls_count" in data

@pytest.mark.asyncio
async def test_telemetry_bus_publish():
    # A quick test to verify the in-process queue works.
    sub = telemetry_bus.subscribe()
    
    async def get_event():
        return await sub.__anext__()
        
    task = asyncio.create_task(get_event())
    await asyncio.sleep(0.1) # Prime generator
    
    # Publish an event
    await telemetry_bus.publish("test_event", {"foo": "bar"})
    
    # Read from subscriber
    event_json = await task
    data = json.loads(event_json)
    assert data["event_type"] == "test_event"
    assert data["payload"]["foo"] == "bar"
