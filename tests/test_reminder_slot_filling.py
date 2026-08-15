import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class ReminderSlotFillingTest(unittest.TestCase):
    def test_extracts_follow_up_time(self):
        from services.reminder_slot_service import extract_reminder_date, extract_time
        self.assertEqual(extract_time("每天早上8点"), "08:00")
        self.assertEqual(extract_time("下午3点半"), "15:00")
        self.assertEqual(extract_time("明天早上八点啊"), "08:00")
        self.assertEqual(extract_reminder_date("明早八点上课"), (date.today() + timedelta(days=1)).isoformat())

    def test_extracts_colon_time_adjacent_to_chinese_text(self):
        from services.reminder_slot_service import extract_time
        from tools.intent_tools import IntentAnalyzerTool

        text = "帮我奶奶设置今天晚上20:10吃药的提醒"
        self.assertEqual(extract_time(text), "20:10")
        intent = IntentAnalyzerTool()._extract_local_reminder_intent(text)
        self.assertEqual(intent["alarm_info"]["display_time"], "20:10")
        self.assertFalse(intent["alarm_info"]["needs_time"])

    def test_pending_reminder_survives_store_recreation(self):
        from storage.sqlite_store import SQLiteStore
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agent.db"
            target_date = (date.today() + timedelta(days=1)).isoformat()
            SQLiteStore(path).set_pending_reminder("session-1", "吃药", "daily", target_date, "recipient-session", "小明")
            pending = SQLiteStore(path).get_pending_reminder("session-1")
            self.assertEqual(pending["title"], "吃药")
            self.assertEqual(pending["repeat_rule"], "daily")
            self.assertEqual(pending["reminder_date"], target_date)
            self.assertEqual(pending["recipient_session_id"], "recipient-session")
            self.assertEqual(pending["created_by"], "小明")


if __name__ == "__main__":
    unittest.main()
