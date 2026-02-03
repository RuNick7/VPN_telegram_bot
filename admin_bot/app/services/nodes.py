"""Node management service."""

from typing import List, Dict, Any, Optional
from app.api.client import RemnawaveClient


class NodeService:
    """Service for node operations."""

    def __init__(self):
        self.client = RemnawaveClient()

    async def list_nodes(self) -> List[Dict[str, Any]]:
        """Get list of all nodes."""
        response = await self.client.get("/v1/nodes")
        return response.get("nodes", [])

    async def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get node by ID."""
        try:
            response = await self.client.get(f"/v1/nodes/{node_id}")
            return response
        except Exception:
            return None

    async def create_node(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new node."""
        return await self.client.post("/v1/nodes", data=data)

    async def update_node(self, node_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update node."""
        return await self.client.put(f"/v1/nodes/{node_id}", data=data)

    async def delete_node(self, node_id: str) -> None:
        """Delete node."""
        await self.client.delete(f"/v1/nodes/{node_id}")

    async def close(self):
        """Close client connection."""
        await self.client.close()


node_service = NodeService()
