import logging
import time
import threading
from datetime import datetime, timezone

import asyncpg
from remnawave_api.models.users import CreateUserRequestDto

from app.clients.remnawave.client import RemnawaveClient
from app.config.settings import get_remnawave_settings
from tgvpn_shared.sync_bridge import run_sync

# Phase 1 stopgap: this module's public functions are synchronous (they make
# blocking Remnawave HTTP calls via `requests`, always invoked through
# `asyncio.to_thread` by callers) while Postgres access is async-only. Rather
# than restructure the sync/async boundary here -- that's Phase 2, once the
# Remnawave client itself becomes natively async -- these small helpers bridge
# the handful of DB touches through `run_sync`. See
# shared/tgvpn_shared/sync_bridge.py for why this doesn't reuse the shared
# connection pool.


async def _user_in_db(conn: asyncpg.Connection, telegram_id: int) -> bool:
    row = await conn.fetchrow("SELECT 1 FROM users WHERE telegram_id = $1", telegram_id)
    return row is not None


async def _create_user_record(conn: asyncpg.Connection, telegram_id: int, username: str) -> None:
    await conn.execute(
        """
        INSERT INTO users (telegram_id, telegram_tag, subscription_ends, reminded, nurture_stage, created_at)
        VALUES ($1, $2, to_timestamp(0), FALSE, 0, now())
        """,
        telegram_id, username,
    )


async def _update_subscription_expire(conn: asyncpg.Connection, telegram_id: int, new_expire: int) -> None:
    await conn.execute(
        "UPDATE users SET subscription_ends = to_timestamp($1) WHERE telegram_id = $2",
        new_expire, telegram_id,
    )


async def _ensure_user_record_and_update_expire(
    conn: asyncpg.Connection, telegram_id: int, username: str, new_expire: int
) -> None:
    async with conn.transaction():
        if not await _user_in_db(conn, telegram_id):
            await _create_user_record(conn, telegram_id, username)
        await _update_subscription_expire(conn, telegram_id, new_expire)


async def _get_user_subscription_ends(conn: asyncpg.Connection, telegram_id: int) -> int | None:
    return await conn.fetchval(
        "SELECT EXTRACT(EPOCH FROM subscription_ends)::bigint FROM users WHERE telegram_id = $1",
        telegram_id,
    )


async def _reset_reminded_flag_async(conn: asyncpg.Connection, telegram_id: int) -> None:
    await conn.execute("UPDATE users SET reminded = FALSE WHERE telegram_id = $1", telegram_id)


