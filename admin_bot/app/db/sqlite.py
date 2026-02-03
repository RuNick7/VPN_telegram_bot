"""SQLite database connection and setup."""

import aiosqlite
from pathlib import Path
from typing import Optional
from app.config.settings import settings


class Database:
    """SQLite database manager."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.user_bot_db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Establish database connection."""
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self.init_schema()

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def execute(self, query: str, parameters: tuple = ()) -> aiosqlite.Cursor:
        """Execute a query."""
        if not self._connection:
            await self.connect()
        return await self._connection.execute(query, parameters)

    async def execute_many(self, query: str, parameters: list) -> aiosqlite.Cursor:
        """Execute a query multiple times."""
        if not self._connection:
            await self.connect()
        return await self._connection.executemany(query, parameters)

    async def fetch_one(self, query: str, parameters: tuple = ()) -> Optional[aiosqlite.Row]:
        """Fetch a single row."""
        cursor = await self.execute(query, parameters)
        return await cursor.fetchone()

    async def fetch_all(self, query: str, parameters: tuple = ()) -> list[aiosqlite.Row]:
        """Fetch all rows."""
        cursor = await self.execute(query, parameters)
        return await cursor.fetchall()

    async def commit(self) -> None:
        """Commit pending transactions."""
        if self._connection:
            await self._connection.commit()

    async def init_schema(self) -> None:
        """Initialize database schema."""
        # Create users table if not exists
        await self.execute("""
            CREATE TABLE IF NOT EXISTS users (
                tg_id INTEGER PRIMARY KEY,
                role TEXT DEFAULT 'user',
                selected_server TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self.commit()


# Global database instance
db = Database()
