import pytest
import asyncio
from unittest.mock import patch, AsyncMock

from app.db.connection import init_db, execute_write_async
from app.scheduler.setup import start_scheduler, shutdown_scheduler, get_scheduler
from app.scheduler.meta import CronMetaManager
from app.tools.builtin.cron_ops import cron_create, cron_list, cron_delete

@pytest.fixture(autouse=True)
async def setup_test_db_cron(monkeypatch, tmp_path):
    test_db_path = tmp_path / "test_athena_cron.db"
    monkeypatch.setenv("SQLITE_DB_PATH", str(test_db_path))
    init_db()
    
    await start_scheduler()
    scheduler = get_scheduler()
    scheduler.remove_all_jobs()
    await execute_write_async("DELETE FROM cron_jobs_meta")
    
    yield
    
    scheduler.remove_all_jobs()
    await execute_write_async("DELETE FROM cron_jobs_meta")
    await shutdown_scheduler()

@pytest.mark.asyncio
async def test_cron_create_alert_and_task():
    """Test creating an alert and an agent_task job."""
    with patch("app.tools.builtin.cron_ops._get_primary_chat_id", return_value=12345):
        # 1. Create alert
        res_alert = await cron_create("alert", "Morning reminder", "0 9 * * *", "Drink water!")
        assert "Success!" in res_alert
        assert "alert" in res_alert
        
        # 2. Create agent_task
        res_task = await cron_create("agent_task", "Daily crypto summary", "0 18 * * *", "Check crypto prices and summarize.")
        assert "Success!" in res_task
        
        # Verify scheduler has 2 jobs
        scheduler = get_scheduler()
        jobs = scheduler.get_jobs()
        assert len(jobs) == 2
        
        # Verify metadata
        meta = await CronMetaManager.get_all_meta()
        assert len(meta) == 2
        
        types = [m["job_type"] for m in meta]
        assert "alert" in types
        assert "agent_task" in types

@pytest.mark.asyncio
async def test_cron_persistence_across_restarts():
    """Test that jobs survive a scheduler restart due to SQLAlchemyJobStore."""
    with patch("app.tools.builtin.cron_ops._get_primary_chat_id", return_value=12345):
        await cron_create("alert", "Persist Test", "*/5 * * * *", "Will I survive?")
        
        # Verify initial
        scheduler = get_scheduler()
        assert len(scheduler.get_jobs()) == 1
        
        # Shutdown
        await shutdown_scheduler()
        
        # Restart
        await start_scheduler()
        scheduler_restarted = get_scheduler()
        
        # Verify loaded from DB
        assert len(scheduler_restarted.get_jobs()) == 1
        jobs = scheduler_restarted.get_jobs()
        assert jobs[0].args == (12345, "Will I survive?")

@pytest.mark.asyncio
async def test_cron_delete():
    """Test deleting a cron job cleanly from both APScheduler and meta."""
    with patch("app.tools.builtin.cron_ops._get_primary_chat_id", return_value=12345):
        await cron_create("alert", "To Delete", "*/5 * * * *", "Delete me")
        
        scheduler = get_scheduler()
        jobs = scheduler.get_jobs()
        job_id = jobs[0].id
        
        # Meta exists
        meta_before = await CronMetaManager.get_all_meta()
        assert len(meta_before) == 1
        
        # Delete
        res = await cron_delete(job_id)
        assert "Success!" in res
        
        # Verify APScheduler removed it
        assert len(scheduler.get_jobs()) == 0
        
        # Verify Meta removed it
        meta_after = await CronMetaManager.get_all_meta()
        assert len(meta_after) == 0

@pytest.mark.asyncio
async def test_cron_list():
    """Test listing of active jobs."""
    with patch("app.tools.builtin.cron_ops._get_primary_chat_id", return_value=12345):
        await cron_create("alert", "List 1", "0 0 * * *", "List msg 1")
        await cron_create("alert", "List 2", "0 1 * * *", "List msg 2")
        
        res = await cron_list()
        assert "List 1" in res
        assert "List 2" in res
        assert "0 0 * * *" in res
        assert "ID:" in res
