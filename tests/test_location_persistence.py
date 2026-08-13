import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class LocationPersistenceTest(unittest.TestCase):
    def test_stores_location_per_session(self):
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            store.set_session_location("web-1", 39.9, 116.4, "北京市朝阳区")
            self.assertEqual(store.get_session_location("web-1")["location_name"], "北京市朝阳区")
            self.assertIsNone(store.get_session_location("other"))


if __name__ == "__main__":
    unittest.main()
