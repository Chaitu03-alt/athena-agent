"""Automated test suite for Phase 5: Procedural Tool Calling, Confidence Reinforcement & Memory Decay."""

import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session as SQLModelSession, select

from app.main import app
from app.db.session import engine, init_db
from app.db.qdrant import ensure_qdrant_collections
from app.models.memory import MemoryProcedural
from app.services.chat import reinforce_rule_access
from app.services.reflection import ReflectionService

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_phase5():
    """Ensure database schema and Qdrant collections are initialized."""
    init_db()
    ensure_qdrant_collections()


@pytest.fixture
def db_session():
    """Transactional database session fixture."""
    with SQLModelSession(engine) as session:
        yield session


def test_schema_attributes_and_defaults(db_session: SQLModelSession):
    """Verify last_accessed_at, access_count, and archived_reason columns exist on MemoryProcedural."""
    rule_id = uuid.uuid4()
    rule = MemoryProcedural(
        id=rule_id,
        rule_statement="Always use pytest for testing Python applications.",
        category="tool_preference",
        confidence=0.85,
        source="explicit_user",
        source_episodic_ids=[],
        active=True,
        is_active=True,
        version=1,
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)

    try:
        assert rule.access_count == 1
        assert rule.last_accessed_at is not None
        assert rule.archived_reason is None
        assert rule.category == "tool_preference"
    finally:
        db_session.delete(rule)
        db_session.commit()


def test_access_and_confidence_reinforcement(db_session: SQLModelSession):
    """Verify that retrieval reinforcement boosts confidence (+0.05 capped at 1.0) and increments access_count."""
    rule1_id = uuid.uuid4()
    rule2_id = uuid.uuid4()

    rule1 = MemoryProcedural(
        id=rule1_id,
        rule_statement="Prefer ripgrep over grep for search in codebase.",
        category="tool_preference",
        confidence=0.80,
        source="explicit_user",
        source_episodic_ids=[],
        access_count=1,
        active=True,
        is_active=True,
        version=1,
    )
    rule2 = MemoryProcedural(
        id=rule2_id,
        rule_statement="Always run git diff before committing.",
        category="workflow",
        confidence=0.98,
        source="explicit_user",
        source_episodic_ids=[],
        access_count=3,
        active=True,
        is_active=True,
        version=1,
    )
    db_session.add(rule1)
    db_session.add(rule2)
    db_session.commit()

    try:
        # Reinforce rule1 and rule2
        reinforced = reinforce_rule_access(db=db_session, rule_ids=[rule1_id, rule2_id], boost_amount=0.05)
        assert len(reinforced) == 2

        db_session.refresh(rule1)
        db_session.refresh(rule2)

        # Rule 1: confidence 0.80 -> 0.85, access_count 1 -> 2
        assert rule1.access_count == 2
        assert abs(rule1.confidence - 0.85) < 1e-4

        # Rule 2: confidence 0.98 + 0.05 = 1.03 -> capped at 1.0, access_count 3 -> 4
        assert rule2.access_count == 4
        assert rule2.confidence == 1.0

    finally:
        db_session.delete(rule1)
        db_session.delete(rule2)
        db_session.commit()


