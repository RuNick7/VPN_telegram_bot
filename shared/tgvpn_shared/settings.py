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
    # The one squad every paying subscriber goes into. Named, not derived from
    # a prefix: users are no longer spread across `internal-1..N`, because load
    # is handled by balancers in front of the nodes rather than by splitting
    # people up. The panel must contain a squad with exactly this name.
    paid_squad_name: str = Field("internal", validation_alias="PAID_SQUAD_NAME")

    # -- FREE tier (Phase 3) -----------------------------------------------
    # Off by default, and deliberately so. Turning it on changes how expiry is
    # enforced: panel accounts stop expiring on their own and a background job
    # becomes the only thing moving lapsed users off paid squads. That is safe
    # only once the health monitor below is known to alert, so enabling it is
    # a separate, deliberate act from deploying the code.
    free_tier_enabled: bool = Field(False, validation_alias="FREE_TIER_ENABLED")
    free_squad_name: str = Field("FREE", validation_alias="FREE_SQUAD_NAME")
    # How far ahead panel expireAt is pushed once the FREE tier owns expiry.
    # Remnawave has no "never expires", so this stands in for it.
    free_tier_panel_expire_years: int = Field(10, validation_alias="FREE_TIER_PANEL_EXPIRE_YEARS")

    # -- LTE quotas (Phase 3) ----------------------------------------------
    lte_enabled: bool = Field(False, validation_alias="LTE_ENABLED")
    lte_squad_name: str = Field("LTE", validation_alias="LTE_SQUAD_NAME")
    lte_cycle_days: int = Field(30, validation_alias="LTE_CYCLE_DAYS")
    lte_free_gb_per_cycle: int = Field(10, validation_alias="LTE_FREE_GB_PER_CYCLE")
    # Which nodes count against the LTE quota. UUIDs win when both are set;
    # the name substrings are the convenient form for a human-managed panel.
    lte_node_uuids_raw: str = Field("", validation_alias="LTE_NODE_UUIDS")
    lte_node_name_keywords_raw: str = Field("lte", validation_alias="LTE_NODE_NAME_KEYWORDS")

    # -- Service health monitoring (Phase 3) -------------------------------
    service_monitor_enabled: bool = Field(True, validation_alias="SERVICE_MONITOR_ENABLED")
    webhook_health_url: str = Field(
        "http://127.0.0.1:8000/health", validation_alias="WEBHOOK_HEALTH_URL"
    )
    user_bot_heartbeat_path: str = Field(
        "/tmp/user_bot_heartbeat", validation_alias="USER_BOT_HEARTBEAT_PATH"
    )
    service_monitor_stale_minutes: int = Field(
        10, validation_alias="SERVICE_MONITOR_STALE_MINUTES"
    )
    # A job is considered stale at this multiple of its own interval -- one
    # missed tick can be scheduling jitter, two in a row cannot.
    job_stale_interval_multiplier: float = Field(
        2.0, validation_alias="JOB_STALE_INTERVAL_MULTIPLIER"
    )

    # -- Subscription / UX -------------------------------------------------
    # The free period is two halves. `trial_days` is what signing up is worth,
    # on whichever side the person arrives; `trial_link_bonus_days` is what
    # connecting the *second* identity is worth -- Telegram onto a website
    # account, or a confirmed address onto a Telegram one. Each is granted at
    # most once per account, so nobody can hold more than their sum.
    #
    # The bot used to carry its own hardcoded 30 in handlers/constants.py and
    # ignored this setting entirely, so the site and the bot were handing out
    # different trials from the same .env.
    trial_days: int = Field(7, validation_alias="TRIAL_DAYS")
    trial_link_bonus_days: int = Field(7, validation_alias="TRIAL_LINK_BONUS_DAYS")
    show_video_instructions: bool = Field(True, validation_alias="SHOW_VIDEO_INSTRUCTIONS")
    faq_url: str = Field("https://nitratex-company.gitbook.io/kairavpn/", validation_alias="FAQ_URL")
    status_channel_url: str = Field("https://t.me/nitratex1", validation_alias="STATUS_CHANNEL_URL")
    # Where "написать в поддержку" points, in the bot and on the website both.
    # It used to be a constant in user_bot/handlers/keyboards.py, which meant
    # the site had no way to learn it and the two could not help but drift.
    support_url: str = Field("https://t.me/nitratex1", validation_alias="SUPPORT_URL")

    # Public origin of the website. The bot needs it to build gift links --
    # the same value the Go service validates its own redirects against.
    web_base_url: str = Field("", validation_alias="WEB_BASE_URL")

    # -- Outgoing mail -----------------------------------------------------
    # The same SMTP account the website uses, read from the same keys, because
    # both now send to customers: the site sends sign-in links, the bot sends
    # the confirmation for attaching an address to a Telegram account.
    #
    # Every one of these is optional here. The website asserts them at start-up
    # and refuses to run without them; the bot degrades instead -- it stops
    # offering the email bonus rather than failing to start over a feature that
    # is not why anyone opened it.
    smtp_host: str = Field("", validation_alias="SMTP_HOST")
    smtp_port: int = Field(587, validation_alias="SMTP_PORT")
    smtp_username: str = Field("", validation_alias="SMTP_USERNAME")
    smtp_password: str = Field("", validation_alias="SMTP_PASSWORD")
    smtp_from: str = Field("", validation_alias="SMTP_FROM")
    smtp_starttls: bool = Field(True, validation_alias="SMTP_STARTTLS")

    @property
    def mail_configured(self) -> bool:
        return bool(self.smtp_host.strip() and self.smtp_from.strip())

    # Legal documents, shown by /docs. Empty means the bot says the document
    # is not published yet rather than offering a dead link.
    offer_url: str = Field("", validation_alias="OFFER_URL")
    refund_policy_url: str = Field("", validation_alias="REFUND_POLICY_URL")
    terms_url: str = Field("", validation_alias="TERMS_URL")
    privacy_policy_url: str = Field("", validation_alias="PRIVACY_POLICY_URL")

    def gift_link(self, code: str) -> str:
        """
        Where to send someone to redeem a gift code on the website.

        Empty when no site is configured, and the caller then offers only the
        code itself -- the bot path has always worked and does not depend on
        the site existing.
        """
        base = self.web_base_url.strip().rstrip("/")
        return f"{base}/gift/{code}" if base else ""

    # -- Backups (admin_bot) ----------------------------------------------
    # BACKUP_DIR / BACKUP_RETENTION_DAYS / REMNAWAVE_BACKUP_ENABLED are gone:
    # they configured a panel-side backup job that called an endpoint
    # Remnawave does not have, so it never produced anything.
    subscription_db_backup_dir: str = Field(
        "./backups/subscription_db", validation_alias="SUBSCRIPTION_DB_BACKUP_DIR"
    )

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

    @property
    def lte_node_uuids(self) -> list[str]:
        """Explicit LTE node UUIDs, comma- or space-separated."""
        return [part for part in self.lte_node_uuids_raw.replace(",", " ").split() if part]

    @property
    def lte_node_name_keywords(self) -> list[str]:
        """Lowercased substrings matched against node names when no UUIDs are set."""
        raw = self.lte_node_name_keywords_raw.replace(",", " ").split()
        return [part.lower() for part in raw if part]

    @property
    def lte_free_bytes_per_cycle(self) -> int:
        return max(0, self.lte_free_gb_per_cycle) * 1024**3

    @property
    def lte_cycle_seconds(self) -> int:
        return max(1, self.lte_cycle_days) * 86400

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
