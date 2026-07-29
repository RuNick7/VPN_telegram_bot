"""
Remnawave operations for user_bot -- async end to end since Phase 2.

Until Phase 2 every function here was synchronous (it drove a `requests`-based
client), so callers wrapped each one in `asyncio.to_thread` and the module's
own DB access had to be bridged back through `tgvpn_shared.sync_bridge`. Now
that the shared Remnawave client is natively async, both detours are gone: the
repository layer is awaited directly and callers just `await`.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone

from remnawave_api.models.users import CreateUserRequestDto
from tgvpn_shared.db import UserRepository
from tgvpn_shared.remnawave import RemnawaveClient, UserNotFoundError
from tgvpn_shared.settings import get_settings
from tgvpn_shared.squads import get_or_create_internal_squad, normalize_new_squad_members

logger = logging.getLogger(__name__)

_users = UserRepository()
_client: RemnawaveClient | None = None

SECONDS_IN_DAY = 86400


def get_client() -> RemnawaveClient:
    """
    Process-wide Remnawave client.

    One instance, so its token cache is actually shared -- the old code built a
    fresh client per call, which meant a single subscription extension cost
    three separate logins.
    """
    global _client
    if _client is None:
        settings = get_settings()
        _client = RemnawaveClient(
            base_url=settings.remnawave_base_url,
            token=settings.remnawave_api_token,
            username=settings.remnawave_username or None,
            password=settings.remnawave_password or None,
            timeout_seconds=settings.remnawave_timeout_seconds,
        )
    return _client


async def close_client() -> None:
    """Release the shared client's connections (called on shutdown)."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None


