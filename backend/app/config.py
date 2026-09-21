"""Application configuration using Pydantic Settings."""

from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Core settings for backend services."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment & Server
    ENVIRONMENT: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "info"

    # Database
    # Default to local SQLite if PostgreSQL is not specified or for easy zero-setup local runs
    DATABASE_URL: str = "sqlite:///./data/personal_agent.db"

    @property
    def resolved_database_url(self) -> str:
        """Resolve database URL ensuring SQLite relative paths are anchored to project root."""
        if self.DATABASE_URL.startswith("sqlite:///") and not self.DATABASE_URL.startswith("sqlite:////"):
            rel_path = self.DATABASE_URL.replace("sqlite:///", "")
            # Project root: check repo root or backend root
            candidate_roots = [
                Path(__file__).resolve().parent.parent.parent,
                Path(__file__).resolve().parent.parent,
            ]
            root_dir = candidate_roots[0]
            for candidate in candidate_roots:
                if (candidate / "pyproject.toml").exists() or (candidate / ".git").exists():
                    root_dir = candidate
                    break
            abs_db_path = (root_dir / rel_path).resolve()
            abs_db_path.parent.mkdir(parents=True, exist_ok=True)
            # Use forward slashes for SQLite URI
            return f"sqlite:///{abs_db_path.as_posix()}"
        return self.DATABASE_URL

    # Vector DB
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_GRPC_PORT: int = 6334

    # LLM Providers & Chains
    ANTHROPIC_API_KEY: Optional[str] = None
    LLM_MODEL_PRIMARY: str = "claude-sonnet-4-6"
    LLM_MODEL_LIGHT: str = "claude-haiku-4-5-20251001"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None

    # Agent Autonomous Loop & Sandbox Settings
    MAX_TOOL_CALLS: int = 5
    TOOL_TIMEOUT_SECONDS: int = 15
    WORKSPACE_DIR: str = "./workspace"

    @property
    def resolved_workspace_dir(self) -> Path:
        """Resolve workspace directory to an absolute path anchored to project/backend root."""
        workspace_path = Path(self.WORKSPACE_DIR)
        if workspace_path.is_absolute():
            resolved = workspace_path.resolve()
        else:
            candidate_roots = [
                Path(__file__).resolve().parent.parent.parent,
                Path(__file__).resolve().parent.parent,
            ]
            root_dir = candidate_roots[0]
            for candidate in candidate_roots:
                if (candidate / "pyproject.toml").exists() or (candidate / ".git").exists():
                    root_dir = candidate
                    break
            resolved = (root_dir / workspace_path).resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    # Embedding Provider
    EMBEDDING_MODE: str = "hosted"  # 'hosted' | 'local'
    VOYAGE_API_KEY: Optional[str] = None

    # Telegram Daemon
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_ALLOWED_USER_IDS: str = ""  # Comma-separated list of IDs

    # Security & Guardrails
    APP_ACCESS_TOKEN: str = "change-me-to-a-secure-random-token"
    SANDBOX_MODE: str = "subprocess"
    CONFIRM_DESTRUCTIVE_ACTIONS: bool = True


settings = Settings()

# Top-level aliases for direct imports (e.g. `from config import MAX_TOOL_CALLS`)
GROQ_API_KEY = settings.GROQ_API_KEY
OPENROUTER_API_KEY = settings.OPENROUTER_API_KEY
MAX_TOOL_CALLS = settings.MAX_TOOL_CALLS
TOOL_TIMEOUT_SECONDS = settings.TOOL_TIMEOUT_SECONDS
WORKSPACE_DIR = settings.WORKSPACE_DIR

