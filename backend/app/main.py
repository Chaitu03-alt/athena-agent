import sys
from pathlib import Path

# Ensure package root is in sys.path so 'app' is importable when executed directly
_app_root = Path(__file__).resolve().parent.parent
if str(_app_root) not in sys.path:
    sys.path.insert(0, str(_app_root))

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response

import asyncio
import structlog
from app.config import settings
from app.db.session import init_db as init_orm_db
from app.db.connection import init_db as init_raw_db
from app.db.qdrant import ensure_qdrant_collections, get_qdrant_health
from app.api.sessions import router as sessions_router
from app.api.memory import router as memory_router
from app.providers.llm_provider import get_llm_provider
from app.worker import reflection_worker
from app.telegram.bot import start_telegram_bot, stop_telegram_bot
from app.scheduler.setup import start_scheduler, shutdown_scheduler

from app.api.telemetry_routes import router as telemetry_router
from app.api.terminal_routes import router as terminal_router
from app.api.cron_routes import router as cron_router

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown events."""
    # Ensure database tables exist (ORM models + raw SQLite schema)
    init_orm_db()
    init_raw_db()
    # Ensure vector collections are initialized
    try:
        ensure_qdrant_collections()
    except Exception as exc:
        logger.warning("Qdrant initialization deferred", error=str(exc))

    # Launch autonomous reflection background worker
    worker_task = asyncio.create_task(reflection_worker.start())

    # Start Telegram Daemon Gateway cooperatively
    await start_telegram_bot()

    # Start APScheduler cooperatively
    await start_scheduler()

    yield

    # Shutdown background worker cleanly
    await shutdown_scheduler()
    await stop_telegram_bot()
    reflection_worker.stop()
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Personal Adaptive AI Agent API",
    description="Backend API for personal adaptive AI agent with persistent episodic, semantic, and procedural memory.",
    version="0.5.0",
    lifespan=lifespan,
)

# Configure CORS for local UI and development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(sessions_router, prefix="/api")
app.include_router(memory_router, prefix="/api/memory", tags=["Memory"])
app.include_router(telemetry_router, prefix="/api/telemetry")
app.include_router(terminal_router, prefix="/api/terminal")
app.include_router(cron_router, prefix="/api/cron")


@app.websocket("/ws/telemetry")
async def websocket_telemetry_alias(websocket: WebSocket) -> None:
    """Convenience alias for /api/telemetry/ws for direct client connections."""
    from app.api.telemetry_routes import websocket_telemetry
    await websocket_telemetry(websocket)


@app.get("/api/health", tags=["Health"])
def health_check() -> Dict[str, Any]:
    """Health check endpoint for Phase 5 verification."""
    return {
        "status": "healthy",
        "service": "personal-agent-backend",
        "phase": "5 - Procedural Tool Calling, Confidence Reinforcement & Memory Decay",
        "version": "0.5.0",
    }


@app.get("/api/system/health", tags=["Health"])
def system_health_check() -> Dict[str, Any]:
    """System health endpoint matching SCHEMA.md specification."""
    llm = get_llm_provider()
    qdrant_info = get_qdrant_health()
    return {
        "status": "healthy",
        "database": f"connected ({settings.resolved_database_url.split('://')[0]})",
        "vector_db": f"{qdrant_info.get('status', 'unknown')} (collections: {qdrant_info.get('collections', [])})",
        "llm_provider": llm.__class__.__name__,
        "model": getattr(llm, "model", settings.LLM_MODEL_PRIMARY),
    }


# --- Frontend HUD Serving ---
# Paths are resolved relative to this file so they work regardless of CWD.
_repo_root = Path(__file__).resolve().parent.parent.parent
_dist = _repo_root / "frontend" / "dist"
_assets = _dist / "assets"

if _assets.exists():
    # Mount /assets separately so JS/CSS bundles are served efficiently.
    app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")
    logger.info("Frontend assets mounted", path=str(_assets))


@app.get("/", include_in_schema=False)
async def serve_hud() -> Response:
    """Serve the Cyberpunk Operator HUD. Falls back to API info if dist is missing."""
    index = _dist / "index.html"
    if index.exists():
        return FileResponse(str(index))
    # Graceful fallback — shouldn't happen if frontend is built
    return JSONResponse({
        "name": "Personal Adaptive AI Agent API",
        "health": "/api/health",
        "docs": "/docs",
        "warning": f"Frontend HUD not built. Expected: {_dist}",
    })


if __name__ == "__main__":
    import os
    import uvicorn
    server_port = int(os.getenv("PORT", str(getattr(settings, "PORT", 8000))))
    uvicorn.run("app.main:app", host="0.0.0.0", port=server_port, reload=True)