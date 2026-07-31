"""User management service (admin side)."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from remnawave_api.models.users import CreateUserRequestDto
from tgvpn_shared.db import UserRepository
from tgvpn_shared.remnawave import UserNotFoundError
from tgvpn_shared.squads import resolve_paid_squad_uuid

from app.api.client import RemnawaveClient
from app.config.settings import settings

_users_repo = UserRepository()


class UserService:
    """Service for user operations."""

    def __init__(self):
        self.client = RemnawaveClient()
        self.log = logging.getLogger(__name__)

    async def _assign_internal_squad(self, user_uuid: str, username: str) -> None:
        """
        Put a freshly created user into the paid squad; never fatal to creation.

        One squad, nothing created here -- see `resolve_paid_squad_uuid`.
        """
        try:
            squad_uuid = await resolve_paid_squad_uuid(self.client, settings.paid_squad_name)
            if not squad_uuid:
                return
            await self.client.set_user_squads([str(user_uuid)], [str(squad_uuid)])
            self.log.info("User %s placed in paid squad %s", username, squad_uuid)
        except Exception as exc:
            self.log.error("Failed to assign paid squad for %s: %s", username, exc)

    async def create_user(
        self,
        username: str,
        telegram_id: Optional[int] = None,
        days_valid: int = 30,
        expire_at: Optional[datetime] = None,
        traffic_limit_bytes: Optional[int] = None,
        tag: Optional[str] = None,
        hwid_device_limit: Optional[int] = None,
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
            activate_all_inbounds=True,
        )
        payload = body.model_dump(mode="json", by_alias=True, exclude_none=True)
        user = await self.client.create_user(payload)

        user_uuid = user.get("uuid")
        if user_uuid:
            await self._assign_internal_squad(str(user_uuid), username)

        if telegram_id is not None:
            await _users_repo.insert_subscription_user(
                telegram_id=telegram_id,
                subscription_ends=int(expire_at.timestamp()),
                telegram_tag=username,
            )
        return user

    async def list_users(self, page: int = 1, size: int = 10) -> Dict[str, Any]:
        """List users with pagination -- `{"users": [...], "total": N}`."""
        return await self.client.list_users(page=page, size=size)

    async def get_user_by_username(self, username: str) -> Dict[str, Any]:
        """
        Find a user by username, falling back to a full scan.

        The direct endpoint matches on username only; the scan additionally
        matches on telegramId, which is how an admin can find a user whose
        panel username was changed away from their Telegram ID.
        """
        needle = str(username).strip()
        if not needle:
            return {}

        try:
            return await self.client.get_user_by_username(needle)
        except UserNotFoundError:
            pass
        except Exception as exc:
            self.log.warning("Direct username lookup failed for %s: %s", needle, exc)

        async for user in self.client.iter_all_users():
            user_username = str(user.get("username") or "").strip()
            user_tg = str(user.get("telegramId") or user.get("telegram_id") or "").strip()
            if user_username == needle or user_tg == needle:
                return user
        return {}

    async def get_user_by_uuid(self, user_uuid: str) -> Dict[str, Any]:
        """Get user by uuid."""
        return await self.client.get_user_by_uuid(user_uuid)

    async def update_user(self, user_uuid: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update user by uuid, translating snake_case field names to the API's."""
        field_aliases = {
            "expire_at": "expireAt",
            "traffic_limit_bytes": "trafficLimitBytes",
            "telegram_id": "telegramId",
            "hwid_device_limit": "hwidDeviceLimit",
        }
        payload: Dict[str, Any] = {"uuid": user_uuid}
        for key, value in data.items():
            api_key = field_aliases.get(key, key)
            payload[api_key] = value.isoformat() if isinstance(value, datetime) else value
        return await self.client.update_user(payload)

    async def delete_user(self, user_uuid: str) -> Dict[str, Any]:
        """Delete user by uuid."""
        return await self.client.delete_user(user_uuid)

    async def close(self):
        """Close client connection."""
        await self.client.close()


user_service = UserService()
