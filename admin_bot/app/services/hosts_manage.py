"""Host management helpers for quick creation."""

from typing import Any, Dict, List

from app.api.client import RemnawaveClient


class HostManageService:
    """Service for host-related listing and updates."""

    def __init__(self):
        self.client = RemnawaveClient()

    async def list_inbounds(self) -> List[Dict[str, Any]]:
        response = await self.client.request("GET", "/config-profiles/inbounds")
        return response.get("response", {}).get("inbounds", [])

    async def list_nodes(self) -> List[Dict[str, Any]]:
        response = await self.client.request("GET", "/nodes")
        return response.get("response", [])

    async def list_internal_squads(self) -> List[Dict[str, Any]]:
        response = await self.client.request("GET", "/internal-squads")
        return response.get("response", {}).get("internalSquads", [])

    async def list_hosts(self) -> List[Dict[str, Any]]:
        response = await self.client.request("GET", "/hosts")
        return response.get("response", [])

    async def get_host(self, host_uuid: str) -> Dict[str, Any]:
        response = await self.client.request("GET", f"/hosts/{host_uuid}")
        return response.get("response", {})

    async def create_host(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self.client.request("POST", "/hosts", json=payload)

    async def update_host(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self.client.request("PATCH", "/hosts", json=payload)

    async def delete_host(self, host_uuid: str) -> Dict[str, Any]:
        payload = {"uuids": [host_uuid]}
        return await self.client.request("POST", "/hosts/bulk/delete", json=payload)


host_manage_service = HostManageService()
