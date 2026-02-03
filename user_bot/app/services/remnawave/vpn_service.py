import logging
import time
import threading
from datetime import datetime, timezone

from app.clients.remnawave.client import RemnawaveClient
from app.config.settings import get_remnawave_settings
from data import db_utils
from data.db_utils import get_db, update_subscription_expire


def _utc_iso_from_timestamp(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _timestamp_from_utc_iso(value: str) -> int:
    normalized = value.replace("Z", "+00:00")
    return int(datetime.fromisoformat(normalized).timestamp())


def _client() -> RemnawaveClient:
    settings = get_remnawave_settings()
    return RemnawaveClient(
        base_url=settings.base_url,
        token=settings.token,
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
    return _client().ensure_token()


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
    payload = {
        "username": username,
        "expireAt": _utc_iso_from_timestamp(expire_time),
        "telegramId": telegram_id,
        "status": "ACTIVE",
        "trafficLimitBytes": 0,
        "trafficLimitStrategy": "NO_RESET",
    }
    try:
        client = _client()
        response = client.create_user(payload)
        _assign_internal_squad_for_user(client, response)
        logging.info("[Remnawave] User %s created.", username)
        return True
    except Exception as exc:
        logging.error("[Remnawave] Failed to create user %s: %s", username, exc)
        return False


def extend_subscription_by_telegram_id(telegram_id: int, days_to_add: int) -> str:
    try:
        username = f"{telegram_id}"
        logging.info("[Remnawave] Extend subscription for @%s", username)

        token = get_token(telegram_id)
        try:
            current_expire = get_user_expire(username, token)
        except ValueError as exc:
            if "User not found" in str(exc):
                created_ok = create_vpn_user_by_telegram_id(telegram_id, days_to_add)
                if not created_ok:
                    return f"❌ Не удалось создать пользователя @{username}."
                current_expire = int(time.time())
            else:
                logging.error("[Remnawave] Ошибка при получении срока подписки @%s: %s", username, exc)
                return f"❌ Ошибка получения срока подписки @{username}."

        days_to_add = int(days_to_add)
        new_expire = max(current_expire, int(time.time())) + days_to_add * 86400
        payload = {"username": username, "expireAt": _utc_iso_from_timestamp(new_expire)}

        _client().update_user(payload, token_override=token)
        update_subscription_expire(telegram_id, new_expire)
        _reset_reminded_flag(telegram_id)
        return (
            f"✅ Подписка @{username} продлена на {days_to_add} дней.\n"
            f"📆 Новая дата окончания: "
            f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(new_expire))}"
        )
    except Exception as exc:
        logging.error("[Remnawave] Ошибка продления подписки: %s", exc)
        return f"❌ Ошибка: {str(exc)}"


def ensure_vpn_profile_created_if_missing(telegram_id: int) -> None:
    try:
        token = get_token(telegram_id)
        username = str(telegram_id)
        get_user_expire(username, token)
        logging.info("[Remnawave] Профиль %s уже существует — не создаём повторно.", username)
    except Exception as exc:
        if "User not found" in str(exc):
            user = db_utils.get_user_by_id(telegram_id)
            if not user:
                logging.warning("[Remnawave] Пользователь %s не найден в БД.", telegram_id)
                return
            days_left = max((user["subscription_ends"] - int(time.time())) // 86400, 1)
            result = extend_subscription_by_telegram_id(telegram_id, days_left)
            logging.info("[Remnawave] Профиль создан: %s", result)
        else:
            logging.error("[Remnawave] Ошибка при проверке профиля: %s", exc)


def _reset_reminded_flag(username: int) -> None:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE subscription SET reminded = 0 WHERE telegram_id = ?", (username,))
        conn.commit()
