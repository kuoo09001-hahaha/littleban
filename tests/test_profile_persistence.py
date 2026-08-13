import tempfile
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class ProfilePersistenceTest(unittest.TestCase):
    def test_family_member_survives_service_recreation(self):
        from services.profile_service import ProfileService
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "agent.db"

            first_service = ProfileService(SQLiteStore(db_path))
            first_service.upsert_family_member(
                person_name="小明",
                age="8",
                gender="男",
                health_condition="花粉过敏",
            )

            second_service = ProfileService(SQLiteStore(db_path))
            member = second_service.get_family_member("小明")

            self.assertEqual(
                member,
                {
                    "person_name": "小明",
                    "age": "8",
                    "gender": "男",
                    "health_condition": "花粉过敏",
                },
            )

    def test_lists_family_members_from_sqlite(self):
        from services.profile_service import ProfileService
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "agent.db"
            service = ProfileService(SQLiteStore(db_path))

            service.upsert_family_member("奶奶", "72", "女", "血压偏高")
            service.upsert_family_member("小明", "8", "男", "花粉过敏")

            self.assertEqual(
                [member["person_name"] for member in service.list_family_members()],
                ["奶奶", "小明"],
            )


if __name__ == "__main__":
    unittest.main()
