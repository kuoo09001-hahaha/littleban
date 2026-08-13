"""Read-only endpoint for inspecting family-scoped health memory."""

from datetime import datetime, timedelta
from fastapi import APIRouter, Query


def create_health_memory_router(get_store) -> APIRouter:
    router = APIRouter(tags=["health-memory"])

    @router.get("/agent/health-memory/{person_name}")
    async def list_health_memory(person_name: str, family_id: str = "default", days: int = Query(7, ge=1, le=365)):
        events = get_store().find_recent_health_events(family_id, person_name, (datetime.now() - timedelta(days=days)).isoformat())
        return {"family_id": family_id, "person_name": person_name, "events": events}

    return router
