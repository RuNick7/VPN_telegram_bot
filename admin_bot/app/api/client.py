"""
admin_bot's Remnawave client -- now the shared one, configured from settings.

The hand-rolled httpx client that used to live here was merged into
`tgvpn_shared.remnawave` in Phase 2 together with user_bot's separate (sync)
client. This module just builds it from admin_bot's configuration; everything
else in admin_bot keeps importing `RemnawaveClient` from here.
"""

from tgvpn_shared.remnawave import RemnawaveClient as _SharedClient

from app.config.settings import settings


def RemnawaveClient() -> _SharedClient:  # noqa: N802 -- kept callable-as-class for existing call sites
    """Build a shared Remnawave client from admin_bot's configuration."""
    return _SharedClient(
        base_url=settings.remnawave_base_url,
        token=settings.remnawave_api_token,
        username=settings.remnawave_username or None,
        password=settings.remnawave_password or None,
        timeout_seconds=settings.remnawave_timeout_seconds,
    )


__all__ = ["RemnawaveClient"]
