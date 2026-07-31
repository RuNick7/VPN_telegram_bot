"""
Remnawave operations for user_bot -- async end to end since Phase 2.

Until Phase 2 every function here was synchronous (it drove a `requests`-based
client), so callers wrapped each one in `asyncio.to_thread` and the module's
own DB access had to be bridged back through `tgvpn_shared.sync_bridge`. Now
that the shared Remnawave client is natively async, both detours are gone: the
repository layer is awaited directly and callers just `await`.
"""

import logging
import time
from datetime import datetime, timezone

from remnawave_api.models.users import CreateUserRequestDto
from tgvpn_shared.db import UserRepository
from tgvpn_shared.free_tier import panel_expire_timestamp
from tgvpn_shared.identity import panel_username_for, resolve_panel_identity
from tgvpn_shared.remnawave import APINotFoundError, RemnawaveClient, UserNotFoundError
from tgvpn_shared.settings import get_settings
from tgvpn_shared.squads import resolve_paid_squad_uuid

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
    The legacy panel username: `str(telegram_id)`.

    Kept because accounts created before the identity rework are named this in
    the panel and are deliberately **not renamed** -- a bulk rename against a
    live panel is not worth the risk. `resolve_panel_user` below tries the
    stored UUID first and only falls back here, backfilling as it goes, so
    this path retires one user at a time.
    """
    return str(telegram_id)


async def resolve_panel_user(user_row: dict) -> dict | None:
    """
    Find this user's panel account by whichever handle we trust most.

    The stored UUID is authoritative and survives an operator renaming the
    account by hand; the stored username is next; `str(telegram_id)` is the
    legacy fallback. A hit on either fallback writes the UUID back, so the
    expensive path is taken at most once per user.

    Returns None when the account genuinely does not exist yet.
    """
    lookup = resolve_panel_identity(dict(user_row))
    client = get_client()

    if lookup.uuid:
        try:
            found = await client.get_user_by_uuid(lookup.uuid)
            if found and found.get("uuid"):
                return found
        except (UserNotFoundError, APINotFoundError):
            # Deleted in the panel, or the UUID is stale. Fall through to the
            # name-based lookups rather than reporting the user as missing.
            logger.info("[Remnawave] Stored UUID %s no longer resolves", lookup.uuid)

    for username in (lookup.username, lookup.legacy_username):
        if not username:
            continue
        found = await client.find_user_by_username(username)
        if found:
            await _remember_panel_identity(user_row, found)
            return found
    return None


async def _remember_panel_identity(user_row: dict, panel_user: dict) -> None:
    """Backfill the panel handle we just resolved the slow way."""
    user_id = user_row.get("id")
    if not user_id or not panel_user.get("uuid"):
        return
    if str(user_row.get("remnawave_uuid") or "") == str(panel_user["uuid"]):
        return
    try:
        await _users.set_panel_identity(
            str(user_id),
            remnawave_uuid=str(panel_user["uuid"]),
            remnawave_username=panel_user.get("username"),
        )
    except Exception as exc:
        # Losing the backfill costs one extra lookup next time, nothing more.
        logger.warning("[Remnawave] Could not store panel identity: %s", exc)




# -- reads -----------------------------------------------------------------


async def _panel_user_for(telegram_id: int) -> dict:
    """
    This Telegram user's panel account, or UserNotFoundError.

    Goes through the database row so the lookup can use our stored UUID.
    Falling straight back to `str(telegram_id)` when there is no row at all
    keeps the pre-rework behaviour for a user the database has somehow lost.
    """
    row = await _users.get_user_by_id(telegram_id)
    if row is None:
        user = await get_client().find_user_by_username(_panel_username(telegram_id))
        if user is None:
            raise UserNotFoundError(f"User not found: {telegram_id}")
        return user

    user = await resolve_panel_user(dict(row))
    if user is None:
        raise UserNotFoundError(f"User not found: {telegram_id}")
    return user


async def get_user_expire(telegram_id: int) -> int:
    """Subscription expiry from the panel, as a Unix timestamp."""
    return _epoch((await _panel_user_for(telegram_id))["expireAt"])


async def get_subscription_url(telegram_id: int) -> str:
    """The user's connection URL, or an empty string if the panel omits it."""
    return (await _panel_user_for(telegram_id)).get("subscriptionUrl", "")


async def get_devices(telegram_id: int) -> tuple[list[dict], int | None]:
    """
    Registered devices and the account's device limit.

    Returns them together because both come out of the same lookup, and a
    count means little to a user without the cap it is measured against. The
    limit is None when the panel doesn't set one.
    """
    user = await _panel_user_for(telegram_id)
    devices = await get_client().list_hwid_devices(str(user["uuid"]))
    limit = user.get("hwidDeviceLimit")
    return devices, int(limit) if isinstance(limit, int) and limit > 0 else None


