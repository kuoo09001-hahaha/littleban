"""Browser geolocation endpoints with Amap reverse geocoding."""

import httpx
from fastapi import APIRouter, HTTPException

from config.settings import settings
from schemas.agent import LocationUpdateRequest


def create_location_router(get_store) -> APIRouter:
    router = APIRouter(tags=["location"])

    @router.get("/agent/location/{session_id}")
    async def get_location(session_id: str):
        return {"location": get_store().get_session_location(session_id)}

    @router.put("/agent/location/{session_id}")
    async def update_location(session_id: str, request: LocationUpdateRequest):
        params = {"key": settings.AMAP_API_KEY, "location": f"{request.longitude},{request.latitude}", "extensions": "base"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(settings.AMAP_REGEOCODE_URL, params=params)
            data = response.json()
            address = data.get("regeocode", {}).get("addressComponent", {}) if response.status_code == 200 else {}
            city = address.get("city") or address.get("province")
            district = address.get("district") or ""
            if not city:
                raise ValueError("未能识别当前位置所属城市")
            location = get_store().set_session_location(session_id, request.latitude, request.longitude, f"{city}{district}")
            return {"success": True, "location": location}
        except Exception as error:
            raise HTTPException(status_code=502, detail=f"定位反查失败：{error}") from error

    return router
