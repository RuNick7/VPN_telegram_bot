"""Router aggregation for all bot handlers."""

from aiogram import Router

from app.handlers import common, admin


def get_all_routers() -> list[Router]:
    """Collect and return all application routers."""
    routers = [
        common.router,
        admin.router,
    ]
    return routers
