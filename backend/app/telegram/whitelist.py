from typing import Set
import structlog

from app.config import settings
from app.db.connection import execute_read_async

logger = structlog.get_logger(__name__)

class WhitelistGuard:
    """
    In-memory O(1) whitelist guard for Telegram incoming messages (Ghost Mode).
    """
    _allowed_ids: Set[int] = set()
    _initialized: bool = False

    @classmethod
    async def initialize(cls) -> None:
        """
        Loads allowed user IDs from environment variables and the allowed_users database table.
        """
        cls._allowed_ids.clear()
        
        # Load from .env config
        env_ids_str = settings.TELEGRAM_ALLOWED_USER_IDS.strip()
        if env_ids_str:
            for part in env_ids_str.split(","):
                part = part.strip()
                if part.isdigit():
                    cls._allowed_ids.add(int(part))
        
        # Load from allowed_users table
        try:
            rows = await execute_read_async("SELECT id FROM allowed_users")
            for row in rows:
                db_id = row["id"]
                if db_id.isdigit():
                    cls._allowed_ids.add(int(db_id))
        except Exception as e:
            logger.error("Failed to load allowed users from database", error=str(e))
            
        cls._initialized = True
        logger.info("Telegram Whitelist Guard initialized", allowed_count=len(cls._allowed_ids))

    @classmethod
    def is_authorized(cls, user_id: int) -> bool:
        """
        Checks if a user is allowed to interact with the bot.
        """
        if not cls._initialized:
            logger.warning("WhitelistGuard checked before initialization!")
            
        return user_id in cls._allowed_ids