# -- writes ----------------------------------------------------------------


async def reset_subscription_url(telegram_id: int) -> str:
    """
    Issue a fresh connection link, invalidating the old one. Returns the new URL.

    Every device keeps working off the old link until it next refreshes, at
    which point it stops -- so this is only worth offering to someone who
    intends to re-import everywhere, and the caller confirms first.

    Registered devices are not cleared: rotating the link and freeing a device
    slot are separate problems, and doing both here would surprise a user who
    only wanted a new link.
    """
    user = await _panel_user_for(telegram_id)
    revoked = await get_client().revoke_subscription(str(user["uuid"]))
    url = revoked.get("subscriptionUrl", "")
    if not url:
        # Older panels answer the revoke with a thinner body; the link is
        # already rotated at this point, so re-read rather than report failure.
        url = await get_subscription_url(telegram_id)
    logger.info("[Remnawave] Subscription link rotated for %s", telegram_id)
    return url


async def delete_device(telegram_id: int, hwid: str) -> None:
    """Unregister one device, freeing its slot against the device limit."""
    user = await _panel_user_for(telegram_id)
    await get_client().delete_hwid_device(str(user["uuid"]), hwid)
    logger.info("[Remnawave] Device removed for %s", telegram_id)


async def _assign_internal_squad(user_uuid: str) -> None:
    """
    Put a new user into the paid squad; never fatal to creation.

    There is one squad now and nothing is created here -- an operator manages
    them in the panel. A failure leaves the user unassigned, which the expiry
    monitor repairs on its next pass, and that is better than refusing to
    create the account at all.
    """
    client = get_client()
    try:
        squad_uuid = await resolve_paid_squad_uuid(client, get_settings().paid_squad_name)
        if not squad_uuid:
            return
        await client.set_user_squads([str(user_uuid)], [str(squad_uuid)])
        logger.info("[Remnawave] User %s placed in paid squad %s", user_uuid, squad_uuid)
    except Exception as exc:
        logger.error("[Remnawave] Failed to assign paid squad: %s", exc)


async def create_vpn_user(telegram_id: int, days_to_add: int) -> bool:
    """Create the panel user for a Telegram account. Returns success."""
    row = await _users.get_user_by_id(telegram_id)
    return await create_panel_account(
        user_row=dict(row) if row else None,
        telegram_id=telegram_id,
        days_to_add=days_to_add,
    )


async def create_panel_account(
    *, user_row: dict | None, telegram_id: int | None, days_to_add: int
) -> bool:
    """
    Create a panel account for one of our users.

    The username comes from **our** UUID, not from a Telegram ID, which is
    what lets an account exist for someone who has never used Telegram. A
    Telegram ID is still attached when we have one -- it costs nothing and an
    operator searching the panel by it expects to find them.

    Accounts created before this change keep their `str(telegram_id)` name;
    only new ones are named this way. `resolve_panel_user` reads both.
    """
    if user_row and user_row.get("id"):
        username = panel_username_for(str(user_row["id"]))
    elif telegram_id is not None:
        # No row to derive a name from. Better a legacy-shaped account than
        # no account at all -- the next lookup finds it either way.
        username = _panel_username(telegram_id)
    else:
        logger.error("[Remnawave] Cannot create a panel account with no identity")
        return False

    subscription_ends = int(time.time()) + int(days_to_add) * SECONDS_IN_DAY
    expire_at = datetime.fromtimestamp(
        panel_expire_timestamp(subscription_ends), tz=timezone.utc
    )
    body = CreateUserRequestDto(
        username=username,
        expire_at=expire_at,
        activate_all_inbounds=True,
    )
    payload = body.model_dump(mode="json", by_alias=True, exclude_none=True)
    if telegram_id is not None:
        # Some panel versions validate telegramId strictly as a number.
        payload["telegramId"] = int(telegram_id)

    try:
        user = await get_client().create_user(payload)
    except Exception as exc:
        logger.error("[Remnawave] Failed to create user %s: %s", username, exc)
        return False

    user_uuid = user.get("uuid")
    if user_uuid:
        if user_row and user_row.get("id"):
            await _users.set_panel_identity(
                str(user_row["id"]),
                remnawave_uuid=str(user_uuid),
                remnawave_username=username,
            )
        await _assign_internal_squad(str(user_uuid))
    else:
        logger.warning("[Remnawave] Cannot assign internal squad: missing user uuid")
    logger.info("[Remnawave] User %s created.", username)
    return True


