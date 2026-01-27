"""Squad management service."""

from typing import List, Dict, Any, Optional
from app.api.client import RemnawaveClient


class SquadService:
    """Service for squad operations."""

    def __init__(self):
        self.client = RemnawaveClient()

    async def list_squads(self, squad_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of squads, optionally filtered by type."""
        endpoint = "/api/v1/squads"
        params = {"type": squad_type} if squad_type else {}
        response = await self.client.get(endpoint)
        return response.get("squads", [])

    async def get_squad(self, squad_id: str) -> Optional[Dict[str, Any]]:
        """Get squad by ID."""
        try:
            response = await self.client.get(f"/api/v1/squads/{squad_id}")
            return response
        except Exception:
            return None

    async def create_squad(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new squad."""
        return await self.client.post("/api/v1/squads", data=data)

    async def update_squad(self, squad_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update squad."""
        return await self.client.put(f"/api/v1/squads/{squad_id}", data=data)

    async def delete_squad(self, squad_id: str) -> None:
        """Delete squad."""
        await self.client.delete(f"/api/v1/squads/{squad_id}")

    async def close(self):
        """Close client connection."""
        await self.client.close()


squad_service = SquadService()