def test_memory_decay_pass(db_session: SQLModelSession):
    """Verify that rules older than the inactivity window decay, and archive when confidence < 0.40."""
    service = ReflectionService()
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(hours=48)
    recent_time = now - timedelta(minutes=5)

    # 1. Normal active rule that should decay confidence
    decaying_rule_id = uuid.uuid4()
    decaying_rule = MemoryProcedural(
        id=decaying_rule_id,
        rule_statement="Use format string interpolation in Python.",
        category="coding_style",
        confidence=0.75,
        source="consolidation_inference",
        source_episodic_ids=[],
        last_accessed_at=old_time,
        access_count=2,
        active=True,
        is_active=True,
        version=1,
    )

    # 2. Low-confidence rule that should be archived below 0.40
    archiving_rule_id = uuid.uuid4()
    archiving_rule = MemoryProcedural(
        id=archiving_rule_id,
        rule_statement="Temporary experiment: use python 2 syntax.",
        category="coding_style",
        confidence=0.42,
        source="consolidation_inference",
        source_episodic_ids=[],
        last_accessed_at=old_time,
        access_count=1,
        active=True,
        is_active=True,
        version=1,
    )

    # 3. Fresh rule that should NOT decay
    fresh_rule_id = uuid.uuid4()
    fresh_rule = MemoryProcedural(
        id=fresh_rule_id,
        rule_statement="Recently used rule that should remain untouched.",
        category="coding_style",
        confidence=0.90,
        source="explicit_user",
        source_episodic_ids=[],
        last_accessed_at=recent_time,
        access_count=5,
        active=True,
        is_active=True,
        version=1,
    )

    db_session.add(decaying_rule)
    db_session.add(archiving_rule)
    db_session.add(fresh_rule)
    db_session.commit()

    try:
        # Run decay pass with 24 hours inactivity window
        result = service.decay_inactive_rules(
            db=db_session,
            inactivity_hours=24.0,
            decay_rate=0.05,
            minimum_active_confidence=0.40,
        )
        assert result["status"] == "success"

        db_session.refresh(decaying_rule)
        db_session.refresh(archiving_rule)
        db_session.refresh(fresh_rule)

        # Rule 1: 0.75 -> 0.70, still active
        assert decaying_rule.is_active is True
        assert abs(decaying_rule.confidence - 0.70) < 1e-4

        # Rule 2: 0.42 - 0.05 = 0.37 < 0.40 -> archived!
        assert archiving_rule.is_active is False
        assert archiving_rule.active is False
        assert archiving_rule.archived_reason == "decay"
        assert abs(archiving_rule.confidence - 0.37) < 1e-4

        # Rule 3: fresh, untouched
        assert fresh_rule.is_active is True
        assert fresh_rule.confidence == 0.90

    finally:
        db_session.delete(decaying_rule)
        db_session.delete(archiving_rule)
        db_session.delete(fresh_rule)
        db_session.commit()


