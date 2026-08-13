"""Device configuration domain model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceConfig:
    device_id: str
    volume: int = 60
    light_profile: str = "warm_soft"
    wake_method: str = "tap_head"
    usage_start: str = "07:00"
    usage_end: str = "22:00"
    content_policy: str = "遵循当前模式的默认安全策略"

