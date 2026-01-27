"""Access control service."""

from app.config.settings import settings
from app.db.repo.users import user_repo


async def check_admin_access(tg_id: int) -> bool:
    """Check if user has admin access."""
    # Check if user is in settings admin_ids
    if tg_id in settings.admin_ids:
        return True

    # Check if user has admin role in database
    user = await user_repo.get_by_tg_id(tg_id)
    if user and user.get("role") == "admin":
        return True

    return False