def _utc_iso_from_timestamp(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _timestamp_from_utc_iso(value: str) -> int:
    normalized = value.replace("Z", "+00:00")
    return int(datetime.fromisoformat(normalized).timestamp())


# Кэш токена панели: без него каждый вызов (_client + ensure_token) делает
# отдельный POST /api/auth/login — одно продление по платежу давало 3 логина.
_TOKEN_TTL_SECONDS = 900
_token_cache: dict = {"token": None, "ts": 0.0}


def invalidate_cached_token() -> None:
    """Сбросить кэш токена (например, после 401 от панели)."""
    _token_cache["token"] = None
    _token_cache["ts"] = 0.0


def _cached_token() -> str | None:
    if _token_cache["token"] and (time.time() - _token_cache["ts"]) < _TOKEN_TTL_SECONDS:
        return _token_cache["token"]
    return None


def _client() -> RemnawaveClient:
    settings = get_remnawave_settings()
    return RemnawaveClient(
        base_url=settings.base_url,
        token=settings.token or _cached_token(),
        username=settings.username,
        password=settings.password,
        timeout_seconds=settings.timeout_seconds,
    )


def _extract_user_uuid(response: dict) -> str | None:
    return (response.get("response", {}) or {}).get("uuid") or response.get("uuid")


def _list_internal_squads(client: RemnawaveClient, token: str) -> list[dict]:
    response = client.list_internal_squads(token_override=token)
    return response.get("response", {}).get("internalSquads", []) or []


def _members_count(squad: dict) -> int:
    info = squad.get("info") or {}
    count = info.get("membersCount")
    return int(count) if isinstance(count, int) else 0


def _next_internal_squad_name(prefix: str, squads: list[dict]) -> str:
    max_index = 0
    for squad in squads:
        name = squad.get("name") or ""
        if not name.startswith(f"{prefix}-"):
            continue
        suffix = name[len(prefix) + 1:]
        if suffix.isdigit():
            max_index = max(max_index, int(suffix))
    return f"{prefix}-{max_index + 1}"


def _extract_inbound_ids(squad: dict) -> list[str]:
    inbounds = squad.get("inbounds") or []
    inbound_ids = []
    for inbound in inbounds:
        uuid = inbound.get("uuid")
        if uuid:
            inbound_ids.append(str(uuid))
    return inbound_ids


def _create_internal_squad(client: RemnawaveClient, name: str, inbound_ids: list[str], token: str) -> dict:
    response = client.create_internal_squad(
        {"name": name, "inbounds": inbound_ids},
        token_override=token,
    )
    return response.get("response", {}) or response


def _assign_user_to_internal_squad(
    client: RemnawaveClient,
    squad_uuid: str,
    user_uuid: str,
    token: str,
) -> None:
    client.add_users_to_internal_squad(
        squad_uuid,
        [user_uuid],
        token_override=token,
    )


def _normalize_new_squad_members(client: RemnawaveClient, squad_uuid: str, user_uuid: str, token: str, delay_seconds: float = 5.0) -> None:
    time.sleep(delay_seconds)
    response = client.list_users(page=1, size=200, token_override=token)
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
            client.update_users_internal_squads([str(uuid)], desired, token_override=token)
            logging.info("[Remnawave] Updated user %s squads -> %s", uuid, desired)
        except Exception as exc:
            logging.warning("[Remnawave] Failed to update user %s squads: %s", uuid, exc)


def _list_all_user_uuids(client: RemnawaveClient, token: str) -> list[str]:
    page = 1
    size = 100
    uuids: list[str] = []
    while True:
        response = client.list_users(page=page, size=size, token_override=token)
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


def _get_or_create_internal_squad(client: RemnawaveClient, token: str) -> tuple[dict | None, bool]:
    settings = get_remnawave_settings()
    squads = _list_internal_squads(client, token)
    limit = settings.internal_squad_max_users
    for squad in squads:
        if _members_count(squad) < limit:
            return squad, False

    prefix = settings.internal_squad_prefix
    name = _next_internal_squad_name(prefix, squads)
    template = next((s for s in squads if (s.get("inbounds") or [])), None)
    inbound_ids = _extract_inbound_ids(template) if template else []
    logging.info("[Remnawave] Creating internal squad %s with %s inbounds", name, len(inbound_ids))
    return _create_internal_squad(client, name, inbound_ids, token), True


def _assign_internal_squad_for_user(client: RemnawaveClient, response: dict) -> None:
    user_uuid = _extract_user_uuid(response)
    if not user_uuid:
        logging.warning("[Remnawave] Cannot assign internal squad: missing user uuid")
        return
    try:
        logging.info("[Remnawave] Assigning internal squad for user uuid=%s", user_uuid)
        token = client.ensure_token()
        squad, created = _get_or_create_internal_squad(client, token)
        squad_uuid = (squad or {}).get("uuid")
        if squad_uuid:
            logging.info("[Remnawave] Selected squad %s created=%s", squad_uuid, created)
            client.update_users_internal_squads([str(user_uuid)], [str(squad_uuid)], token_override=token)
            if created:
                try:
                    threading.Thread(
                        target=_normalize_new_squad_members,
                        args=(client, str(squad_uuid), str(user_uuid), token),
                        daemon=True,
                    ).start()
                except Exception as exc:
                    logging.warning("[Remnawave] Failed to schedule squad normalization: %s", exc)
        else:
            logging.warning("[Remnawave] Internal squad not found/created for user %s", user_uuid)
    except Exception as exc:
        logging.error("[Remnawave] Failed to assign internal squad: %s", exc)


def get_token(_telegram_id: int) -> str:
    settings = get_remnawave_settings()
    if settings.token:
        return settings.token
    cached = _cached_token()
    if cached:
        return cached
    token = _client().ensure_token()
    _token_cache["token"] = token
    _token_cache["ts"] = time.time()
    return token


def get_user_expire(username: str, token: str | None = None) -> int:
    response = _client().get_user_by_username(username, token_override=token)
    expire_at = response["response"]["expireAt"]
    return _timestamp_from_utc_iso(expire_at)


def get_subscription_url(username: str, token: str | None = None) -> str:
    response = _client().get_user_by_username(username, token_override=token)
    return response["response"].get("subscriptionUrl", "")


def create_vpn_user_by_telegram_id(telegram_id: int, days_to_add: int) -> bool:
    username = f"{telegram_id}"
    now = int(time.time())
    expire_time = now + int(days_to_add) * 86400
    expire_at = datetime.fromtimestamp(expire_time, tz=timezone.utc)
    body = CreateUserRequestDto(
        username=username,
        telegram_id=telegram_id,
        expire_at=expire_at,
        activate_all_inbounds=True,
    )
    payload = body.model_dump(mode="json", by_alias=True, exclude_none=True)
    # Some API versions validate telegramId strictly as number.
    payload["telegramId"] = int(telegram_id)
    try:
        client = _client()
        response = client.create_user(payload)
        _assign_internal_squad_for_user(client, response)
        logging.info("[Remnawave] User %s created.", username)
        return True
    except Exception as exc:
        logging.error("[Remnawave] Failed to create user %s: %s", username, exc)
        return False


def _ensure_remnawave_user_for_extend(telegram_id: int, days_to_add: int, token: str) -> tuple[int | None, str | None]:
    """
    Ensure user exists in Remnawave before extension.
    Returns (current_expire_ts, error_message).
    """
    username = f"{telegram_id}"
    try:
        current_expire = get_user_expire(username, token)
        return current_expire, None
    except ValueError as exc:
        if "User not found" not in str(exc):
            logging.error("[Remnawave] Ошибка получения срока подписки @%s: %s", username, exc)
            return None, f"❌ Ошибка получения срока подписки @{username}."

        logging.info("[Remnawave] Пользователь @%s не найден, создаём профиль.", username)
        created_ok = create_vpn_user_by_telegram_id(telegram_id, days_to_add)
        if not created_ok:
            return None, f"❌ Не удалось создать пользователя @{username}."

        try:
            # Re-read actual expire from panel after successful create.
            current_expire = get_user_expire(username, token)
            return current_expire, None
        except Exception as exc2:
            logging.warning(
                "[Remnawave] Пользователь @%s создан, но срок не удалось прочитать: %s",
                username,
                exc2,
            )
            return int(time.time()), None
    except Exception as exc:
        logging.error("[Remnawave] Ошибка при проверке пользователя @%s: %s", username, exc)
        return None, f"❌ Ошибка проверки пользователя @{username}."


def extend_subscription_by_telegram_id(telegram_id: int, days_to_add: int) -> str:
    try:
        username = f"{telegram_id}"
        logging.info("[Remnawave] Extend subscription for @%s", username)

        token = get_token(telegram_id)
        current_expire, ensure_error = _ensure_remnawave_user_for_extend(telegram_id, days_to_add, token)
        if ensure_error:
            return ensure_error
        if current_expire is None:
            return f"❌ Ошибка проверки пользователя @{username}."

        days_to_add = int(days_to_add)
        new_expire = max(current_expire, int(time.time())) + days_to_add * 86400
        payload = {"username": username, "expireAt": _utc_iso_from_timestamp(new_expire)}

        _client().update_user(payload, token_override=token)
        run_sync(lambda conn: _ensure_user_record_and_update_expire(conn, telegram_id, username, new_expire))
        _reset_reminded_flag(telegram_id)
        return (
            f"✅ Подписка @{username} продлена на {days_to_add} дней.\n"
            f"📆 Новая дата окончания: "
            f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(new_expire))}"
        )
    except Exception as exc:
        logging.error("[Remnawave] Ошибка продления подписки: %s", exc)
        invalidate_cached_token()
        return f"❌ Ошибка: {str(exc)}"


def ensure_vpn_profile_created_if_missing(telegram_id: int) -> None:
    try:
        token = get_token(telegram_id)
        username = str(telegram_id)
        get_user_expire(username, token)
        logging.info("[Remnawave] Профиль %s уже существует — не создаём повторно.", username)
    except Exception as exc:
        if "User not found" in str(exc):
            subscription_ends = run_sync(lambda conn: _get_user_subscription_ends(conn, telegram_id))
            if subscription_ends is None:
                logging.warning("[Remnawave] Пользователь %s не найден в БД.", telegram_id)
                return
            days_left = max((subscription_ends - int(time.time())) // 86400, 1)
            result = extend_subscription_by_telegram_id(telegram_id, days_left)
            logging.info("[Remnawave] Профиль создан: %s", result)
        else:
            logging.error("[Remnawave] Ошибка при проверке профиля: %s", exc)


def _reset_reminded_flag(telegram_id: int) -> None:
    run_sync(lambda conn: _reset_reminded_flag_async(conn, telegram_id))
