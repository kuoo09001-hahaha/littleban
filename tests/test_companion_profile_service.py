import asyncio
import tempfile
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class CompanionProfileServiceTest(unittest.TestCase):
    def test_personal_info_tool_uses_persistent_profile_service(self):
        from agents.companion_agent import CompanionAgent
        from services.profile_service import ProfileService
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "agent.db"
            first_agent = CompanionAgent(
                tools=[],
                memory=None,
                profile_service=ProfileService(SQLiteStore(db_path)),
            )

            asyncio.run(first_agent._execute_add_personal_info_tool({
                "person_name": "爷爷",
                "age": "75",
                "gender": "男",
                "health_condition": "膝盖不好",
            }))

            second_agent = CompanionAgent(
                tools=[],
                memory=None,
                profile_service=ProfileService(SQLiteStore(db_path)),
            )
            result = asyncio.run(second_agent._execute_recall_personal_info_tool({
                "person_name": "爷爷",
            }))

            self.assertIn("爷爷的个人信息", result)
            self.assertIn("75岁", result)
            self.assertIn("膝盖不好", result)


if __name__ == "__main__":
    unittest.main()
