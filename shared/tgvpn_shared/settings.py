"""
One settings model for both bots.

Before Phase 2 configuration was parsed twice and inconsistently: admin_bot had
a pydantic `Settings` model, while user_bot read `os.getenv` directly at ~20
call sites, each with its own defaulting and coercion. Both read the same root
`.env`.

Everything is optional here on purpose. A single model shared by three
entrypoints (admin_bot, user_bot polling, user_bot webhook) can't demand every
field, since none of them needs all of them -- the webhook process has no use
for `admin_bot_token`. Entrypoints assert what they actually require via
`require()` at startup, which fails with a readable message instead of a
pydantic traceback.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# shared/tgvpn_shared/settings.py -> shared/tgvpn_shared -> shared -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Everything both bots read from the environment."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        # Fields carry `validation_alias` for their env var names; without
        # this, constructing Settings(...) in Python would only accept those
        # alias spellings and silently ignore the field names.
        populate_by_name=True,
    )

    # -- Telegram ----------------------------------------------------------
    admin_bot_token: str = Field("", validation_alias="ADMIN_BOT_TOKEN")
    user_bot_token: str = Field("", validation_alias="USER_BOT_TOKEN")
    telegram_bot_username: str = Field("", validation_alias="TELEGRAM_BOT_USERNAME")
    # Kept as the raw string and split in `admin_ids` below. Typing this as
    # `list[int]` makes pydantic-settings try to JSON-decode the env value
    # *before* any validator runs, so a plain `ADMIN_IDS=` or `ADMIN_IDS=1,2`
    # raises SettingsError instead of parsing -- a real crash this project hit.
    admin_ids_raw: str = Field("", validation_alias="ADMIN_IDS")

    # -- Database ----------------------------------------------------------
    database_url: str = Field("", validation_alias="DATABASE_URL")

    # -- Remnawave ---------------------------------------------------------
    remnawave_base_url: str = Field("", validation_alias="REMNAWAVE_BASE_URL")
    remnawave_username: str = Field("", validation_alias="REMNAWAVE_USERNAME")
    remnawave_password: str = Field("", validation_alias="REMNAWAVE_PASSWORD")
    remnawave_token: str = Field("", validation_alias="REMNAWAVE_TOKEN")
    remnawave_api_key: str = Field("", validation_alias="REMNAWAVE_API_KEY")
    remnawave_timeout_seconds: int = Field(5, validation_alias="REMNAWAVE_TIMEOUT_SECONDS")

    # -- YooKassa ----------------------------------------------------------
    yookassa_shop_id: str = Field("", validation_alias="YOOKASSA_SHOP_ID")
    yookassa_secret_key: str = Field("", validation_alias="YOOKASSA_SECRET_KEY")

    # -- Webhook server ----------------------------------------------------
    webhook_host: str = Field("127.0.0.1", validation_alias="WEBHOOK_HOST")
    webhook_port: int = Field(8000, validation_alias="WEBHOOK_PORT")
    webhook_shutdown_timeout: float = Field(5.0, validation_alias="WEBHOOK_SHUTDOWN_TIMEOUT")

    # -- Squads ------------------------------------------------------------
    internal_squad_max_users: int = Field(30, validation_alias="INTERNAL_SQUAD_MAX_USERS")
    internal_squad_prefix: str = Field("internal", validation_alias="INTERNAL_SQUAD_PREFIX")

    # -- Subscription / UX -------------------------------------------------
    trial_days: int = Field(30, validation_alias="TRIAL_DAYS")
    show_video_instructions: bool = Field(True, validation_alias="SHOW_VIDEO_INSTRUCTIONS")
    faq_url: str = Field("https://nitratex-company.gitbook.io/kairavpn/", validation_alias="FAQ_URL")
    status_channel_url: str = Field("https://t.me/nitratex1", validation_alias="STATUS_CHANNEL_URL")

    # -- Backups (admin_bot) ----------------------------------------------
    backup_dir: str = Field("./backups", validation_alias="BACKUP_DIR")
    backup_retention_days: int = Field(30, validation_alias="BACKUP_RETENTION_DAYS")
    subscription_db_backup_dir: str = Field(
        "./backups/subscription_db", validation_alias="SUBSCRIPTION_DB_BACKUP_DIR"
    )
    remnawave_backup_enabled: bool = Field(True, validation_alias="REMNAWAVE_BACKUP_ENABLED")

    # -- Monitoring (admin_bot) -------------------------------------------
    monitor_interval_minutes: int = Field(5, validation_alias="MONITOR_INTERVAL_MINUTES")
    node_ram_max_percent: int = Field(70, validation_alias="NODE_RAM_MAX_PERCENT")

    # -- Logging -----------------------------------------------------------
    log_level: str = Field("INFO", validation_alias="LOG_LEVEL")
    log_file: str = Field("./logs/bot.log", validation_alias="LOG_FILE")

    # -- Derived -----------------------------------------------------------

    @property
    def admin_ids(self) -> list[int]:
        """`ADMIN_IDS` as ints. Accepts comma- or space-separated values."""
        parts = self.admin_ids_raw.replace(",", " ").split()
        return [int(part) for part in parts if part.lstrip("-").isdigit()]

    @property
    def primary_admin_id(self) -> int:
        """First configured admin, or 0 when none is set."""
        ids = self.admin_ids
        return ids[0] if ids else 0

    @property
    def remnawave_api_token(self) -> str:
        """`REMNAWAVE_TOKEN` and `REMNAWAVE_API_KEY` are interchangeable aliases."""
        return (self.remnawave_token or self.remnawave_api_key).strip()

    def require(self, *names: str) -> None:
        """
        Fail fast at startup if a required setting is missing.

        Names are attribute names on this model (`"user_bot_token"`), so an
        entrypoint declares exactly what it needs rather than every process
        having to satisfy every other process's requirements.
        """
        missing = [name for name in names if not getattr(self, name, None)]
        if missing:
            raise RuntimeError(
                "Missing required configuration: "
                + ", ".join(sorted(missing))
                + f". Set them in {REPO_ROOT / '.env'} or the environment."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings singleton."""
    return Settings()


def reload_settings() -> Settings:
    """Drop the cached instance and re-read the environment (used by tests)."""
    get_settings.cache_clear()
    return get_settings()
