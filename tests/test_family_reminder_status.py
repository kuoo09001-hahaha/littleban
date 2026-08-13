"""Regression tests for sender-scoped family reminder completion checks."""

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class FamilyReminderStatusTest(unittest.TestCase):
    def test_sender_can_check_recipient_completion_but_other_sender_cannot(self):
        from services.reminder_slot_service import format_reminder_completion_status
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            family_id, today = "family-status", date.today().isoformat()
            recipient_session = store.member_session_id(family_id, "王秀芬")
            reminder = store.create_reminder(recipient_session, "吃药", "12:00", "daily", today, created_by="小明")
            self.assertTrue(store.complete_reminder(reminder["reminder_id"]))
            own = store.find_reminder_status_for_creator(recipient_session, "小明", today, "吃药")
            self.assertIn("已经完成了", format_reminder_completion_status("王秀芬", own, today))
            self.assertEqual(store.find_reminder_status_for_creator(recipient_session, "王刚", today, "吃药"), [])

    def test_unfinished_one_time_task_reports_not_completed(self):
        from services.reminder_slot_service import format_reminder_completion_status
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            today = date.today().isoformat()
            recipient_session = store.member_session_id("family-status", "王刚")
            store.create_reminder(recipient_session, "秀英要去找我们孙子", "12:00", "once", today, created_by="秀英")
            pending = store.find_reminder_status_for_creator(recipient_session, "秀英", today)
            self.assertIn("还没有完成", format_reminder_completion_status("王刚", pending, today))


if __name__ == "__main__":
    unittest.main()
