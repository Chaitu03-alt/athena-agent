"""Database engine and session management."""

import os
from pathlib import Path
from typing import Generator
from sqlalchemy import event
from sqlmodel import Session as SQLModelSession, SQLModel, create_engine
from app.config import settings

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

engine = create_engine(
    db_url,
    echo=(settings.LOG_LEVEL.lower() == "debug"),
    connect_args=connect_args,
)

# Enable foreign keys for SQLite
if db_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_session() -> Generator[SQLModelSession, None, None]:
    """Provide a transactional database session for requests."""
    with SQLModelSession(engine) as session:
        yield session


def init_db() -> None:
    """Initialize database tables."""
    SQLModel.metadata.create_all(engine)
