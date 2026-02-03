"""Remnawave API client using the official SDK."""

import httpx
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from remnawave_api import RemnawaveSDK
from app.config.settings import settings
from app.api.errors import APIError, handle_api_error


class RemnawaveClient:
    """SDK-backed client for Remnawave API."""

    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self.base_url = self._normalize_base_url(settings.remnawave_api_url)
        self.api_key = settings.remnawave_api_key
        self.sdk = RemnawaveSDK(base_url=self.base_url, token=self.api_key)
        # SDK exposes its internal AsyncClient for custom requests
        self.client: httpx.AsyncClient = self.sdk._client
        timeout_seconds = max(1, int(getattr(settings, "remnawave_timeout_seconds", 5)))
        self.client.timeout = httpx.Timeout(timeout_seconds)
        self._logger.info("Remnawave base URL: %s", self.base_url)

    @staticmethod
    def _normalize_base_url(value: str) -> str:
        """Normalize and validate base URL."""
        if not value:
            raise APIError("REMNAWAVE_BASE_URL is empty.")
        base_url = value.strip()
        if base_url.endswith("/api"):
            base_url = base_url[:-4]
        if base_url.endswith("/api/"):
            base_url = base_url[:-5]
        if not base_url.startswith(("http://", "https://")):
            base_url = f"https://{base_url}"
        parsed = urlparse(base_url)
        if not parsed.hostname:
            raise APIError(f"Invalid REMNAWAVE_BASE_URL: {value}")
        return f"{base_url}/api"

    async def request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Make an API request."""
        try:
            response = await self.client.request(method, endpoint, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise handle_api_error(e)
        except httpx.RequestError as e:
            message = str(e) or type(e).__name__
            raise APIError(
                f"Request failed: {message} (base_url={self.base_url}, endpoint={endpoint})"
            ) from e

    async def get(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """GET request."""
        return await self.request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, data: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """POST request."""
        return await self.request("POST", endpoint, json=data, **kwargs)

    async def put(self, endpoint: str, data: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """PUT request."""
        return await self.request("PUT", endpoint, json=data, **kwargs)

    async def delete(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """DELETE request."""
        return await self.request("DELETE", endpoint, **kwargs)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
