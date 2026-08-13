"""Device configuration Agent API routes."""

from typing import Callable

from fastapi import APIRouter, HTTPException

from schemas.agent import DeviceConfigRequest, DeviceConfigResponse, DeviceModeRequest, DeviceModeResponse
from services.device_config_service import DeviceConfigService
from services.device_mode_service import DeviceModeService


router = APIRouter()


def create_devices_router(
    get_device_mode_service: Callable[[], DeviceModeService],
    get_device_config_service: Callable[[], DeviceConfigService],
) -> APIRouter:
    """Create device configuration routes."""

    @router.get("/agent/devices/{device_id}/mode", response_model=DeviceModeResponse)
    async def get_device_mode(device_id: str):
        """获取设备默认模式"""
        service = get_device_mode_service()
        resolved = service.resolve_mode(device_id=device_id, request_mode=None)
        return DeviceModeResponse(
            device_id=device_id,
            mode=resolved.mode.value,
            source=resolved.source,
        )

    @router.put("/agent/devices/{device_id}/mode", response_model=DeviceModeResponse)
    async def set_device_mode(device_id: str, request: DeviceModeRequest):
        """设置设备默认模式"""
        service = get_device_mode_service()
        try:
            mode = service.set_device_mode(device_id, request.mode)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        return DeviceModeResponse(
            device_id=device_id,
            mode=mode.value,
            source="device",
        )

    @router.get("/agent/devices/{device_id}/config", response_model=DeviceConfigResponse)
    async def get_device_config(device_id: str):
        """获取设备配置"""
        config = get_device_config_service().get_config(device_id)
        return DeviceConfigResponse(**config.__dict__)

    @router.put("/agent/devices/{device_id}/config", response_model=DeviceConfigResponse)
    async def set_device_config(device_id: str, request: DeviceConfigRequest):
        """设置设备配置"""
        config = get_device_config_service().update_config(
            device_id=device_id,
            volume=request.volume,
            light_profile=request.light_profile,
            wake_method=request.wake_method,
            usage_start=request.usage_start,
            usage_end=request.usage_end,
            content_policy=request.content_policy,
        )
        return DeviceConfigResponse(**config.__dict__)

    return router
