import sqlite3
import asyncio
import os
from pathlib import Path
from typing import Any, Callable, List, Tuple, Dict, Optional

def get_connection() -> sqlite3.Connection:
    """
    Creates a new SQLite connection with the required PRAGMAs.
    Must be called per-thread if not shared carefully, but we'll use a new connection per transaction.
    """
    raw_db_path = os.getenv("SQLITE_DB_PATH", "data/athena.db")
    if raw_db_path == ":memory:":
        db_path = ":memory:"
    else:
        p = Path(raw_db_path)
        if p.is_absolute():
            db_file = p
        else:
            # Anchor relative path to project root
            repo_root = Path(__file__).resolve().parent.parent.parent
            if (repo_root / "backend").exists() or (repo_root / ".git").exists():
                db_file = (repo_root / p).resolve()
            else:
                db_file = (Path(__file__).resolve().parent.parent / p).resolve()
        db_file.parent.mkdir(parents=True, exist_ok=True)
        db_path = str(db_file)
        
    conn = sqlite3.connect(db_path, isolation_level=None) # We handle transactions manually
    conn.row_factory = sqlite3.Row
    
    # Apply essential pragmas for zero-infra architecture
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    
    return conn

def init_db():
    """Initializes the database schema from schema.sql if not already created."""
    schema_path = Path(__file__).parent / "schema.sql"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    
    conn = get_connection()
    try:
        conn.executescript(schema_sql)
    finally:
        conn.close()

async def execute_read_async(query: str, params: Tuple = ()) -> List[sqlite3.Row]:
    """
    Executes a read query asynchronously by delegating to a thread pool.
    """
    def _read() -> List[sqlite3.Row]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()
        finally:
            conn.close()
            
    return await asyncio.to_thread(_read)

async def execute_write_async(query: str, params: Tuple = ()) -> int:
    """
    Executes a write query asynchronously. Returns the rowcount.
    """
    def _write() -> int:
        conn = get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
            
    return await asyncio.to_thread(_write)

async def execute_transaction_async(func: Callable[[sqlite3.Connection], Any]) -> Any:
    """
    Executes a block of operations within a single transaction in a separate thread.
    `func` takes a sqlite3.Connection and performs synchronous operations.
    """
    def _tx() -> Any:
        conn = get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE")
            result = func(conn)
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
            
    return await asyncio.to_thread(_tx)
