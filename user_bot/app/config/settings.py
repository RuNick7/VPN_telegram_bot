import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[3]
load_dotenv(dotenv_path=ROOT_DIR / ".env")


@dataclass(frozen=True)
class RemnawaveSettings:
    base_url: str
    username: str | None
    password: str | None
    token: str | None
    timeout_seconds: int
    internal_squad_max_users: int
    internal_squad_prefix: str
    lte_squad_name: str
    lte_free_gb_per_30d: int
    free_squad_name: str
    infinite_expire_date: str


def get_remnawave_settings() -> RemnawaveSettings:
    base_url = (os.getenv("REMNAWAVE_BASE_URL") or "").rstrip("/")
    if not base_url:
        raise ValueError("REMNAWAVE_BASE_URL is not set")

    timeout_raw = os.getenv("REMNAWAVE_TIMEOUT_SECONDS", "5")
    try:
        timeout_seconds = int(timeout_raw)
    except ValueError as exc:
        raise ValueError("REMNAWAVE_TIMEOUT_SECONDS must be an integer") from exc

    internal_max_raw = os.getenv("INTERNAL_SQUAD_MAX_USERS", "30")
    try:
        internal_squad_max_users = int(internal_max_raw)
    except ValueError as exc:
        raise ValueError("INTERNAL_SQUAD_MAX_USERS must be an integer") from exc

    internal_squad_prefix = os.getenv("INTERNAL_SQUAD_PREFIX", "internal").strip() or "internal"
    lte_squad_name = os.getenv("LTE_SQUAD_NAME", "LTE").strip() or "LTE"
    lte_free_raw = os.getenv("LTE_FREE_GB_PER_30D", "1")
    try:
        lte_free_gb_per_30d = int(lte_free_raw)
    except ValueError as exc:
        raise ValueError("LTE_FREE_GB_PER_30D must be an integer") from exc

    free_squad_name = os.getenv("FREE_SQUAD_NAME", "FREE").strip() or "FREE"
    infinite_expire_date = (
        os.getenv("INFINITE_EXPIRE_DATE", "2099-12-31T23:59:59.000Z").strip()
        or "2099-12-31T23:59:59.000Z"
    )

    return RemnawaveSettings(
        base_url=base_url,
        username=os.getenv("REMNAWAVE_USERNAME"),
        password=os.getenv("REMNAWAVE_PASSWORD"),
        token=(os.getenv("REMNAWAVE_TOKEN") or os.getenv("REMNAWAVE_API_KEY")),
        timeout_seconds=timeout_seconds,
        internal_squad_max_users=internal_squad_max_users,
        internal_squad_prefix=internal_squad_prefix,
        lte_squad_name=lte_squad_name,
        lte_free_gb_per_30d=lte_free_gb_per_30d,
        free_squad_name=free_squad_name,
        infinite_expire_date=infinite_expire_date,
    )
