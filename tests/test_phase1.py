"""Automated tests for Phase 1: MVP Chat + Raw Memory."""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session as SQLModelSession, select

from app.main import app
from app.db.session import engine, init_db
from app.models.session import Session
from app.models.message import Message
from app.models.memory import MemoryEpisodic
from app.orchestrator.heuristics import compute_importance_score, extract_tags
from app.orchestrator.agent import AgentOrchestrator


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Ensure all database tables exist before tests run."""
    init_db()


@pytest.fixture
def db_session():
    """Provide a transactional session for testing."""
    with SQLModelSession(engine) as session:
        yield session


def test_heuristic_importance_scoring():
    """Test heuristic importance scoring based on content characteristics."""
    # Preference / Directive should score high
    high_turn = compute_importance_score(
        "Remember that I prefer TypeScript over JavaScript for all new frontend code.",
        "Understood, I have noted this preference.",
    )
    assert high_turn >= 0.50

    # Rule directive
    rule_turn = compute_importance_score(
        "Never delete files without asking for confirmation first."
    )
    assert rule_turn >= 0.50

    # Explicit guideline override must score >= 0.85
    override_turn = compute_importance_score(
        "Athena, update my guidelines: I no longer want to use docstrings for public functions. Stop writing docstrings"
    )
    assert override_turn >= 0.85

    # Small talk greeting should score low
    low_turn = compute_importance_score("hello", "Hi there! How can I help you today?")
    assert low_turn <= 0.30

    # Tag extraction
    tags = extract_tags("Always use pytest with fastapi and postgres")
    assert "pytest" in tags
    assert "fastapi" in tags
    assert "postgres" in tags
    assert "preference" in tags


import asyncio

def test_orchestrator_turn_loop(db_session: SQLModelSession):
    """Test orchestrator execution, message persistence, and episodic memory creation."""
    async def _test():
        # 1. Create a session
        test_session = Session(id=uuid.uuid4(), title="Test Orchestrator Session")
        db_session.add(test_session)
        db_session.commit()

        orchestrator = AgentOrchestrator()
        tokens = []
        done_event = None

        # 2. Execute turn stream
        async for event in orchestrator.handle_turn_stream(
            test_session.id,
            "Remember that I prefer strict typing in Python.",
            db_session,
        ):
            if event["type"] == "token":
                tokens.append(event["content"])
            elif event["type"] == "done":
                done_event = event

        assert len(tokens) > 0
        assert done_event is not None
        assert "message_id" in done_event
        assert done_event["importance_score"] >= 0.5

        # 3. Verify messages in database
        messages = list(
            db_session.exec(
                select(Message).where(Message.session_id == test_session.id).order_by(Message.created_at.asc())
            ).all()
        )
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"

        # 4. Verify episodic memory in database
        episodic_entries = list(
            db_session.exec(
                select(MemoryEpisodic).where(MemoryEpisodic.session_id == test_session.id)
            ).all()
        )
        assert len(episodic_entries) == 1
        entry = episodic_entries[0]
        assert entry.entry_type == "turn"
        assert entry.importance_score >= 0.5
        assert "preference" in entry.tags or "python" in entry.tags

    asyncio.run(_test())


def test_api_session_crud_and_streaming():
    """Test full REST API lifecycle for chat sessions and streaming messages."""
    client = TestClient(app)

    # 1. Create a new session
    resp = client.post("/api/sessions", json={"title": "Test Web Session"})
    assert resp.status_code == 201
    session_data = resp.json()
    session_id = session_data["id"]
    assert session_data["title"] == "Test Web Session"

    # 2. List sessions
    list_resp = client.get("/api/sessions")
    assert list_resp.status_code == 200
    all_sessions = list_resp.json()
    assert any(s["id"] == session_id for s in all_sessions)

    # 3. Send message and receive SSE stream
    with client.stream(
        "POST",
        f"/api/sessions/{session_id}/messages",
        json={"content": "Please explain how episodic memory works in Phase 1."},
    ) as stream_resp:
        assert stream_resp.status_code == 200
        assert "text/event-stream" in stream_resp.headers["content-type"]
        events = []
        for line in stream_resp.iter_lines():
            if line.startswith("data: "):
                events.append(line[6:])

        assert len(events) > 0

    # 4. Verify messages history
    history_resp = client.get(f"/api/sessions/{session_id}/messages")
    assert history_resp.status_code == 200
    messages = history_resp.json()
    assert len(messages) >= 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
