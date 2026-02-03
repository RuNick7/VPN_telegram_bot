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

    return RemnawaveSettings(
        base_url=base_url,
        username=os.getenv("REMNAWAVE_USERNAME"),
        password=os.getenv("REMNAWAVE_PASSWORD"),
        token=os.getenv("REMNAWAVE_TOKEN"),
        timeout_seconds=timeout_seconds,
        internal_squad_max_users=internal_squad_max_users,
        internal_squad_prefix=internal_squad_prefix,
    )
