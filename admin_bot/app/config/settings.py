"""Application settings loaded from environment variables using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, ClassVar
from pathlib import Path


class Settings(BaseSettings):
    """Application configuration."""

    base_dir: ClassVar[Path] = Path(__file__).resolve().parents[2]
    model_config = SettingsConfigDict(
        env_file=base_dir / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Telegram Bot
    bot_token: str
    admin_ids: List[int] = []

    # API Configuration
    remnawave_api_url: str = "https://api.remnawave.com"
    remnawave_api_key: str = ""

    # Database
    sqlite_db_path: str = "./data/bot.db"
    user_bot_db_path: str = ""

    # Backup
    backup_dir: str = "./backups"
    backup_retention_days: int = 30
    subscription_db_backup_dir: str = "./backups/subscription_db"

    # Monitoring
    monitor_interval_minutes: int = 5
    node_ram_max_percent: int = 70
    squad_max_users: int = 10

    # Logging
    log_level: str = "INFO"
    log_file: str = "./logs/bot.log"

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value):
        """Parse admin IDs from int or comma-separated string."""
        if value is None or value == "":
            return []
        if isinstance(value, int):
            return [value]
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        return value

    @field_validator("remnawave_api_url", "remnawave_api_key", mode="before")
    @classmethod
    def strip_env_values(cls, value):
        """Strip whitespace from env values."""
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("user_bot_db_path", mode="before")
    @classmethod
    def set_user_bot_db_path(cls, value):
        """Set default user_bot DB path if not provided."""
        if isinstance(value, str) and value.strip():
            return value.strip()
        return str(cls.base_dir.parent / "user_bot" / "data" / "subscription.db")


settings = Settings()
