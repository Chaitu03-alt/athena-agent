import sys
from pathlib import Path

# Ensure package root is in sys.path so 'app' is importable when executed directly
_app_root = Path(__file__).resolve().parent.parent
if str(_app_root) not in sys.path:
    sys.path.insert(0, str(_app_root))

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import asyncio
from app.config import settings
from app.db.session import init_db
from app.db.qdrant import ensure_qdrant_collections, get_qdrant_health
from app.api.sessions import router as sessions_router
from app.api.memory import router as memory_router
from app.providers.llm_provider import get_llm_provider
from app.worker import reflection_worker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown events."""
    # Ensure database tables exist
    init_db()
    # Ensure vector collections are initialized
    try:
        ensure_qdrant_collections()
    except Exception as exc:
        print(f"Warning: Qdrant initialization deferred: {exc}")

    # Launch autonomous reflection background worker
    worker_task = asyncio.create_task(reflection_worker.start())

    yield

    # Shutdown background worker cleanly
    reflection_worker.stop()
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Personal Adaptive AI Agent API",
    description="Backend API for personal adaptive AI agent with persistent episodic, semantic, and procedural memory.",
    version="0.3.0",
    lifespan=lifespan,
)

# Configure CORS for local UI and development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production environments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(sessions_router, prefix="/api")
app.include_router(memory_router, prefix="/api/memory", tags=["Memory"])


@app.get("/api/health", tags=["Health"])
def health_check() -> Dict[str, Any]:
    """Health check endpoint for Phase 3 verification."""
    return {
        "status": "healthy",
        "service": "personal-agent-backend",
        "phase": "3 - Autonomous Reflection Worker & Rule Lifecycle",
        "version": "0.3.0",
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


@app.get("/", tags=["Root"])
def root() -> Dict[str, str]:
    """Root endpoint."""
    return {
        "name": "Personal Adaptive AI Agent API",
        "health": "/api/health",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

