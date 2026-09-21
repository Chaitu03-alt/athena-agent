import structlog
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from app.config import settings
from app.telegram.whitelist import WhitelistGuard
from app.telegram.commands import start_command, status_command, reset_command, memory_command
from app.telegram.handlers import handle_message

logger = structlog.get_logger(__name__)

# Global reference to the application for clean shutdown
_telegram_app = None

def get_telegram_app():
    """Retrieve the global Telegram Application instance."""
    return _telegram_app

async def start_telegram_bot() -> None:
    """
    Initializes the Telegram bot Application cooperatively and starts polling.
    Designed to run alongside FastAPI's uvicorn event loop.
    """
    global _telegram_app
    
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN is not set. Telegram Daemon Gateway will not start.")
        return
        
    await WhitelistGuard.initialize()

    # Build application
    _telegram_app = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()
    
    # Wire handlers
    _telegram_app.add_handler(CommandHandler("start", start_command))
    _telegram_app.add_handler(CommandHandler("status", status_command))
    _telegram_app.add_handler(CommandHandler("reset", reset_command))
    _telegram_app.add_handler(CommandHandler("memory", memory_command))
    
    # Text message handler (ignore commands)
    _telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Initialize and start cooperatively
    await _telegram_app.initialize()
    await _telegram_app.start()
    await _telegram_app.updater.start_polling()
    
    logger.info("Telegram Daemon Gateway started cooperatively.")


async def stop_telegram_bot() -> None:
    """
    Gracefully stops the Telegram bot Application and its updater.
    """
    global _telegram_app
    if _telegram_app:
        logger.info("Stopping Telegram Daemon Gateway...")
        await _telegram_app.updater.stop()
        await _telegram_app.stop()
        await _telegram_app.shutdown()
        _telegram_app = None
        logger.info("Telegram Daemon Gateway stopped.")
