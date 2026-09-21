"""Automated test suite for Phase 2: Memory Consolidation and Semantic Vector Storage."""

import json
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session as SQLModelSession, select

from app.main import app
from app.db.session import engine, init_db
from app.db.qdrant import ensure_qdrant_collections, get_qdrant_health, upsert_memory_vector, search_memory_vectors
from app.models.memory import MemoryEpisodic, MemoryProcedural, MemorySemantic
from app.models.session import Session
from app.services.reflection import ReflectionService

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_phase2():
    """Ensure database tables and Qdrant collections are initialized."""
    init_db()
    ensure_qdrant_collections()


@pytest.fixture
def db_session():
    """Provide a transactional session for testing."""
    with SQLModelSession(engine) as session:
        yield session


def test_qdrant_health_and_collection():
    """Test Qdrant health check and ensure collections exist."""
    health = get_qdrant_health()
    assert health["status"] == "connected"
    assert "agent_memories" in health["collections"]


def test_qdrant_vector_upsert_and_search():
    """Test upserting a vector into Qdrant and searching by cosine similarity."""
    test_id = str(uuid.uuid4())
    vector = [0.0, 1.0] + [0.0] * 1022
    payload = {
        "memory_id": test_id,
        "content": "Prefer using pytest for testing.",
        "category": "tooling",
        "is_active": True,
    }
    upsert_memory_vector(point_id=test_id, vector=vector, payload=payload)

    results = search_memory_vectors(query_vector=vector, limit=100)
    assert len(results) > 0
    found = any(r["id"] == test_id for r in results)
    assert found


@pytest.mark.asyncio
async def test_reflection_service_consolidation(db_session: SQLModelSession):
    """Test reflection service filtering and consolidation logic."""
    # 1. Create a test session
    session_obj = Session(id=uuid.uuid4(), title="Test Reflection Session")
    db_session.add(session_obj)
    db_session.commit()

    # 2. Insert high-importance turn (should consolidate)
    high_turn = MemoryEpisodic(
        id=uuid.uuid4(),
        session_id=session_obj.id,
        content="User: Remember that I always write typed code with Pydantic.\nAssistant: Understood.",
        importance_score=0.85,
        consolidated=False,
        tags=["preference", "pydantic"],
    )
    # 3. Insert low-importance turn (should NOT consolidate)
    low_turn = MemoryEpisodic(
        id=uuid.uuid4(),
        session_id=session_obj.id,
        content="User: What's the weather like today?\nAssistant: I don't have real-time weather info.",
        importance_score=0.20,
        consolidated=False,
        tags=[],
    )
    db_session.add(high_turn)
    db_session.add(low_turn)
    db_session.commit()

    service = ReflectionService()
    result = await service.consolidate(db=db_session, importance_threshold=0.70)

    assert result["status"] == "success"
    assert result["processed_episodic_count"] >= 1

    # Verify high_turn is marked consolidated
    db_session.refresh(high_turn)
    db_session.refresh(low_turn)
    assert high_turn.consolidated is True
    assert low_turn.consolidated is False


def test_api_memory_endpoints():
    """Test memory API endpoints (/status, /procedural, /consolidate)."""
    # Check status endpoint
    status_resp = client.get("/api/memory/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["vector_db"]["status"] == "connected"

    # Check list procedural
    proc_resp = client.get("/api/memory/procedural")
    assert proc_resp.status_code == 200
    assert isinstance(proc_resp.json(), list)

    # Check manual consolidate trigger
    cons_resp = client.post("/api/memory/consolidate", json={"importance_threshold": 0.99})
    assert cons_resp.status_code == 200
    cons_data = cons_resp.json()
    assert cons_data["status"] == "success"


def test_chat_turn_retrieves_memory_and_adheres():
    """Test that chat turn retrieves recalled procedural rules and answers adhering to them."""
    # 1. Create a session
    sess_resp = client.post("/api/sessions", json={"title": "Test Memory Recall Chat"})
    assert sess_resp.status_code == 201
    session_id = sess_resp.json()["id"]

    # 2. Send coding prompt
    msg_resp = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"content": "Please write a Python function to process records"},
    )
    assert msg_resp.status_code == 200

    # 3. Read streamed SSE content
    response_body = msg_resp.text
    # Must not contain the old hardcoded Phase 1 message
    assert "Everything is operating normally under Phase 1" not in response_body
    
    # Reconstruct text from streamed SSE tokens
    token_contents = []
    for line in response_body.splitlines():
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:].strip())
                if data.get("type") == "token":
                    token_contents.append(data.get("content", ""))
            except json.JSONDecodeError:
                pass
    full_text = "".join(token_contents)

    # Must adhere to recalled preferences (functional or OOP or strict typing)
    assert any(
        kw in full_text
        for kw in [
            "modular functional",
            "strict typing",
            "pipe_transform",
            "object-oriented",
            "DataFilterService",
        ]
    )

