import json
import sqlite3
from typing import Dict, Any, Optional

from app.db.connection import execute_read_async, execute_write_async

class KeyValueStore:
    """
    Persistent key-value profile memory store backed by the user_kv SQLite table.
    Values are automatically JSON encoded/decoded.
    """

    @staticmethod
    async def get(key: str) -> Optional[Any]:
        """
        Retrieves a value by key. Returns None if the key does not exist.
        """
        query = "SELECT value FROM user_kv WHERE key = ?"
        rows = await execute_read_async(query, (key,))
        if rows:
            raw_value = rows[0]["value"]
            try:
                return json.loads(raw_value)
            except json.JSONDecodeError:
                return raw_value
        return None

    @staticmethod
    async def set(key: str, value: Any) -> None:
        """
        Sets a key to a specified value. Upserts if the key already exists.
        """
        encoded_value = json.dumps(value)
        
        # SQLite UPSERT syntax
        query = """
        INSERT INTO user_kv (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET 
            value = excluded.value,
            updated_at = excluded.updated_at
        """
        await execute_write_async(query, (key, encoded_value))

    @staticmethod
    async def list_all() -> Dict[str, Any]:
        """
        Retrieves all key-value pairs as a dictionary.
        """
        query = "SELECT key, value FROM user_kv"
        rows = await execute_read_async(query)
        
        result = {}
        for row in rows:
            key = row["key"]
            raw_value = row["value"]
            try:
                result[key] = json.loads(raw_value)
            except json.JSONDecodeError:
                result[key] = raw_value
                
        return result
