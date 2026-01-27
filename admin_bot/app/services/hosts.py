"""Host management service."""

from typing import List, Dict, Any, Optional
from app.api.client import RemnawaveClient


class HostService:
    """Service for host operations."""

    def __init__(self):
        self.client = RemnawaveClient()

    async def list_hosts(self, node_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of hosts, optionally filtered by node."""
        endpoint = "/api/v1/hosts"
        params = {"node_id": node_id} if node_id else {}
        response = await self.client.get(endpoint)
        return response.get("hosts", [])

    async def get_host(self, host_id: str) -> Optional[Dict[str, Any]]:
        """Get host by ID."""
        try:
            response = await self.client.get(f"/api/v1/hosts/{host_id}")
            return response
        except Exception:
            return None

    async def create_host(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new host."""
        return await self.client.post("/api/v1/hosts", data=data)

    async def update_host(self, host_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update host."""
        return await self.client.put(f"/api/v1/hosts/{host_id}", data=data)

    async def delete_host(self, host_id: str) -> None:
        """Delete host."""
        await self.client.delete(f"/api/v1/hosts/{host_id}")

    async def bulk_create_hosts(self, hosts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Bulk create hosts."""
        return await self.client.post("/api/v1/hosts/bulk", data={"hosts": hosts})

    async def close(self):
        """Close client connection."""
        await self.client.close()


host_service = HostService()
