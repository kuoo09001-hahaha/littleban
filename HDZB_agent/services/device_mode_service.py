"""In-memory device mode configuration service."""

from dataclasses import dataclass
from typing import Dict, Optional

from domain.modes import ModeType, parse_mode


@dataclass(frozen=True)
class ResolvedMode:
    mode: ModeType
    source: str


class DeviceModeService:
    """Store and resolve the companion mode for local prototype devices."""

    def __init__(self, default_mode: ModeType = ModeType.ELDER, store=None):
        self.default_mode = default_mode
        self.store = store
        self._device_modes: Dict[str, ModeType] = {}

    def set_device_mode(self, device_id: str, mode: str | ModeType) -> ModeType:
        parsed_mode = parse_mode(mode)
        if self.store:
            self.store.set_device_mode(device_id, parsed_mode.value)
        else:
            self._device_modes[device_id] = parsed_mode
        return parsed_mode

    def get_device_mode(self, device_id: str) -> Optional[ModeType]:
        if self.store:
            stored_mode = self.store.get_device_mode(device_id)
            if stored_mode is None:
                return None
            return parse_mode(stored_mode)

        return self._device_modes.get(device_id)

    def resolve_mode(self, device_id: Optional[str], request_mode: Optional[str | ModeType]) -> ResolvedMode:
        if request_mode:
            return ResolvedMode(mode=parse_mode(request_mode), source="request")

        if device_id:
            device_mode = self.get_device_mode(device_id)
            if device_mode:
                return ResolvedMode(mode=device_mode, source="device")

        return ResolvedMode(mode=self.default_mode, source="default")
