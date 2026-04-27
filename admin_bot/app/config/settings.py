"""Application settings loaded from environment variables using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, Field, AliasChoices
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
    remnawave_api_key: str = Field(
        "",
        validation_alias=AliasChoices("REMNAWAVE_TOKEN", "REMNAWAVE_API_KEY"),
    )
    remnawave_timeout_seconds: int = Field(5, validation_alias="REMNAWAVE_TIMEOUT_SECONDS")

    # Database
    user_bot_db_path: str = ""

    # Backup
    backup_dir: str = "./backups"
    backup_retention_days: int = 30
    subscription_db_backup_dir: str = "./backups/subscription_db"
    remnawave_backup_enabled: bool = Field(True, validation_alias="REMNAWAVE_BACKUP_ENABLED")

    # Monitoring
    monitor_interval_minutes: int = 5
    node_ram_max_percent: int = 70
    internal_squad_max_users: int = 30
    internal_squad_prefix: str = "internal"
    lte_traffic_monitor_enabled: bool = Field(True, validation_alias="LTE_TRAFFIC_MONITOR_ENABLED")
    lte_squad_name: str = Field("LTE", validation_alias="LTE_SQUAD_NAME")
    lte_free_gb_per_30d: int = Field(1, validation_alias="LTE_FREE_GB_PER_30D")
    lte_period_days: int = Field(30, validation_alias="LTE_PERIOD_DAYS")
    lte_limited_node_uuids: List[str] = Field(default_factory=list, validation_alias="LTE_LIMITED_NODE_UUIDS")
    lte_limited_node_name_keywords: List[str] = Field(
        default_factory=lambda: ["LTE"],
        validation_alias="LTE_LIMITED_NODE_NAME_KEYWORDS",
    )

    # Free squad / infinite-expire model. When a user's subscription ends locally
    # we strip paid squads, demote them to FREE_SQUAD_NAME (limited servers) and
    # force-disconnect open sessions. Panel expireAt is kept at INFINITE_EXPIRE_DATE
    # so we are the single source of truth for subscription days.
    free_squad_name: str = Field("FREE", validation_alias="FREE_SQUAD_NAME")
    subscription_expire_monitor_enabled: bool = Field(
        True,
        validation_alias="SUBSCRIPTION_EXPIRE_MONITOR_ENABLED",
    )
    infinite_expire_date: str = Field(
        "2099-12-31T23:59:59.000Z",
        validation_alias="INFINITE_EXPIRE_DATE",
    )

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

    @field_validator("lte_limited_node_uuids", "lte_limited_node_name_keywords", mode="before")
    @classmethod
    def parse_csv_list(cls, value):
        """Parse comma-separated values into list[str]."""
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    @field_validator("lte_squad_name", mode="before")
    @classmethod
    def normalize_lte_squad_name(cls, value):
        """Ensure LTE squad name is non-empty."""
        if isinstance(value, str) and value.strip():
            return value.strip()
        return "LTE"

    @field_validator("free_squad_name", mode="before")
    @classmethod
    def normalize_free_squad_name(cls, value):
        """Ensure FREE squad name is non-empty."""
        if isinstance(value, str) and value.strip():
            return value.strip()
        return "FREE"

    @field_validator("infinite_expire_date", mode="before")
    @classmethod
    def normalize_infinite_expire(cls, value):
        """Strip whitespace, fall back to a far-future date."""
        if isinstance(value, str) and value.strip():
            return value.strip()
        return "2099-12-31T23:59:59.000Z"

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
