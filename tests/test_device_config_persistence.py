import tempfile
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class DeviceConfigPersistenceTest(unittest.TestCase):
    def test_device_config_survives_service_recreation(self):
        from services.device_config_service import DeviceConfigService
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "agent.db"

            first_service = DeviceConfigService(SQLiteStore(db_path))
            first_service.update_config(
                device_id="toy-001",
                volume=55,
                light_profile="soft",
                wake_method="tap_head",
                usage_start="08:00",
                usage_end="21:30",
                content_policy="需要家长知情后再处理定位和联系人信息",
            )

            second_service = DeviceConfigService(SQLiteStore(db_path))
            config = second_service.get_config("toy-001")

            self.assertEqual(config.device_id, "toy-001")
            self.assertEqual(config.volume, 55)
            self.assertEqual(config.light_profile, "soft")
            self.assertEqual(config.wake_method, "tap_head")
            self.assertEqual(config.usage_start, "08:00")
            self.assertEqual(config.usage_end, "21:30")
            self.assertEqual(config.content_policy, "需要家长知情后再处理定位和联系人信息")


if __name__ == "__main__":
    unittest.main()

