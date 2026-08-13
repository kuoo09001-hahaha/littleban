import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class AgentModesTest(unittest.TestCase):
    def test_resolves_request_mode_first(self):
        from domain.modes import ModeType
        from services.device_mode_service import DeviceModeService

        service = DeviceModeService(default_mode=ModeType.ELDER)
        service.set_device_mode("device-1", ModeType.ELDER)

        resolved = service.resolve_mode(device_id="device-1", request_mode="child")

        self.assertEqual(resolved.mode, ModeType.CHILD)
        self.assertEqual(resolved.source, "request")

    def test_resolves_device_mode_second(self):
        from domain.modes import ModeType
        from services.device_mode_service import DeviceModeService

        service = DeviceModeService(default_mode=ModeType.ELDER)
        service.set_device_mode("device-1", ModeType.CHILD)

        resolved = service.resolve_mode(device_id="device-1", request_mode=None)

        self.assertEqual(resolved.mode, ModeType.CHILD)
        self.assertEqual(resolved.source, "device")

    def test_defaults_to_elder(self):
        from domain.modes import ModeType
        from services.device_mode_service import DeviceModeService

        service = DeviceModeService(default_mode=ModeType.ELDER)

        resolved = service.resolve_mode(device_id="unknown-device", request_mode=None)

        self.assertEqual(resolved.mode, ModeType.ELDER)
        self.assertEqual(resolved.source, "default")

    def test_rejects_invalid_mode(self):
        from services.device_mode_service import DeviceModeService

        service = DeviceModeService()

        with self.assertRaises(ValueError):
            service.resolve_mode(device_id="device-1", request_mode="teen")


if __name__ == "__main__":
    unittest.main()
