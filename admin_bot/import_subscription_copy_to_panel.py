import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from remnawave_api.models.users import CreateUserRequestDto

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from user_bot.app.clients.remnawave.client import RemnawaveClient
from user_bot.app.config.settings import get_remnawave_settings


SOURCE_DB_PATH = Path(__file__).resolve().parents[1] / "user_bot" / "data" / "subscription copy.db"
INACTIVE_DAYS = 30
PAGE_SIZE = 200


def load_eligible_rows(db_path: Path, inactive_days: int) -> list[dict]:
    if not db_path.exists():
        raise RuntimeError(f"Source DB not found: {db_path}")

    threshold_ts = int(datetime.now(timezone.utc).timestamp()) - (inactive_days * 24 * 60 * 60)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT s.telegram_id, s.subscription_ends
            FROM subscription s
            WHERE s.id = (
                SELECT s2.id
                FROM subscription s2
                WHERE s2.telegram_id = s.telegram_id
                ORDER BY s2.subscription_ends DESC, s2.id DESC
                LIMIT 1
            )
              AND s.subscription_ends IS NOT NULL
              AND s.subscription_ends > 0
              AND s.subscription_ends >= ?
            ORDER BY s.telegram_id
            """,
            (threshold_ts,),
        ).fetchall()
    finally:
        conn.close()

    result: list[dict] = []
    for row in rows:
        tg_id = row["telegram_id"]
        sub_end = row["subscription_ends"]
        if tg_id is None or sub_end is None:
            continue
        result.append({"telegram_id": int(tg_id), "subscription_ends": int(sub_end)})
    return result


def _extract_users(response: dict) -> tuple[list[dict], int]:
    data = response.get("response") if isinstance(response.get("response"), dict) else response
    users = data.get("users") or []
    total = int(data.get("total") or len(users))
    return users, total


def list_all_panel_user_uuids(client: RemnawaveClient, token: str) -> list[str]:
    page = 1
    uuids: list[str] = []
    while True:
        response = client.list_users(page=page, size=PAGE_SIZE, token_override=token)
        users, total = _extract_users(response)
        for user in users:
            uuid = user.get("uuid")
            if uuid:
                uuids.append(str(uuid))
        max_page = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        if page >= max_page:
            break
        page += 1
    return uuids


def delete_all_panel_users(client: RemnawaveClient, token: str) -> tuple[int, int]:
    uuids = list_all_panel_user_uuids(client, token)
    deleted = 0
    failed = 0
    for uuid in uuids:
        try:
            resp = requests.delete(
                f"{client._base_url}/api/users/{uuid}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=client._timeout_seconds,
            )
            resp.raise_for_status()
            deleted += 1
        except Exception:
            failed += 1
    return deleted, failed


def import_rows(client: RemnawaveClient, token: str, rows: list[dict]) -> tuple[int, int]:
    imported = 0
    failed = 0
    for item in rows:
        tg_id = int(item["telegram_id"])
        expire_at = datetime.fromtimestamp(int(item["subscription_ends"]), tz=timezone.utc)
        dto = CreateUserRequestDto(
            username=str(tg_id),
            telegram_id=tg_id,
            expire_at=expire_at,
            activate_all_inbounds=True,
        )
        payload = dto.model_dump(mode="json", by_alias=True, exclude_none=True)
        try:
            client.create_user(payload, token_override=token)
            imported += 1
        except Exception:
            failed += 1
    return imported, failed


def main() -> None:
    env = get_remnawave_settings()
    print(f"Remnawave URL: {env.base_url}")
    print(f"Source DB: {SOURCE_DB_PATH}")
    rows = load_eligible_rows(SOURCE_DB_PATH, INACTIVE_DAYS)
    print(f"Eligible users (subscription active or ended <= {INACTIVE_DAYS} days): {len(rows)}")

    client = RemnawaveClient(
        base_url=env.base_url,
        token=env.token,
        username=env.username,
        password=env.password,
        timeout_seconds=env.timeout_seconds,
    )

    token = client.ensure_token()
    if env.token:
        try:
            # Validate provided API token first.
            client.list_users(page=1, size=1, token_override=token)
        except Exception:
            if env.username and env.password:
                # Fallback to login if static token is invalid/expired.
                token = client.login()
            else:
                raise

    deleted, delete_failed = delete_all_panel_users(client, token)
    print(f"Deleted users from panel: {deleted}, delete_failed: {delete_failed}")

    imported, import_failed = import_rows(client, token, rows)
    print(f"Imported users: {imported}, import_failed: {import_failed}")


if __name__ == "__main__":
    main()
