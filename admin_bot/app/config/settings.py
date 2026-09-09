"""
admin_bot's import point for the shared settings model.

The standalone pydantic model that used to live here was merged into
`tgvpn_shared.settings` in Phase 2, so both bots parse configuration once and
the same way. This module stays because every admin_bot module already imports
`from app.config.settings import settings`.

Unlike the old model, importing this no longer raises when a token is unset --
`main.py` asserts what admin_bot actually needs via `settings.require(...)`
and reports it readably instead of surfacing a pydantic traceback.
"""

from tgvpn_shared.settings import Settings, get_settings

settings: Settings = get_settings()

__all__ = ["Settings", "settings"]
