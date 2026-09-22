"""Automated test suite for Phase 3: Autonomous Reflection Worker, Conflict Resolution & Rule Lifecycle."""

import asyncio
import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlmodel import Session as SQLModelSession, select

from app.main import app
from app.db.session import engine, init_db
from app.db.qdrant import ensure_qdrant_collections, search_memory_vectors, update_memory_payload
from app.models.memory import MemoryEpisodic, MemoryProcedural, MemorySemantic
from app.models.session import Session
from app.services.reflection import ReflectionService
from app.worker import AutonomousReflectionWorker

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_phase3():
    """Ensure tables and Qdrant collections are ready."""
    init_db()
    ensure_qdrant_collections()


@pytest.fixture
def db_session():
    """Transactional session fixture."""
    with SQLModelSession(engine) as session:
        yield session


def test_rule_versioning_and_lifecycle_model(db_session: SQLModelSession):
    """Verify is_active and version attributes in procedural and semantic models."""
    proc = MemoryProcedural(
        id=uuid.uuid4(),
        rule_statement="Always write docstrings for public functions.",
        category="coding_style",
        confidence=0.90,
        source="explicit_user",
        source_episodic_ids=[],
        is_active=True,
        version=1,
    )
    sem = MemorySemantic(
        id=uuid.uuid4(),
        statement="Project backend is built with FastAPI.",
        category="project_fact",
        confidence=0.95,
        source_episodic_ids=[],
        is_active=True,
        version=1,
    )
    db_session.add(proc)
    db_session.add(sem)
    db_session.commit()

    db_session.refresh(proc)
    db_session.refresh(sem)
    try:
        assert proc.is_active is True
        assert proc.version == 1
        assert sem.is_active is True
        assert sem.version == 1
    finally:
        db_session.delete(proc)
        db_session.delete(sem)
        db_session.commit()


@pytest.mark.asyncio
async def test_conflict_resolution_and_version_chain(db_session: SQLModelSession):
    """Verify that a conflicting preference soft-deprecates the older rule and increments version."""
    now = datetime.now(timezone.utc)
    # 1. Seed existing active functional style rule
    rule_v1 = MemoryProcedural(
        id=uuid.uuid4(),
        rule_statement="Prefer writing Python code in a modular functional style.",
        category="coding_style",
        confidence=0.90,
        source="consolidation_inference",
        source_episodic_ids=[],
        active=True,
        is_active=True,
        version=1,
        created_at=now,
        updated_at=now,
    )
    db_session.add(rule_v1)
    db_session.commit()

    # 2. Add an episodic turn expressing a conflicting preference (OOP style)
    test_session = Session(id=uuid.uuid4(), title="Shift to OOP")
    db_session.add(test_session)
    db_session.commit()

    shift_turn = MemoryEpisodic(
        id=uuid.uuid4(),
        session_id=test_session.id,
        content="User: Actually I now prefer object-oriented class-based OOP style in Python code.\nAssistant: Understood.",
        importance_score=0.90,
        consolidated=False,
        tags=["preference", "python", "oop"],
        created_at=now,
    )
    db_session.add(shift_turn)
    db_session.commit()

    # 3. Run consolidation
    service = ReflectionService()
    result = await service.consolidate(db=db_session, importance_threshold=0.70)
    assert result["status"] == "success"

    # 4. Verify rule_v1 was deprecated and superseded
    db_session.refresh(rule_v1)
    assert rule_v1.is_active is False
    assert rule_v1.superseded_by is not None

    # 5. Verify new rule was created with version 2
    rule_v2 = db_session.get(MemoryProcedural, rule_v1.superseded_by)
    assert rule_v2 is not None
    assert rule_v2.is_active is True
    assert rule_v2.version == 2
    assert "object-oriented" in rule_v2.rule_statement.lower() or "oop" in rule_v2.rule_statement.lower()


def test_qdrant_active_only_filtering():
    """Verify Qdrant search with active_only=True ignores deactivated points."""
    active_id = str(uuid.uuid4())
    inactive_id = str(uuid.uuid4())
    vector = [1.0] + [0.0] * 1023

    from app.db.qdrant import upsert_memory_vector

    # Upsert active
    upsert_memory_vector(
        point_id=active_id,
        vector=vector,
        payload={"is_active": True, "content": "Active testing point"},
    )
    # Upsert inactive
    upsert_memory_vector(
        point_id=inactive_id,
        vector=vector,
        payload={"is_active": False, "content": "Inactive testing point"},
    )

    results = search_memory_vectors(query_vector=vector, limit=50, active_only=True)
    ids_found = [r["id"] for r in results]

    assert active_id in ids_found
    assert inactive_id not in ids_found


