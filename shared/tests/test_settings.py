"""Settings parsing, including the crash this model was built to prevent."""

import pytest

from tgvpn_shared.settings import Settings


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch):
    """
    Hide the ambient environment from these tests.

    `_env_file=None` stops pydantic-settings reading the repo's .env, but it
    still reads os.environ -- and other conftests in the same pytest run set
    DATABASE_URL and friends there.
    """
    for name in (
        "ADMIN_BOT_TOKEN",
        "Admin_bot_token",
        "USER_BOT_TOKEN",
        "ADMIN_IDS",
        "DATABASE_URL",
        "REMNAWAVE_BASE_URL",
        "REMNAWAVE_TOKEN",
        "REMNAWAVE_API_KEY",
        "YOOKASSA_SHOP_ID",
        "YOOKASSA_SECRET_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def make(**env) -> Settings:
    """Build Settings from an explicit dict, ignoring the repo's real .env."""
    return Settings(_env_file=None, **env)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("", []),
        ("111111111", [111111111]),
        ("111,222,333", [111, 222, 333]),
        ("111, 222 , 333", [111, 222, 333]),
        ("111 222", [111, 222]),
        ("111,,222,", [111, 222]),
        ("not-a-number", []),
    ],
)
def test_admin_ids_parsing(raw, expected):
    assert make(admin_ids_raw=raw).admin_ids == expected


def test_empty_admin_ids_does_not_raise():
    """
    Regression: `ADMIN_IDS=` used to crash admin_bot at import.

    Typing the field as `list[int]` made pydantic-settings JSON-decode the env
    value before any validator could normalize it, so an empty (or plain
    comma-separated) value raised SettingsError.
    """
    assert make(admin_ids_raw="").admin_ids == []


def test_primary_admin_id_defaults_to_zero():
    assert make(admin_ids_raw="").primary_admin_id == 0
    assert make(admin_ids_raw="42,43").primary_admin_id == 42


def test_remnawave_token_and_api_key_are_aliases():
    assert make(remnawave_token="  tok  ").remnawave_api_token == "tok"
    assert make(remnawave_api_key="key").remnawave_api_token == "key"
    # REMNAWAVE_TOKEN wins when both are set.
    assert make(remnawave_token="tok", remnawave_api_key="key").remnawave_api_token == "tok"


def test_require_lists_every_missing_field():
    settings = make(user_bot_token="set")
    with pytest.raises(RuntimeError) as excinfo:
        settings.require("user_bot_token", "database_url", "remnawave_base_url")
    message = str(excinfo.value)
    assert "database_url" in message
    assert "remnawave_base_url" in message
    assert "user_bot_token" not in message


def test_require_passes_when_all_present():
    make(user_bot_token="a", database_url="b").require("user_bot_token", "database_url")
