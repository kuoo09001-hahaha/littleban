import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class RecurringReminderTest(unittest.TestCase):
    def test_daily_completion_keeps_reminder_for_future_days(self):
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            reminder = store.create_reminder("web-1", "吃药", "12:00", "daily")
            self.assertTrue(store.complete_reminder(reminder["reminder_id"]))
            stored = store.list_reminders("web-1")[0]
            self.assertIsNone(stored["completed_at"])
            self.assertEqual(stored["last_completed_date"], date.today().isoformat())

    def test_daily_correction_updates_single_existing_reminder_without_duplication(self):
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            store.create_reminder("web-1", "吃药", "08:00", "daily")
            reminder, updated = store.upsert_reminder("web-1", "提醒", "12:00", "daily")
            self.assertTrue(updated)
            self.assertEqual(reminder["title"], "吃药")
            self.assertEqual(reminder["reminder_time"], "12:00")
            self.assertEqual(len(store.list_reminders("web-1")), 1)


if __name__ == "__main__":
    unittest.main()
