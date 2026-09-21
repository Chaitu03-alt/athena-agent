import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from app.db.session import engine
from app.scheduler.meta import ensure_cron_meta_schema

logger = structlog.get_logger(__name__)

# Global singleton for the scheduler
_scheduler = None

def get_scheduler() -> AsyncIOScheduler:
    """Retrieve the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        raise RuntimeError("Scheduler is not initialized. Call start_scheduler() first.")
    return _scheduler

async def start_scheduler() -> None:
    """
    Initializes and starts the APScheduler cooperatively using the WAL SQLite database.
    """
    global _scheduler
    
    # 1. Ensure meta schema is upgraded
    await ensure_cron_meta_schema()
    
    # 2. Configure JobStore pointing directly to the SQLModel/SQLAlchemy engine
    jobstores = {
        'default': SQLAlchemyJobStore(engine=engine, tablename='apscheduler_jobs')
    }
    
    # 3. JobDefaults: define misfire grace time
    # For general jobs, we allow some grace, but individual jobs can override this.
    job_defaults = {
        'coalesce': True,
        'max_instances': 1
    }
    
    _scheduler = AsyncIOScheduler(jobstores=jobstores, job_defaults=job_defaults, timezone="UTC")
    
    try:
        _scheduler.start()
        logger.info("APScheduler started cooperatively inside FastAPI.")
    except Exception as e:
        logger.error("Failed to start APScheduler", error=str(e))


async def shutdown_scheduler() -> None:
    """
    Gracefully shuts down the APScheduler.
    """
    global _scheduler
    if _scheduler:
        logger.info("Shutting down APScheduler...")
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("APScheduler stopped.")
