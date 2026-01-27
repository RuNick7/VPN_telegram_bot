"""User management service."""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from remnawave_api.models.users import CreateUserRequestDto

from app.api.client import RemnawaveClient
from app.services.subscription_db import insert_subscription_user


class UserService:
    """Service for user operations."""

    def __init__(self):
        self.client = RemnawaveClient()

    async def create_user(
        self,
        username: str,
        telegram_id: Optional[int] = None,
        days_valid: int = 30,
        expire_at: Optional[datetime] = None,
        traffic_limit_bytes: Optional[int] = None,
        tag: Optional[str] = None,
        hwid_device_limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create a new user with a default expiration."""
        if expire_at is None:
            expire_at = datetime.now(timezone.utc) + timedelta(days=days_valid)
        body = CreateUserRequestDto(
            username=username,
            expire_at=expire_at,
            telegram_id=telegram_id,
            traffic_limit_bytes=traffic_limit_bytes,
            tag=tag,
            hwidDeviceLimit=hwid_device_limit,
            activate_all_inbounds=True
        )
        payload = body.model_dump(mode="json", by_alias=True, exclude_none=True)
        user = await self.client.request("POST", "/users", json=payload)

        if telegram_id is not None:
            await insert_subscription_user(
                telegram_id=telegram_id,
                subscription_ends=expire_at,
                telegram_tag=username,
            )
        return user

    async def list_users(self, page: int = 1, size: int = 10) -> Dict[str, Any]:
        """List users with pagination."""
        params = {"page": page, "size": size, "limit": size}
        return await self.client.request("GET", "/users", params=params)

    async def get_user_by_username(self, username: str) -> Dict[str, Any]:
        """Find user by username using list endpoint."""
        page = 1
        size = 100
        while True:
            response = await self.list_users(page=page, size=size)
            data = response.get("response", {})
            users = data.get("users", [])
            for user in users:
                if user.get("username") == username:
                    return user
            total = data.get("total")
            if not total:
                break
            max_page = max(1, (total + size - 1) // size)
            if page >= max_page:
                break
            page += 1
        return {}

    async def get_user_by_uuid(self, user_uuid: str) -> Dict[str, Any]:
        """Get user by uuid."""
        return await self.client.request("GET", f"/users/{user_uuid}")

    async def update_user(self, user_uuid: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user by uuid."""
        payload: Dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, datetime):
                payload[key] = value.isoformat()
            else:
                payload[key] = value
        payload["uuid"] = user_uuid
        return await self.client.request("PATCH", "/users", json=payload)

    async def delete_user(self, user_uuid: str) -> Dict[str, Any]:
        """Delete user by uuid."""
        return await self.client.request("DELETE", f"/users/{user_uuid}")

    async def close(self):
        """Close client connection."""
        await self.client.close()


user_service = UserService()
