"""User management service."""

import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from remnawave_api.models.users import CreateUserRequestDto

from app.api.client import RemnawaveClient
from app.config.settings import settings
from app.services.subscription_db import insert_subscription_user


class UserService:
    """Service for user operations."""

    def __init__(self):
        self.client = RemnawaveClient()
        self.log = logging.getLogger(__name__)

    async def _list_internal_squads(self) -> list[dict]:
        response = await self.client.request("GET", "/internal-squads")
        if "response" in response:
            return response.get("response", {}).get("internalSquads", []) or []
        return response.get("internalSquads", []) or []

    async def _list_all_user_uuids(self) -> list[str]:
        page = 1
        size = 100
        uuids: list[str] = []
        while True:
            response = await self.list_users(page=page, size=size)
            data = response.get("response", {})
            users = data.get("users", [])
            for user in users:
                uuid = user.get("uuid")
                if uuid:
                    uuids.append(str(uuid))
            total = data.get("total")
            if not total:
                break
            max_page = max(1, (total + size - 1) // size)
            if page >= max_page:
                break
            page += 1
        return uuids

    @staticmethod
    def _members_count(squad: dict) -> int:
        info = squad.get("info") or {}
        count = info.get("membersCount")
        return int(count) if isinstance(count, int) else 0

    def _next_internal_squad_name(self, squads: list[dict]) -> str:
        prefix = settings.internal_squad_prefix
        max_index = 0
        for squad in squads:
            name = squad.get("name") or ""
            if not name.startswith(f"{prefix}-"):
                continue
            suffix = name[len(prefix) + 1:]
            if suffix.isdigit():
                max_index = max(max_index, int(suffix))
        return f"{prefix}-{max_index + 1}"

    @staticmethod
    def _extract_inbound_ids(squad: dict) -> list[str]:
        inbounds = squad.get("inbounds") or []
        inbound_ids = []
        for inbound in inbounds:
            uuid = inbound.get("uuid")
            if uuid:
                inbound_ids.append(str(uuid))
        return inbound_ids

    async def _create_internal_squad(self, name: str, inbound_ids: list[str]) -> dict:
        payload = {"name": name, "inbounds": inbound_ids}
        response = await self.client.request("POST", "/internal-squads", json=payload)
        if "response" in response:
            return response.get("response", {}) or {}
        return response

    async def _assign_user_to_internal_squad(self, squad_uuid: str, user_uuid: str) -> None:
        payload = {"userUuids": [user_uuid]}
        await self.client.request(
            "POST",
            f"/internal-squads/{squad_uuid}/bulk-actions/add-users",
            json=payload,
        )

    async def _update_user_internal_squads(self, user_uuid: str, squad_uuids: list[str]) -> None:
        payload = {"uuids": [user_uuid], "activeInternalSquads": squad_uuids}
        await self.client.request("POST", "/users/bulk/update-squads", json=payload)

    async def _remove_users_from_internal_squad(self, squad_uuid: str, user_uuids: list[str]) -> dict | None:
        if not user_uuids:
            return None
        payload = {"userUuids": user_uuids}
        try:
            return await self.client.request(
                "DELETE",
                f"/internal-squads/{squad_uuid}/bulk-actions/remove-users",
                json=payload,
            )
        except Exception as exc:
            self.log.warning("DELETE remove-users failed: %s", exc)
            return None

    async def _normalize_new_squad_members(self, squad_uuid: str, user_uuid: str, delay_seconds: float = 5.0) -> None:
        await asyncio.sleep(delay_seconds)
        response = await self.list_users(page=1, size=200)
        users = response.get("response", {}).get("users", [])
        for user in users:
            uuid = user.get("uuid")
            if not uuid:
                continue
            squads = user.get("activeInternalSquads") or []
            squad_ids = [str(s.get("uuid")) for s in squads if s.get("uuid")]
            if str(uuid) == str(user_uuid):
                desired = [str(squad_uuid)]
            else:
                desired = [s for s in squad_ids if s != str(squad_uuid)]
            if desired == squad_ids:
                continue
            try:
                await self._update_user_internal_squads(str(uuid), desired)
                self.log.info("Updated user %s squads -> %s", uuid, desired)
            except Exception as exc:
                self.log.warning("Failed to update user %s squads: %s", uuid, exc)

    async def _get_or_create_internal_squad(self) -> tuple[Optional[dict], bool]:
        squads = await self._list_internal_squads()
        limit = settings.internal_squad_max_users
        for squad in squads:
            if self._members_count(squad) < limit:
                return squad, False

        name = self._next_internal_squad_name(squads)
        template = next((s for s in squads if (s.get("inbounds") or [])), None)
        inbound_ids = self._extract_inbound_ids(template) if template else []
        self.log.info("Creating internal squad %s with %s inbounds", name, len(inbound_ids))
        return await self._create_internal_squad(name, inbound_ids), True

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

        user_uuid = user.get("uuid") or (user.get("response", {}) or {}).get("uuid")
        if user_uuid:
            try:
                self.log.info("Assigning internal squad for user %s (uuid=%s)", username, user_uuid)
                squad, created = await self._get_or_create_internal_squad()
                squad_uuid = (squad or {}).get("uuid")
                if squad_uuid:
                    self.log.info(
                        "Selected squad %s created=%s for user %s",
                        squad_uuid,
                        created,
                        username,
                    )
                    await self._update_user_internal_squads(str(user_uuid), [str(squad_uuid)])
                    if created:
                        try:
                            asyncio.create_task(
                                self._normalize_new_squad_members(str(squad_uuid), str(user_uuid))
                            )
                        except Exception as exc:
                            self.log.warning("Failed to schedule squad normalization: %s", exc)
                else:
                    self.log.warning("Internal squad not found/created for user %s", username)
            except Exception as e:
                self.log.error("Failed to assign internal squad for %s: %s", username, e)

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
