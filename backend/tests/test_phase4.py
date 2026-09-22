"""Automated test suite for Phase 4: Frontend Memory Dashboard & User Controls Backend Support."""

import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session as SQLModelSession

from app.main import app
from app.db.session import engine, init_db
from app.db.qdrant import ensure_qdrant_collections
from app.models.memory import MemoryProcedural

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_phase4():
    """Ensure database tables and Qdrant collections are initialized."""
    init_db()
    ensure_qdrant_collections()


@pytest.fixture
def db_session():
    """Transactional session fixture."""
    with SQLModelSession(engine) as session:
        yield session


def test_patch_rule_status_toggle(db_session: SQLModelSession):
    """Verify PATCH /api/memory/rules/{rule_id} toggles is_active and updates timestamp."""
    rule_id = uuid.uuid4()
    rule = MemoryProcedural(
        id=rule_id,
        rule_statement="Always add type hints to exported interfaces.",
        category="coding_style",
        confidence=0.92,
        source="explicit_user",
        source_episodic_ids=[],
        active=True,
        is_active=True,
        version=1,
    )
    db_session.add(rule)
    db_session.commit()

    try:
        # 1. Toggle to False (deactivate)
        patch_resp1 = client.patch(
            f"/api/memory/rules/{rule_id}",
            json={"is_active": False},
        )
        assert patch_resp1.status_code == 200
        data1 = patch_resp1.json()
        assert data1["status"] == "success"
        assert data1["is_active"] is False
        assert data1["rule_id"] == str(rule_id)

        # Verify in database
        db_session.refresh(rule)
        assert not rule.is_active
        assert not rule.active

        # 2. Toggle back to True (reactivate)
        patch_resp2 = client.patch(
            f"/api/memory/rules/{rule_id}",
            json={"is_active": True},
        )
        assert patch_resp2.status_code == 200
        data2 = patch_resp2.json()
        assert data2["status"] == "success"
        assert data2["is_active"] is True

        db_session.refresh(rule)
        assert rule.is_active
        assert rule.active

    finally:
        db_session.delete(rule)
        db_session.commit()


def test_get_rules_active_only_filter(db_session: SQLModelSession):
    """Verify GET /api/memory/rules with active_only=true vs active_only=false."""
    active_id = uuid.uuid4()
    inactive_id = uuid.uuid4()

    active_rule = MemoryProcedural(
        id=active_id,
        rule_statement="Active test rule for filter verification.",
        category="workflow",
        confidence=0.88,
        source="test",
        source_episodic_ids=[],
        active=True,
        is_active=True,
        version=1,
    )
    inactive_rule = MemoryProcedural(
        id=inactive_id,
        rule_statement="Archived test rule for filter verification.",
        category="workflow",
        confidence=0.75,
        source="test",
        source_episodic_ids=[],
        active=False,
        is_active=False,
        version=1,
    )
    db_session.add(active_rule)
    db_session.add(inactive_rule)
    db_session.commit()

    try:
        # 1. Default / active_only=true
        resp_active = client.get("/api/memory/rules?active_only=true")
        assert resp_active.status_code == 200
        active_list = resp_active.json()
        active_ids = [r["id"] for r in active_list]
        assert str(active_id) in active_ids
        assert str(inactive_id) not in active_ids

        # 2. active_only=false (All rules)
        resp_all = client.get("/api/memory/rules?active_only=false")
        assert resp_all.status_code == 200
        all_list = resp_all.json()
        all_ids = [r["id"] for r in all_list]
        assert str(active_id) in all_ids
        assert str(inactive_id) in all_ids

    finally:
        db_session.delete(active_rule)
        db_session.delete(inactive_rule)
        db_session.commit()


def test_patch_rule_not_found():
    """Verify PATCH returns 404 for a non-existent rule ID."""
    random_id = uuid.uuid4()
    resp = client.patch(
        f"/api/memory/rules/{random_id}",
        json={"is_active": True},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()