async def _current_subscription_ends(telegram_id: int) -> int:
    """
    The user's real expiry, from whichever system currently owns it.

    With the FREE tier on, the panel's `expireAt` is a far-future placeholder
    (see `panel_expire_timestamp`) and reading it would extend a subscription
    from ten years out. Our own database holds the real date in that mode.
    """
    if get_settings().free_tier_enabled:
        info = await _users.get_subscription_info(telegram_id)
        return int(info["subscription_ends"] or 0) if info else 0
    return await get_user_expire(telegram_id)


async def _current_expire_for_extend(telegram_id: int, days_to_add: int) -> tuple[int | None, str | None]:
    """
    Current expiry for a user, creating the panel profile if it's missing.

    Returns `(expire_ts, error_message)` -- exactly one is non-None.
    """
    username = _panel_username(telegram_id)
    try:
        # The panel lookup is what tells us the account exists at all, so it
        # happens even when the database owns the date.
        await get_user_expire(telegram_id)
        return await _current_subscription_ends(telegram_id), None
    except UserNotFoundError:
        logger.info("[Remnawave] Пользователь @%s не найден, создаём профиль.", username)
        # Created with zero days on purpose: the caller adds `days_to_add`
        # immediately afterwards, so creating with them too would grant the
        # period twice. (It did -- this path double-counted before Phase 3.)
        if not await create_vpn_user(telegram_id, 0):
            return None, f"❌ Не удалось создать пользователя @{username}."
        return int(time.time()), None
    except Exception as exc:
        logger.error("[Remnawave] Ошибка при проверке пользователя @%s: %s", username, exc)
        return None, f"❌ Ошибка проверки пользователя @{username}."


async def set_panel_expiry(telegram_id: int, expire_ts: int) -> None:
    """
    Write a new expiry into the panel, addressing the account by UUID.

    By UUID rather than by username because the two kinds of account are named
    differently now -- legacy ones `str(telegram_id)`, new ones `u-<uuid>` --
    and patching by a name that does not exist would silently update nothing.
    """
    user = await _panel_user_for(telegram_id)
    await get_client().update_user(
        {"uuid": str(user["uuid"]), "expireAt": _utc_iso(panel_expire_timestamp(expire_ts))}
    )


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

        await set_panel_expiry(telegram_id, new_expire)
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


async def extend_subscription_for_row(user_row: dict, days_to_add: int) -> str:
    """
    Same, for a user identified by our own id rather than by a Telegram ID.

    This is what makes a website purchase creditable. `extend_subscription`
    above resolves everything through `telegram_id`, which an account created
    by email simply does not have -- so before this existed such a payment was
    taken and never applied.

    Users who *do* have a Telegram ID keep going through the function above:
    it is the same logic and changing the bot's path here would risk the
    working case to fix the broken one.
    """
    user_id = str(user_row.get("id") or "")
    if not user_id:
        return "❌ Не удалось определить пользователя."

    days_to_add = int(days_to_add)
    try:
        profile = await resolve_panel_user(user_row)
        if profile is None:
            # Created with zero days: the extension below adds them, and
            # creating with them too would grant the period twice.
            created = await create_panel_account(
                user_row=user_row, telegram_id=user_row.get("telegram_id"), days_to_add=0
            )
            if not created:
                return "❌ Не удалось создать профиль в панели."
            profile = await resolve_panel_user(await _reload_row(user_id) or user_row)
            if profile is None:
                return "❌ Профиль создан, но не найден в панели."

        current_expire = int(user_row.get("subscription_ends") or 0)
        if not get_settings().free_tier_enabled:
            # Without the FREE tier the panel still owns the date, so read it
            # back rather than trusting a row that may be behind.
            try:
                current_expire = _epoch(profile["expireAt"])
            except (KeyError, TypeError, ValueError):
                pass

        new_expire = max(current_expire, int(time.time())) + days_to_add * SECONDS_IN_DAY

        await get_client().update_user(
            {
                "uuid": str(profile["uuid"]),
                "expireAt": _utc_iso(panel_expire_timestamp(new_expire)),
            }
        )
        await _users.set_subscription_ends(user_id, new_expire)
        return (
            f"✅ Подписка продлена на {days_to_add} дней.\n"
            f"📆 Новая дата окончания: "
            f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(new_expire))}"
        )
    except Exception as exc:
        logger.error("[Remnawave] Ошибка продления подписки для %s: %s", user_id, exc)
        get_client().invalidate_token()
        return f"❌ Ошибка: {exc}"


async def _reload_row(user_id: str) -> dict | None:
    row = await _users.get_user_by_uuid(user_id)
    return dict(row) if row else None


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
