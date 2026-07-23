import logging
import time
import threading
from datetime import datetime, timezone

from remnawave_api.models.users import CreateUserRequestDto

from app.clients.remnawave.client import RemnawaveClient
from app.config.settings import get_remnawave_settings
from data import db_utils
from data.db_utils import get_db, update_subscription_expire


def _utc_iso_from_timestamp(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _timestamp_from_utc_iso(value: str) -> int:
    normalized = value.replace("Z", "+00:00")
    return int(datetime.fromisoformat(normalized).timestamp())


def _parse_infinite_expire_at() -> datetime:
    """Parse INFINITE_EXPIRE_DATE setting into a tz-aware datetime."""
    raw = (get_remnawave_settings().infinite_expire_date or "").strip()
    if not raw:
        raw = "2099-12-31T23:59:59.000Z"
    normalized = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        dt = datetime(2099, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _infinite_expire_iso() -> str:
    return _parse_infinite_expire_at().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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


def _find_internal_squad_by_name(
    squads: list[dict],
    name: str,
) -> dict | None:
    needle = (name or "").strip().lower()
    if not needle:
        return None
    for squad in squads:
        squad_name = str(squad.get("name") or "").strip().lower()
        if squad_name == needle:
            return squad
    return None


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


def _is_paid_internal_squad(squad: dict, prefix: str) -> bool:
    """Internal pool squads follow the `<prefix>-<n>` naming convention."""
    name = str(squad.get("name") or "")
    return name.startswith(f"{prefix}-")


def _internal_squad_index(squad: dict, prefix: str) -> int:
    """Numeric suffix from `<prefix>-<n>` (e.g. internal-3 -> 3); 0 if not paid."""
    name = str(squad.get("name") or "")
    if not name.startswith(f"{prefix}-"):
        return 0
    suffix = name[len(prefix) + 1:]
    return int(suffix) if suffix.isdigit() else 0


def _get_or_create_internal_squad(client: RemnawaveClient, token: str) -> tuple[dict | None, bool]:
    """Find or create a paid `internal-*` squad with capacity (excludes FREE/LTE).

    New users always land in the highest-indexed `internal-<N>` first; we only
    fall back to older pools when the newer ones are saturated.
    """
    settings = get_remnawave_settings()
    squads = _list_internal_squads(client, token)
    limit = settings.internal_squad_max_users
    prefix = settings.internal_squad_prefix
    paid_squads = [s for s in squads if _is_paid_internal_squad(s, prefix)]
    paid_squads_sorted = sorted(
        paid_squads, key=lambda s: _internal_squad_index(s, prefix), reverse=True
    )
    for squad in paid_squads_sorted:
        if _members_count(squad) < limit:
            return squad, False

    name = _next_internal_squad_name(prefix, squads)
    template = next((s for s in paid_squads if (s.get("inbounds") or [])), None)
    if not template:
        template = next((s for s in squads if (s.get("inbounds") or [])), None)
    inbound_ids = _extract_inbound_ids(template) if template else []
    logging.info("[Remnawave] Creating internal squad %s with %s inbounds", name, len(inbound_ids))
    return _create_internal_squad(client, name, inbound_ids, token), True


def _assign_internal_squad_for_user(client: RemnawaveClient, response: dict) -> None:
    """
    Assign newly-created user to a paid internal squad.

    LTE squad is intentionally NOT added at creation time. LTE access is a paid
    add-on that is only granted by the LTE traffic monitor when the user has a
    positive paid balance and an active subscription.
    """
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
            target_squads = [str(squad_uuid)]
            client.update_users_internal_squads([str(user_uuid)], target_squads, token_override=token)
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


def _restore_paid_squad_after_payment(client: RemnawaveClient, telegram_id: int) -> None:
    """
    Promote user from FREE squad back to a paid internal squad after payment.

    Strategy:
    - Read user's current squads.
    - If user already has a paid `internal-*` squad → leave squads untouched.
    - Otherwise: pick a paid internal squad and replace `[FREE]` with `[paid]`.
    - LTE squad assignment is left to the traffic monitor.
    """
    settings = get_remnawave_settings()
    username = str(telegram_id)
    try:
        token = client.ensure_token()
        user_resp = client.get_user_by_username(username, token_override=token)
        user = (user_resp or {}).get("response") or {}
        user_uuid = user.get("uuid")
        if not user_uuid:
            return
        active_squads = user.get("activeInternalSquads") or []
        current_uuids = [str(s.get("uuid")) for s in active_squads if s.get("uuid")]

        all_squads = _list_internal_squads(client, token)
        paid_uuids = {
            str(s.get("uuid"))
            for s in all_squads
            if _is_paid_internal_squad(s, settings.internal_squad_prefix) and s.get("uuid")
        }
        free_squad = _find_internal_squad_by_name(all_squads, settings.free_squad_name)
        free_uuid = str((free_squad or {}).get("uuid") or "")

        already_paid = any(uuid in paid_uuids for uuid in current_uuids)
        if already_paid:
            return

        squad, _created = _get_or_create_internal_squad(client, token)
        target_uuid = str((squad or {}).get("uuid") or "")
        if not target_uuid:
            logging.warning("[Remnawave] No paid squad available for restore: tg=%s", telegram_id)
            return

        new_squads = [u for u in current_uuids if u and u != free_uuid]
        if target_uuid not in new_squads:
            new_squads.append(target_uuid)
        client.update_users_internal_squads([str(user_uuid)], new_squads, token_override=token)
        logging.info(
            "[Remnawave] Restored paid squad for tg=%s: %s → %s",
            telegram_id,
            current_uuids,
            new_squads,
        )
    except Exception as exc:
        logging.warning("[Remnawave] Failed to restore paid squad for tg=%s: %s", telegram_id, exc)


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
    """
    Create user in Remnawave with infinite expireAt.

    `days_to_add` is no longer applied to the panel: we count days locally in
    the subscription DB and the panel keeps the user technically valid forever.
    The argument is preserved for callers' compatibility.
    """
    del days_to_add  # kept for backwards compatibility
    username = f"{telegram_id}"
    expire_at = _parse_infinite_expire_at()
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


def _ensure_remnawave_user_for_extend(telegram_id: int, token: str) -> tuple[bool, str | None]:
    """
    Ensure user exists in Remnawave before extension.
    Returns (existed_or_created, error_message).
    """
    username = f"{telegram_id}"
    try:
        get_user_expire(username, token)
        return True, None
    except ValueError as exc:
        if "User not found" not in str(exc):
            logging.error("[Remnawave] Ошибка получения профиля @%s: %s", username, exc)
            return False, f"❌ Ошибка получения профиля @{username}."

        logging.info("[Remnawave] Пользователь @%s не найден, создаём профиль.", username)
        created_ok = create_vpn_user_by_telegram_id(telegram_id, 0)
        if not created_ok:
            return False, f"❌ Не удалось создать пользователя @{username}."
        return True, None
    except Exception as exc:
        logging.error("[Remnawave] Ошибка при проверке пользователя @%s: %s", username, exc)
        return False, f"❌ Ошибка проверки пользователя @{username}."


def extend_subscription_by_telegram_id(telegram_id: int, days_to_add: int) -> str:
    """
    Extend local subscription_ends by `days_to_add`.

    Panel's expireAt is held at INFINITE_EXPIRE_DATE: we never push the local
    end date to Remnawave. After updating the DB we promote the user back to a
    paid internal squad if they were demoted to FREE.
    """
    try:
        username = f"{telegram_id}"
        logging.info("[Remnawave] Extend subscription for @%s by %sd", username, days_to_add)

        token = get_token(telegram_id)
        ensured, ensure_error = _ensure_remnawave_user_for_extend(telegram_id, token)
        if ensure_error:
            return ensure_error
        if not ensured:
            return f"❌ Ошибка проверки пользователя @{username}."

        days_to_add = int(days_to_add)
        if not db_utils.user_in_db(telegram_id):
            db_utils.create_user_record(telegram_id, username)

        user_row = db_utils.get_user_by_id(telegram_id)
        current_local_expire = int(user_row["subscription_ends"]) if user_row else 0
        new_expire = max(current_local_expire, int(time.time())) + days_to_add * 86400
        update_subscription_expire(telegram_id, new_expire)

        # Make sure panel still reports infinite expiration. This is idempotent:
        # if the user was created with the old logic (real expireAt) we lift it
        # to infinity here; for new users the patch is a no-op.
        try:
            payload = {"username": username, "expireAt": _infinite_expire_iso()}
            _client().update_user(payload, token_override=token)
        except Exception as exc:
            logging.warning("[Remnawave] Failed to enforce infinite expireAt for @%s: %s", username, exc)

        # Bring user back from FREE squad immediately so they don't have to wait
        # for the next subscription monitor cycle.
        try:
            _restore_paid_squad_after_payment(_client(), telegram_id)
        except Exception as exc:
            logging.warning("[Remnawave] Failed to restore paid squad for @%s: %s", username, exc)

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
            ok = create_vpn_user_by_telegram_id(telegram_id, 0)
            logging.info("[Remnawave] Профиль создан: %s", ok)
        else:
            logging.error("[Remnawave] Ошибка при проверке профиля: %s", exc)


def _reset_reminded_flag(username: int) -> None:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE subscription SET reminded = 0 WHERE telegram_id = ?", (username,))
        conn.commit()
