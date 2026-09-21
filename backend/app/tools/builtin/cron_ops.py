import uuid
import json
import structlog
from typing import Optional
from pydantic import BaseModel, Field

from app.config import settings
from app.tools.registry import register_tool
from app.scheduler.setup import get_scheduler
from app.scheduler.meta import CronMetaManager
from app.scheduler.jobs import execute_alert_job, execute_agent_task_job

logger = structlog.get_logger(__name__)

def _get_primary_chat_id() -> int:
    """Helper to get the primary user's chat_id from config, defaulting to 0 for local HUD operations."""
    ids_str = settings.TELEGRAM_ALLOWED_USER_IDS
    if not ids_str or not ids_str.strip():
        return 0
    try:
        return int(ids_str.split(",")[0].strip())
    except (ValueError, IndexError):
        return 0


class CronCreateArgs(BaseModel):
    job_type: str = Field(description="Must be 'alert' or 'agent_task'.")
    label: str = Field(description="A human-readable label for this job.")
    schedule_desc: str = Field(description="Standard 5-field cron expression, e.g. '*/5 * * * *'.")
    message_or_prompt: str = Field(description="The alert text or the task prompt for the agent.")

@register_tool(
    name="cron_create",
    description="Creates a recurring cron job for alerts or autonomous agent workflows.",
    parameters=CronCreateArgs.model_json_schema()
)
async def cron_create(job_type: str, label: str, schedule_desc: str, message_or_prompt: str) -> str:
    """
    Creates a recurring cron job. Use job_type='alert' for simple notifications. 
    Use job_type='agent_task' for background autonomous agent workflows.
    """
    if job_type not in ("alert", "agent_task"):
        return "Error: job_type must be 'alert' or 'agent_task'"
        
    try:
        chat_id = _get_primary_chat_id()
        scheduler = get_scheduler()
        
        from apscheduler.triggers.cron import CronTrigger
        trigger = CronTrigger.from_crontab(schedule_desc)
        
        job_id = uuid.uuid4().hex
        
        if job_type == "alert":
            scheduler.add_job(
                execute_alert_job,
                trigger=trigger,
                id=job_id,
                args=[chat_id, message_or_prompt],
                misfire_grace_time=10, # short grace for alerts
            )
        else:
            scheduler.add_job(
                execute_agent_task_job,
                trigger=trigger,
                id=job_id,
                args=[chat_id, label, message_or_prompt],
                misfire_grace_time=3600, # fire once on recovery for agent tasks
                coalesce=True
            )
            
        await CronMetaManager.create_meta(
            job_id=job_id,
            job_type=job_type,
            label=label,
            schedule_desc=schedule_desc,
            payload={"message_or_prompt": message_or_prompt},
            created_via="llm"
        )
        return f"Success! Created '{job_type}' job '{label}' with ID {job_id} on schedule {schedule_desc}."
        
    except Exception as e:
        logger.error("Failed to create cron job", error=str(e))
        return f"Failed to create cron job: {str(e)}"


class CronListArgs(BaseModel):
    pass

@register_tool(
    name="cron_list",
    description="Lists all active recurring cron jobs along with their IDs and labels.",
    parameters=CronListArgs.model_json_schema()
)
async def cron_list() -> str:
    """
    Lists all active recurring cron jobs along with their IDs and labels.
    """
    try:
        jobs = await CronMetaManager.get_all_meta()
        if not jobs:
            return "No active cron jobs found."
            
        result = []
        for j in jobs:
            result.append(f"ID: {j['apscheduler_job_id']} | Type: {j['job_type']} | Label: '{j['label']}' | Schedule: {j['schedule_desc']}")
            
        return "\n".join(result)
    except Exception as e:
        return f"Failed to list cron jobs: {str(e)}"


class CronDeleteArgs(BaseModel):
    job_id: str = Field(description="The exact apscheduler_job_id to delete.")

@register_tool(
    name="cron_delete",
    description="Deletes an active cron job by its ID.",
    parameters=CronDeleteArgs.model_json_schema()
)
async def cron_delete(job_id: str) -> str:
    """
    Deletes an active cron job by its ID. Use cron_list first if you don't know the ID.
    """
    try:
        scheduler = get_scheduler()
        
        # Will raise JobLookupError if not found in apscheduler, but we ignore it just in case metadata is desynced
        try:
            scheduler.remove_job(job_id)
        except Exception:
            logger.warning(f"Job {job_id} not found in APScheduler, but will attempt to remove metadata anyway.")
            
        await CronMetaManager.delete_meta(job_id)
        return f"Success! Deleted job ID {job_id}."
        
    except Exception as e:
        logger.error("Failed to delete cron job", error=str(e))
        return f"Failed to delete cron job: {str(e)}"
