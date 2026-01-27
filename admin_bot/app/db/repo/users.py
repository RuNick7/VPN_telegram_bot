"""User repository for database operations."""

from typing import Optional, List
from app.db.sqlite import db


class UserRepository:
    """Repository for user data operations."""

    async def get_by_tg_id(self, tg_id: int) -> Optional[dict]:
        """Get user by Telegram ID."""
        row = await db.fetch_one(
            "SELECT * FROM users WHERE tg_id = ?",
            (tg_id,)
        )
        return dict(row) if row else None

    async def create(self, tg_id: int, role: str = "user", selected_server: Optional[str] = None) -> dict:
        """Create a new user."""
        await db.execute(
            "INSERT INTO users (tg_id, role, selected_server) VALUES (?, ?, ?)",
            (tg_id, role, selected_server)
        )
        await db.commit()
        return await self.get_by_tg_id(tg_id)

    async def update_role(self, tg_id: int, role: str) -> None:
        """Update user role."""
        await db.execute(
            "UPDATE users SET role = ?, updated_at = CURRENT_TIMESTAMP WHERE tg_id = ?",
            (role, tg_id)
        )
        await db.commit()

    async def update_selected_server(self, tg_id: int, server: str) -> None:
        """Update user's selected server."""
        await db.execute(
            "UPDATE users SET selected_server = ?, updated_at = CURRENT_TIMESTAMP WHERE tg_id = ?",
            (server, tg_id)
        )
        await db.commit()

    async def get_all_admins(self) -> List[dict]:
        """Get all admin users."""
        rows = await db.fetch_all("SELECT * FROM users WHERE role = 'admin'")
        return [dict(row) for row in rows]

    async def exists(self, tg_id: int) -> bool:
        """Check if user exists."""
        row = await db.fetch_one("SELECT 1 FROM users WHERE tg_id = ?", (tg_id,))
        return row is not None


user_repo = UserRepository()