def test_api_decay_endpoint(db_session: SQLModelSession):
    """Verify POST /api/memory/decay executes decay and returns summary."""
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(hours=30)
    test_id = uuid.uuid4()

    rule = MemoryProcedural(
        id=test_id,
        rule_statement="Test rule for API decay endpoint.",
        category="workflow",
        confidence=0.60,
        source="test",
        source_episodic_ids=[],
        last_accessed_at=old_time,
        active=True,
        is_active=True,
        version=1,
    )
    db_session.add(rule)
    db_session.commit()

    try:
        resp = client.post(
            "/api/memory/decay",
            json={"inactivity_hours": 24.0, "decay_rate": 0.05, "minimum_active_confidence": 0.40},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "decayed_count" in data
        assert "archived_count" in data

        db_session.refresh(rule)
        assert abs(rule.confidence - 0.55) < 1e-4
    finally:
        db_session.delete(rule)
        db_session.commit()


def test_tool_preference_category_query(db_session: SQLModelSession):
    """Verify GET /api/memory/rules?category=tool_preference filters correctly."""
    tool_rule_id = uuid.uuid4()
    tool_rule = MemoryProcedural(
        id=tool_rule_id,
        rule_statement="Always include --verbose when running pytest.",
        category="tool_preference",
        confidence=0.95,
        source="explicit_user",
        source_episodic_ids=[],
        active=True,
        is_active=True,
        version=1,
    )
    db_session.add(tool_rule)
    db_session.commit()

    try:
        resp = client.get("/api/memory/rules?category=tool_preference")
        assert resp.status_code == 200
        items = resp.json()
        assert any(r["id"] == str(tool_rule_id) for r in items)
        for item in items:
            assert item["category"] == "tool_preference"
    finally:
        db_session.delete(tool_rule)
        db_session.commit()


def test_turn_stream_reinforces_injected_rules(db_session: SQLModelSession):
    """Verify that a multi-turn chat stream automatically reinforces all active procedural rules injected into context."""
    from app.models.session import Session

    old_time = datetime.now(timezone.utc) - timedelta(hours=5)
    test_rule_id = uuid.uuid4()
    test_rule = MemoryProcedural(
        id=test_rule_id,
        rule_statement="Always write clean modular code.",
        category="coding_style",
        confidence=0.85,
        source="explicit_user",
        source_episodic_ids=[],
        access_count=1,
        last_accessed_at=old_time,
        active=True,
        is_active=True,
        version=1,
    )
    db_session.add(test_rule)

    sess_id = uuid.uuid4()
    session = Session(id=sess_id, title="Test Reinforcement Session")
    db_session.add(session)
    db_session.commit()

    try:
        # Trigger message turn via API
        resp = client.post(
            f"/api/sessions/{sess_id}/messages",
            json={"content": "Can you review my code?"},
        )
        assert resp.status_code == 200

        # Read streaming response to ensure full execution
        _ = resp.content

        # Verify rule in database was reinforced immediately
        db_session.refresh(test_rule)
        assert test_rule.access_count >= 2
        last_acc = test_rule.last_accessed_at if test_rule.last_accessed_at.tzinfo else test_rule.last_accessed_at.replace(tzinfo=timezone.utc)
        assert last_acc > old_time
        assert abs(test_rule.confidence - 0.90) < 1e-4

    finally:
        from app.models.message import Message
        from app.models.memory import MemoryEpisodic

        db_session.delete(test_rule)
        for ep in db_session.exec(select(MemoryEpisodic).where(MemoryEpisodic.session_id == sess_id)).all():
            db_session.delete(ep)
        for msg in db_session.exec(select(Message).where(Message.session_id == sess_id)).all():
            db_session.delete(msg)
        db_session.delete(session)
        db_session.commit()


@pytest.mark.asyncio
async def test_retrieve_memory_context_vector_fallback(db_session: SQLModelSession, monkeypatch):
    """Verify that retrieve_memory_context degrades gracefully to DB rules when vector search fails."""
    from app.services.chat import retrieve_memory_context
    from app.models.memory import MemoryProcedural

    # Create active rule
    rule_id = uuid.uuid4()
    test_rule = MemoryProcedural(
        id=rule_id,
        rule_statement="Always use robust try/except fallbacks for external APIs.",
        category="coding_style",
        confidence=0.85,
        source="explicit_user",
        active=True,
        is_active=True,
        version=1,
    )
    db_session.add(test_rule)
    db_session.commit()

    # Simulate vector search failure inside chat service
    def mock_search_fail(*args, **kwargs):
        raise ConnectionError("Qdrant simulated connection failure")

    import app.services.chat
    monkeypatch.setattr(app.services.chat, "search_memory_vectors", mock_search_fail)

    try:
        context = await retrieve_memory_context(
            query_text="How should I write API error handling?",
            db=db_session,
            limit=5,
        )
        assert context is not None
        assert "active_rules" in context
        assert "retrieved_memories" in context
        # Vector memories degraded to empty list without raising exception
        assert context["retrieved_memories"] == []
        # Active DB rules were retrieved successfully
        rule_ids = [r.id for r in context["active_rules"]]
        assert rule_id in rule_ids
    finally:
        db_session.delete(test_rule)
        db_session.commit()


@pytest.mark.asyncio
async def test_consolidation_concurrency_lock(db_session: SQLModelSession):
    """Verify that ReflectionService prevents concurrent execution when consolidation is in progress."""
    service = ReflectionService()
    # Acquire lock manually to simulate an ongoing background cycle
    await service._consolidation_lock.acquire()
    try:
        res = await service.consolidate(db=db_session, importance_threshold=0.5)
        assert res["status"] == "in_progress"
        assert "already running" in res["message"]
    finally:
        service._consolidation_lock.release()


def test_session_cascade_delete(db_session: SQLModelSession):
    """Verify that deleting a session cascades and removes episodic memories without ForeignKeyViolation."""
    from app.models.session import Session
    from app.models.message import Message
    from app.models.memory import MemoryEpisodic

    sess_id = uuid.uuid4()
    session = Session(id=sess_id, title="Session to Delete")
    db_session.add(session)
    db_session.commit()

    msg_id = uuid.uuid4()
    msg = Message(id=msg_id, session_id=sess_id, role="user", content="Hello test cascade")
    db_session.add(msg)
    db_session.commit()

    ep_id = uuid.uuid4()
    ep = MemoryEpisodic(
        id=ep_id,
        session_id=sess_id,
        message_id=msg_id,
        content="User: Hello\nAssistant: Hi",
        entry_type="turn",
        importance_score=0.8,
    )
    db_session.add(ep)
    db_session.commit()

    # Call DELETE /api/sessions/{session_id}
    resp = client.delete(f"/api/sessions/{sess_id}")
    assert resp.status_code == 204

    # Verify session, message, and episodic memory are all deleted cleanly
    assert db_session.get(Session, sess_id) is None
    assert db_session.get(Message, msg_id) is None
    assert db_session.get(MemoryEpisodic, ep_id) is None


@pytest.mark.asyncio
async def test_run_db_offload_thread():
    """Verify that run_db offloads blocking calls to a worker thread asynchronously."""
    from app.db.session import run_db
    import threading

    current_tid = threading.get_ident()

    def blocking_work(val: int) -> int:
        worker_tid = threading.get_ident()
        assert worker_tid != current_tid
        return val * 2

    res = await run_db(blocking_work, 21)
    assert res == 42



