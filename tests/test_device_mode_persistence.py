import tempfile
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class DeviceModePersistenceTest(unittest.TestCase):
    def test_device_mode_survives_service_recreation(self):
        from domain.modes import ModeType
        from services.device_mode_service import DeviceModeService
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "agent.db"

            first_service = DeviceModeService(store=SQLiteStore(db_path))
            first_service.set_device_mode("toy-001", ModeType.CHILD)

            second_service = DeviceModeService(store=SQLiteStore(db_path))
            resolved = second_service.resolve_mode(device_id="toy-001", request_mode=None)

            self.assertEqual(resolved.mode, ModeType.CHILD)
            self.assertEqual(resolved.source, "device")


if __name__ == "__main__":
    unittest.main()
