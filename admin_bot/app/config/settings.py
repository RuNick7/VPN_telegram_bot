"""Application settings loaded from environment variables using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, Field
from typing import List, ClassVar
from pathlib import Path


class Settings(BaseSettings):
    """Application configuration."""

    base_dir: ClassVar[Path] = Path(__file__).resolve().parents[2]
    model_config = SettingsConfigDict(
        env_file=base_dir.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Telegram Bot
    admin_bot_token: str = Field(..., validation_alias="Admin_bot_token")
    admin_ids: List[int] = []
    # Token user_bot для рассылки (пользователи общаются с user_bot, не с админ-ботом)
    user_bot_token: str = Field("", validation_alias="USER_BOT_TOKEN")

    # API Configuration
    remnawave_api_url: str = Field("https://api.remnawave.com", validation_alias="REMNAWAVE_BASE_URL")
    remnawave_api_key: str = Field("", validation_alias="REMNAWAVE_TOKEN")
    remnawave_timeout_seconds: int = Field(5, validation_alias="REMNAWAVE_TIMEOUT_SECONDS")

    # Database
    user_bot_db_path: str = ""

    # Backup
    backup_dir: str = "./backups"
    backup_retention_days: int = 30
    subscription_db_backup_dir: str = "./backups/subscription_db"

    # Monitoring
    monitor_interval_minutes: int = 5
    node_ram_max_percent: int = 70
    internal_squad_max_users: int = 30
    internal_squad_prefix: str = "internal"

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

    @field_validator("remnawave_timeout_seconds", mode="before")
    @classmethod
    def parse_timeout(cls, value):
        """Parse timeout seconds from env; fallback to default."""
        if value is None or value == "":
            return 5
        try:
            return int(value)
        except (TypeError, ValueError):
            return 5

    @field_validator("user_bot_db_path", mode="before")
    @classmethod
    def set_user_bot_db_path(cls, value):
        """Set default user_bot DB path if not provided."""
        if isinstance(value, str) and value.strip():
            return value.strip()
        return str(cls.base_dir.parent / "user_bot" / "data" / "subscription.db")


settings = Settings()
