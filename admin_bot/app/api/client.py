"""Remnawave API client using the official SDK."""

import httpx
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from remnawave_api import RemnawaveSDK
from app.config.settings import settings
from app.api.errors import APIError, handle_api_error


class RemnawaveClient:
    """SDK-backed client for Remnawave API."""

    def __init__(self):
        self.base_url = self._normalize_base_url(settings.remnawave_api_url)
        self.api_key = settings.remnawave_api_key
        self.sdk = RemnawaveSDK(base_url=self.base_url, token=self.api_key)
        # SDK exposes its internal AsyncClient for custom requests
        self.client: httpx.AsyncClient = self.sdk._client

    @staticmethod
    def _normalize_base_url(value: str) -> str:
        """Normalize and validate base URL."""
        if not value:
            raise APIError("REMNAWAVE_API_URL is empty.")
        base_url = value.strip()
        if not base_url.startswith(("http://", "https://")):
            base_url = f"https://{base_url}"
        parsed = urlparse(base_url)
        if not parsed.hostname:
            raise APIError(f"Invalid REMNAWAVE_API_URL: {value}")
        return base_url

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
            raise APIError(f"Request failed: {str(e)}") from e

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
