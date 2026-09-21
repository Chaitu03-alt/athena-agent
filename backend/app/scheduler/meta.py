import json
import structlog
from typing import Optional, List, Dict, Any

from app.db.connection import execute_write_async, execute_read_async

logger = structlog.get_logger(__name__)

async def ensure_cron_meta_schema() -> None:
    """
    Ensures the cron_jobs_meta table matches the Phase 4 schema requirements.
    Drops the old Phase 2 schema and recreates it if necessary.
    """
    try:
        # Check current schema
        columns = await execute_read_async("PRAGMA table_info(cron_jobs_meta)")
        col_names = [c["name"] for c in columns]
        
        # If schema is old, drop and recreate
        if "apscheduler_job_id" not in col_names:
            logger.info("Dropping legacy cron_jobs_meta table for Phase 4 schema upgrade...")
            await execute_write_async("DROP TABLE IF EXISTS cron_jobs_meta")
            
            ddl = """
            CREATE TABLE cron_jobs_meta (
                apscheduler_job_id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                label TEXT NOT NULL,
                schedule_desc TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_via TEXT NOT NULL
            )
            """
            await execute_write_async(ddl)
            logger.info("New cron_jobs_meta table created.")
            
    except Exception as e:
        logger.error("Failed to ensure cron_meta schema", error=str(e))


class CronMetaManager:
    """CRUD operations for human-facing cron jobs metadata."""
    
    @classmethod
    async def create_meta(
        cls, 
        job_id: str, 
        job_type: str, 
        label: str, 
        schedule_desc: str, 
        payload: Dict[str, Any],
        created_via: str = "llm"
    ) -> None:
        await execute_write_async(
            """
            INSERT INTO cron_jobs_meta (apscheduler_job_id, job_type, label, schedule_desc, payload_json, created_via)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, job_type, label, schedule_desc, json.dumps(payload), created_via)
        )

    @classmethod
    async def get_all_meta(cls) -> List[Dict[str, Any]]:
        rows = await execute_read_async("SELECT * FROM cron_jobs_meta ORDER BY created_at DESC")
        result = []
        for row in rows:
            r_dict = dict(row)
            try:
                r_dict["payload"] = json.loads(r_dict.pop("payload_json"))
            except (json.JSONDecodeError, TypeError):
                r_dict["payload"] = {}
            result.append(r_dict)
        return result

    @classmethod
    async def delete_meta(cls, job_id: str) -> None:
        await execute_write_async(
            "DELETE FROM cron_jobs_meta WHERE apscheduler_job_id = ?",
            (job_id,)
        )
