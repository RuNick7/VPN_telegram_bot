import logging
from typing import Any

import requests


class RemnawaveClient:
    def __init__(
        self,
        base_url: str,
        token: str | None,
        username: str | None,
        password: str | None,
        timeout_seconds: int,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._username = username
        self._password = password
        self._timeout_seconds = timeout_seconds

    def _headers(self, token_override: str | None = None) -> dict[str, str]:
        token = token_override or self._token
        if not token:
            return {}
        return {"Authorization": f"Bearer {token}"}

    def login(self) -> str:
        if not self._username or not self._password:
            raise ValueError("REMNAWAVE_USERNAME/REMNAWAVE_PASSWORD are not set")

        url = f"{self._base_url}/api/auth/login"
        resp = requests.post(
            url,
            json={"username": self._username, "password": self._password},
            timeout=self._timeout_seconds,
        )
        resp.raise_for_status()
        token = resp.json()["response"]["accessToken"]
        self._token = token
        return token

    def ensure_token(self) -> str:
        if self._token:
            return self._token
        return self.login()

    def get_user_by_username(self, username: str, token_override: str | None = None) -> dict[str, Any]:
        token = token_override or self.ensure_token()
        url = f"{self._base_url}/api/users/by-username/{username}"
        resp = requests.get(
            url,
            headers=self._headers(token),
            timeout=self._timeout_seconds,
        )
        if resp.status_code == 404:
            raise ValueError("User not found")
        resp.raise_for_status()
        return resp.json()

    def create_user(self, payload: dict[str, Any], token_override: str | None = None) -> dict[str, Any]:
        token = token_override or self.ensure_token()
        url = f"{self._base_url}/api/users"
        resp = requests.post(
            url,
            headers=self._headers(token),
            json=payload,
            timeout=self._timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()

    def list_users(self, page: int = 1, size: int = 100, token_override: str | None = None) -> dict[str, Any]:
        token = token_override or self.ensure_token()
        url = f"{self._base_url}/api/users"
        resp = requests.get(
            url,
            headers=self._headers(token),
            params={"page": page, "size": size, "limit": size},
            timeout=self._timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()

    def list_internal_squads(self, token_override: str | None = None) -> dict[str, Any]:
        token = token_override or self.ensure_token()
        url = f"{self._base_url}/api/internal-squads"
        resp = requests.get(
            url,
            headers=self._headers(token),
            timeout=self._timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()

    def create_internal_squad(self, payload: dict[str, Any], token_override: str | None = None) -> dict[str, Any]:
        token = token_override or self.ensure_token()
        url = f"{self._base_url}/api/internal-squads"
        resp = requests.post(
            url,
            headers=self._headers(token),
            json=payload,
            timeout=self._timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()

    def add_users_to_internal_squad(
        self,
        squad_uuid: str,
        user_uuids: list[str],
        token_override: str | None = None,
    ) -> dict[str, Any]:
        token = token_override or self.ensure_token()
        url = f"{self._base_url}/api/internal-squads/{squad_uuid}/bulk-actions/add-users"
        resp = requests.post(
            url,
            headers=self._headers(token),
            json={"userUuids": user_uuids},
            timeout=self._timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()

    def update_users_internal_squads(
        self,
        user_uuids: list[str],
        squad_uuids: list[str],
        token_override: str | None = None,
    ) -> dict[str, Any]:
        token = token_override or self.ensure_token()
        url = f"{self._base_url}/api/users/bulk/update-squads"
        resp = requests.post(
            url,
            headers=self._headers(token),
            json={"uuids": user_uuids, "activeInternalSquads": squad_uuids},
            timeout=self._timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()
    def remove_users_from_internal_squad(
        self,
        squad_uuid: str,
        user_uuids: list[str],
        token_override: str | None = None,
    ) -> dict[str, Any]:
        token = token_override or self.ensure_token()
        url = f"{self._base_url}/api/internal-squads/{squad_uuid}/bulk-actions/remove-users"
        resp = requests.delete(
            url,
            headers=self._headers(token),
            json={"userUuids": user_uuids},
            timeout=self._timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()

    def update_user(self, payload: dict[str, Any], token_override: str | None = None) -> dict[str, Any]:
        token = token_override or self.ensure_token()
        url = f"{self._base_url}/api/users"
        resp = requests.patch(
            url,
            headers=self._headers(token),
            json=payload,
            timeout=self._timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()

    def get_subscription_by_username(self, username: str, token_override: str | None = None) -> dict[str, Any]:
        token = token_override or self.ensure_token()
        url = f"{self._base_url}/api/subscriptions/by-username/{username}"
        resp = requests.get(
            url,
            headers=self._headers(token),
            timeout=self._timeout_seconds,
        )
        if resp.status_code == 404:
            raise ValueError("User not found")
        resp.raise_for_status()
        return resp.json()

    def debug_log_response(self, response: dict[str, Any], label: str) -> None:
        logging.debug("[Remnawave] %s response: %s", label, response)