def _utc_iso(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _epoch(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def _panel_username(telegram_id: int) -> str:
    """
    The panel username for a Telegram user.

    Still `str(telegram_id)` -- decoupling the panel handle from the Telegram
    ID is Phase 4's identity rework, and existing accounts are not renamed.
    """
    return str(telegram_id)


# -- reads -----------------------------------------------------------------


async def get_user_expire(telegram_id: int) -> int:
    """Subscription expiry from the panel, as a Unix timestamp."""
    user = await get_client().get_user_by_username(_panel_username(telegram_id))
    return _epoch(user["expireAt"])


async def get_subscription_url(telegram_id: int) -> str:
    """The user's connection URL, or an empty string if the panel omits it."""
    user = await get_client().get_user_by_username(_panel_username(telegram_id))
    return user.get("subscriptionUrl", "")


# -- writes ----------------------------------------------------------------


async def _assign_internal_squad(user_uuid: str) -> None:
    """Place a new user into a squad with room; never fatal to creation."""
    settings = get_settings()
    client = get_client()
    try:
        squad, created = await get_or_create_internal_squad(
            client,
            max_users=settings.internal_squad_max_users,
            prefix=settings.internal_squad_prefix,
        )
        squad_uuid = (squad or {}).get("uuid")
        if not squad_uuid:
            logger.warning("[Remnawave] Internal squad not found/created for user %s", user_uuid)
            return

        logger.info("[Remnawave] Selected squad %s created=%s", squad_uuid, created)
        await client.set_user_squads([str(user_uuid)], [str(squad_uuid)])
        if created:
            asyncio.create_task(normalize_new_squad_members(client, str(squad_uuid), str(user_uuid)))
    except Exception as exc:
        logger.error("[Remnawave] Failed to assign internal squad: %s", exc)


async def create_vpn_user(telegram_id: int, days_to_add: int) -> bool:
    """Create the panel user for a Telegram account. Returns success."""
    username = _panel_username(telegram_id)
    expire_at = datetime.fromtimestamp(
        int(time.time()) + int(days_to_add) * SECONDS_IN_DAY, tz=timezone.utc
    )
    body = CreateUserRequestDto(
        username=username,
        telegram_id=telegram_id,
        expire_at=expire_at,
        activate_all_inbounds=True,
    )
    payload = body.model_dump(mode="json", by_alias=True, exclude_none=True)
    # Some panel versions validate telegramId strictly as a number.
    payload["telegramId"] = int(telegram_id)

    try:
        user = await get_client().create_user(payload)
    except Exception as exc:
        logger.error("[Remnawave] Failed to create user %s: %s", username, exc)
        return False

    user_uuid = user.get("uuid")
    if user_uuid:
        await _assign_internal_squad(str(user_uuid))
    else:
        logger.warning("[Remnawave] Cannot assign internal squad: missing user uuid")
    logger.info("[Remnawave] User %s created.", username)
    return True


async def _current_expire_for_extend(telegram_id: int, days_to_add: int) -> tuple[int | None, str | None]:
    """
    Current expiry for a user, creating the panel profile if it's missing.

    Returns `(expire_ts, error_message)` -- exactly one is non-None.
    """
    username = _panel_username(telegram_id)
    try:
        return await get_user_expire(telegram_id), None
    except UserNotFoundError:
        logger.info("[Remnawave] Пользователь @%s не найден, создаём профиль.", username)
        if not await create_vpn_user(telegram_id, days_to_add):
            return None, f"❌ Не удалось создать пользователя @{username}."
        try:
            return await get_user_expire(telegram_id), None
        except Exception as exc:
            logger.warning(
                "[Remnawave] Пользователь @%s создан, но срок не удалось прочитать: %s", username, exc
            )
            return int(time.time()), None
    except Exception as exc:
        logger.error("[Remnawave] Ошибка при проверке пользователя @%s: %s", username, exc)
        return None, f"❌ Ошибка проверки пользователя @{username}."


async def extend_subscription(telegram_id: int, days_to_add: int) -> str:
    """
    Add days to a subscription, in the panel and in our database.

    Extends from whichever is later -- the current expiry or now -- so
    extending an already-lapsed subscription doesn't back-date it. Returns a
    user-facing status line.
    """
    username = _panel_username(telegram_id)
    try:
        logger.info("[Remnawave] Extend subscription for @%s", username)
        current_expire, error = await _current_expire_for_extend(telegram_id, days_to_add)
        if error:
            return error
        if current_expire is None:
            return f"❌ Ошибка проверки пользователя @{username}."

        days_to_add = int(days_to_add)
        new_expire = max(current_expire, int(time.time())) + days_to_add * SECONDS_IN_DAY

        await get_client().update_user({"username": username, "expireAt": _utc_iso(new_expire)})
        # Creates the row if the user somehow has none, and clears `reminded`
        # so the expiry reminder can fire again for the new period.
        await _users.upsert_subscription_expire(
            telegram_id=telegram_id,
            subscription_ends=new_expire,
        )
        return (
            f"✅ Подписка @{username} продлена на {days_to_add} дней.\n"
            f"📆 Новая дата окончания: "
            f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(new_expire))}"
        )
    except Exception as exc:
        logger.error("[Remnawave] Ошибка продления подписки: %s", exc)
        get_client().invalidate_token()
        return f"❌ Ошибка: {str(exc)}"


async def ensure_vpn_profile_exists(telegram_id: int) -> None:
    """
    Recreate a panel profile that went missing, preserving the DB's remaining days.

    Covers users whose panel account was deleted (e.g. by the inactive-user
    cleanup job) while their subscription row survived.
    """
    try:
        await get_user_expire(telegram_id)
        logger.info("[Remnawave] Профиль %s уже существует — не создаём повторно.", telegram_id)
        return
    except UserNotFoundError:
        pass
    except Exception as exc:
        logger.error("[Remnawave] Ошибка при проверке профиля: %s", exc)
        return

    info = await _users.get_subscription_info(telegram_id)
    if info is None:
        logger.warning("[Remnawave] Пользователь %s не найден в БД.", telegram_id)
        return
    days_left = max((int(info["subscription_ends"] or 0) - int(time.time())) // SECONDS_IN_DAY, 1)
    logger.info("[Remnawave] Профиль создан: %s", await extend_subscription(telegram_id, days_left))
