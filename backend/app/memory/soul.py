import uuid
import sqlite3
from typing import List, Dict, Any, Optional
from app.db.connection import execute_read_async, execute_transaction_async

class SoulPromptManager:
    """
    Manages the versioned 'soul prompt' for the agent.
    Only one prompt can be active (is_active = 1) at any given time, enforced by a partial unique index.
    """

    @staticmethod
    async def get_active_soul() -> Optional[Dict[str, Any]]:
        """
        Retrieves the currently active soul prompt.
        """
        query = "SELECT id, prompt_text, created_at FROM soul_prompts WHERE is_active = 1"
        rows = await execute_read_async(query)
        if rows:
            return dict(rows[0])
        return None

    @staticmethod
    async def set_soul_prompt(prompt_text: str) -> str:
        """
        Sets a new soul prompt as active, deactivating the previous one in a single atomic transaction.
        Returns the ID of the new prompt.
        """
        new_id = uuid.uuid4().hex

        def _transaction(conn: sqlite3.Connection) -> str:
            # Deactivate current active prompt
            conn.execute("UPDATE soul_prompts SET is_active = 0 WHERE is_active = 1")
            
            # Insert the new active prompt
            conn.execute(
                "INSERT INTO soul_prompts (id, prompt_text, is_active) VALUES (?, ?, 1)",
                (new_id, prompt_text)
            )
            return new_id

        return await execute_transaction_async(_transaction)

    @staticmethod
    async def get_version_history() -> List[Dict[str, Any]]:
        """
        Retrieves the full history of soul prompts ordered by creation date descending.
        """
        query = "SELECT id, prompt_text, is_active, created_at FROM soul_prompts ORDER BY created_at DESC"
        rows = await execute_read_async(query)
        return [dict(row) for row in rows]