def test_api_rule_management_endpoints(db_session: SQLModelSession):
    """Verify GET /api/memory/rules and DELETE /api/memory/rules/{id}."""
    test_rule = MemoryProcedural(
        id=uuid.uuid4(),
        rule_statement="Temporary test rule to verify endpoint deactivation.",
        category="testing",
        confidence=0.99,
        source="test",
        source_episodic_ids=[],
        active=True,
        is_active=True,
        version=1,
    )
    db_session.add(test_rule)
    db_session.commit()
    target_id = str(test_rule.id)

    # 1. Fetch active rules
    rules_resp = client.get("/api/memory/rules")
    assert rules_resp.status_code == 200
    rules = rules_resp.json()
    assert isinstance(rules, list)
    assert any(r["id"] == target_id for r in rules)

    # 2. Deactivate rule
    del_resp = client.delete(f"/api/memory/rules/{target_id}")
    assert del_resp.status_code == 200
    del_data = del_resp.json()
    assert del_data["status"] == "success"
    assert del_data["is_active"] is False

    # 3. Verify rule is no longer in active list
    rules_after = client.get("/api/memory/rules").json()
    assert not any(r["id"] == target_id for r in rules_after)


@pytest.mark.asyncio
async def test_background_worker_lifecycle():
    """Verify background worker starts and stops cleanly."""
    worker = AutonomousReflectionWorker(interval_seconds=1)
    task = asyncio.create_task(worker.start())
    await asyncio.sleep(0.1)
    assert worker.is_running
    worker.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert not worker.is_running


@pytest.mark.asyncio
async def test_deduplication_reinforces_confidence_without_duplicate_row(db_session: SQLModelSession):
    """Verify that duplicate candidate rules reinforce confidence and update timestamp instead of inserting duplicate rows."""
    service = ReflectionService()
    now = datetime.now(timezone.utc)

    # 1. Clean active rules
    service.deduplicate_and_clean_active_rules(db_session)

    # Count initial active rules with strict typing
    initial_strict = list(
        db_session.exec(
            select(MemoryProcedural)
            .where(MemoryProcedural.is_active == True)
            .where(MemoryProcedural.rule_statement == "Prefer strict typing in Python code.")
        ).all()
    )

    # 2. Add an episodic turn with strict typing preference
    session1 = Session(id=uuid.uuid4(), title="Strict Typing 1")
    db_session.add(session1)
    db_session.commit()

    turn1 = MemoryEpisodic(
        id=uuid.uuid4(),
        session_id=session1.id,
        content="User: Always use strict typing in Python.\nAssistant: Noted.",
        importance_score=0.90,
        consolidated=False,
        tags=["preference", "typing"],
        created_at=now,
    )
    db_session.add(turn1)
    db_session.commit()

    # 3. Consolidate turn1
    res1 = await service.consolidate(db=db_session, importance_threshold=0.70)
    assert res1["status"] == "success"

    rules_after_turn1 = list(
        db_session.exec(
            select(MemoryProcedural)
            .where(MemoryProcedural.is_active == True)
            .where(MemoryProcedural.rule_statement == "Prefer strict typing in Python code.")
        ).all()
    )
    assert len(rules_after_turn1) == 1
    canonical_rule = rules_after_turn1[0]
    initial_confidence = canonical_rule.confidence
    initial_updated_at = canonical_rule.updated_at

    # 4. Add a duplicate episodic turn with identical preference
    session2 = Session(id=uuid.uuid4(), title="Strict Typing 2")
    db_session.add(session2)
    db_session.commit()

    turn2 = MemoryEpisodic(
        id=uuid.uuid4(),
        session_id=session2.id,
        content="User: Always use strict typing in Python.\nAssistant: Acknowledged.",
        importance_score=0.90,
        consolidated=False,
        tags=["preference", "typing"],
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(turn2)
    db_session.commit()

    # 5. Consolidate turn2
    res2 = await service.consolidate(db=db_session, importance_threshold=0.70)
    assert res2["status"] == "success"

    # 6. Verify NO duplicate rule was created
    rules_after_turn2 = list(
        db_session.exec(
            select(MemoryProcedural)
            .where(MemoryProcedural.is_active == True)
            .where(MemoryProcedural.rule_statement == "Prefer strict typing in Python code.")
        ).all()
    )
    assert len(rules_after_turn2) == 1, f"Expected exactly 1 active rule, got {len(rules_after_turn2)}"

    # 7. Verify confidence and updated_at were reinforced
    db_session.refresh(canonical_rule)
    assert canonical_rule.confidence >= initial_confidence
    assert canonical_rule.updated_at >= initial_updated_at

