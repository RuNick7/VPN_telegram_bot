"""Repository for `admin_operators` — replaces admin_bot/app/db/sqlite.py's
`Database`/`users` table and admin_bot/app/db/repo/users.py's UserRepository
(renamed here to avoid colliding with the new customer-identity `users` table)."""

from __future__ import annotations

from typing import Optional

from .pool import get_pool


class AdminOperatorRepository:
    async def get_by_tg_id(self, tg_id: int) -> Optional[dict]:
        pool = await get_pool()
        row = await pool.fetchrow("SELECT * FROM admin_operators WHERE tg_id = $1", tg_id)
        return dict(row) if row else None

    async def create(self, tg_id: int, role: str = "user", selected_server: Optional[str] = None) -> dict:
        pool = await get_pool()
        await pool.execute(
            "INSERT INTO admin_operators (tg_id, role, selected_server) VALUES ($1, $2, $3)",
            tg_id, role, selected_server,
        )
        return await self.get_by_tg_id(tg_id)

    async def update_role(self, tg_id: int, role: str) -> None:
        pool = await get_pool()
        await pool.execute(
            "UPDATE admin_operators SET role = $1, updated_at = now() WHERE tg_id = $2",
            role, tg_id,
        )

    async def update_selected_server(self, tg_id: int, server: str) -> None:
        pool = await get_pool()
        await pool.execute(
            "UPDATE admin_operators SET selected_server = $1, updated_at = now() WHERE tg_id = $2",
            server, tg_id,
        )

    async def get_all_admins(self) -> list[dict]:
        pool = await get_pool()
        rows = await pool.fetch("SELECT * FROM admin_operators WHERE role = 'admin'")
        return [dict(row) for row in rows]

    async def exists(self, tg_id: int) -> bool:
        pool = await get_pool()
        row = await pool.fetchrow("SELECT 1 FROM admin_operators WHERE tg_id = $1", tg_id)
        return row is not None
