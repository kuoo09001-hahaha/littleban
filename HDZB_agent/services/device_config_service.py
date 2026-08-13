"""Persistent device configuration service."""

from domain.device_config import DeviceConfig
from storage.sqlite_store import SQLiteStore


class DeviceConfigService:
    """Manage hardware-facing device configuration."""

    def __init__(self, store: SQLiteStore):
        self.store = store

    def get_config(self, device_id: str) -> DeviceConfig:
        stored = self.store.get_device_config(device_id)
        if stored is None:
            return DeviceConfig(device_id=device_id)
        return DeviceConfig(**stored)

    def update_config(
        self,
        device_id: str,
        volume: int,
        light_profile: str,
        wake_method: str,
        usage_start: str,
        usage_end: str,
        content_policy: str,
    ) -> DeviceConfig:
        config = DeviceConfig(
            device_id=device_id,
            volume=volume,
            light_profile=light_profile,
            wake_method=wake_method,
            usage_start=usage_start,
            usage_end=usage_end,
            content_policy=content_policy,
        )
        self.store.upsert_device_config(config)
        return config

