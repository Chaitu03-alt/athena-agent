from typing import List, Dict, Any
from fastapi import APIRouter
from pydantic import BaseModel
import structlog

from app.scheduler.meta import CronMetaManager
from app.tools.builtin.cron_ops import cron_create, cron_delete

logger = structlog.get_logger(__name__)

router = APIRouter()

class CronCreateRequest(BaseModel):
    job_type: str
    label: str
    schedule_desc: str
    message_or_prompt: str

class CronDeleteRequest(BaseModel):
    job_id: str

@router.get("/list", tags=["Cron"])
async def api_cron_list() -> List[Dict[str, Any]]:
    """Lists all active recurring cron jobs."""
    jobs = await CronMetaManager.get_all_meta()
    return jobs

@router.post("/create", tags=["Cron"])
async def api_cron_create(req: CronCreateRequest) -> Dict[str, str]:
    """Creates a new cron job via HUD."""
    res = await cron_create(req.job_type, req.label, req.schedule_desc, req.message_or_prompt)
    if "Success" in res:
        return {"status": "success", "message": res}
    return {"status": "error", "message": res}

@router.post("/delete", tags=["Cron"])
async def api_cron_delete(req: CronDeleteRequest) -> Dict[str, str]:
    """Deletes an active cron job via HUD."""
    res = await cron_delete(req.job_id)
    if "Success" in res:
        return {"status": "success", "message": res}
    return {"status": "error", "message": res}
