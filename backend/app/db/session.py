import asyncio
import os
from pathlib import Path
from typing import Callable, Generator, TypeVar
from sqlalchemy import event
from sqlmodel import Session as SQLModelSession, SQLModel, create_engine
from app.config import settings

T = TypeVar("T")

# Ensure data directory exists if using default SQLite
if settings.DATABASE_URL.startswith("sqlite"):
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    if db_path.startswith("./") or db_path.startswith(".\\") or not os.path.isabs(db_path):
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

# Connect args for SQLite to allow multi-threaded access in FastAPI
connect_args = {}
db_url = settings.resolved_database_url
if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine_kwargs = {
    "echo": (settings.LOG_LEVEL.lower() == "debug"),
    "connect_args": connect_args,
    "pool_pre_ping": True,
    "pool_recycle": 1800,
}
if not db_url.startswith("sqlite"):
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_engine(
    db_url,
    **engine_kwargs,
)

# Enable foreign keys and register missing math functions for SQLite
if db_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
        # Register custom least function in SQLite so func.least works identically to Postgres
        dbapi_connection.create_function("least", -1, min)


async def run_db(func: Callable[..., T], *args, **kwargs) -> T:
    """Offload blocking sync SQLModel / DB operations to a thread pool executor."""
    return await asyncio.to_thread(func, *args, **kwargs)


def get_session() -> Generator[SQLModelSession, None, None]:
    """Provide a transactional database session for requests with rollback on error."""
    with SQLModelSession(engine) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


def init_db() -> None:
    """Initialize database tables."""
    SQLModel.metadata.create_all(engine)

