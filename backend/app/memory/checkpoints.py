import uuid
from typing import List, Dict, Any

from app.db.connection import execute_read_async, execute_write_async
from app.providers.base import LLMProvider

class CheckpointManager:
    """
    Manages session checkpoints, providing rolling summarization when turn limits are exceeded.
    """
    MAX_TURNS = 20

    @staticmethod
    async def append_turn(session_id: str, role: str, content: str) -> None:
        """
        Appends a raw conversation turn.
        """
        turn_id = uuid.uuid4().hex
        query = """
        INSERT INTO checkpoints (id, session_id, role, content, is_summary)
        VALUES (?, ?, ?, ?, 0)
        """
        await execute_write_async(query, (turn_id, session_id, role, content))

    @staticmethod
    async def get_recent_checkpoints(session_id: str, limit: int = MAX_TURNS) -> List[Dict[str, Any]]:
        """
        Fetches the latest turns, up to the specified limit, sorted chronologically.
        """
        # Fetching DESC for limit, then sorting ASC in Python to maintain conversation order
        query = """
        SELECT id, role, content, is_summary, created_at
        FROM checkpoints
        WHERE session_id = ?
        ORDER BY created_at DESC, is_summary ASC, rowid DESC
        LIMIT ?
        """
        rows = await execute_read_async(query, (session_id, limit))
        
        # Reverse to chronological
        result = [dict(row) for row in rows]
        result.reverse()
        return result

    @staticmethod
    async def compact_overflow_turns(session_id: str, llm_provider: LLMProvider) -> None:
        """
        Checks if the turns for a session exceed MAX_TURNS. If they do, rolls up the oldest turns
        into a single summary row and prunes the raw rows.
        """
        # Get count
        count_query = "SELECT COUNT(*) as cnt FROM checkpoints WHERE session_id = ?"
        count_rows = await execute_read_async(count_query, (session_id,))
        count = count_rows[0]["cnt"]

        if count <= CheckpointManager.MAX_TURNS:
            return

        # Fetch all except the last 10 (keep latest 10 pristine)
        keep_recent = 10
        to_summarize_count = count - keep_recent
        
        fetch_old_query = """
        SELECT id, role, content, created_at 
        FROM checkpoints 
        WHERE session_id = ? 
        ORDER BY created_at ASC, rowid ASC 
        LIMIT ?
        """
        old_rows = await execute_read_async(fetch_old_query, (session_id, to_summarize_count))
        
        if not old_rows:
            return
            
        old_ids = [row["id"] for row in old_rows]
        
        # Build prompt for summarization
        transcript = "\n".join([f"{row['role']}: {row['content']}" for row in old_rows])
        messages = [
            {
                "role": "system", 
                "content": "You are a summarizing agent. Summarize the following conversation history compactly. Retain key facts, decisions, and context."
            },
            {
                "role": "user",
                "content": transcript
            }
        ]
        
        response = await llm_provider.complete(messages=messages)
        summary_content = response.content or "Summary failed."
        
        # Use the created_at of the newest summarized row to maintain chronological position
        summary_created_at = old_rows[-1]["created_at"]
        
        # Insert summary row
        summary_id = uuid.uuid4().hex
        insert_summary = """
        INSERT INTO checkpoints (id, session_id, role, content, is_summary, created_at)
        VALUES (?, ?, 'system', ?, 1, ?)
        """
        await execute_write_async(insert_summary, (summary_id, session_id, summary_content, summary_created_at))
        
        # Delete old rows (simulating IN clause with parameters)
        placeholders = ",".join(["?"] * len(old_ids))
        delete_old = f"DELETE FROM checkpoints WHERE id IN ({placeholders})"
        await execute_write_async(delete_old, tuple(old_ids))
