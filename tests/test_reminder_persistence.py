import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class ReminderPersistenceTest(unittest.TestCase):
    def test_all_reminder_types_are_idempotent_for_the_same_event(self):
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            for repeat_rule, reminder_date in (("once", "2026-08-16"), ("daily", "2026-08-15"), ("weekdays", "2026-08-15")):
                first, first_updated = store.upsert_reminder(
                    "grandma-session", "吃药", "20:12", repeat_rule, reminder_date, "小明"
                )
                second, second_updated = store.upsert_reminder(
                    "grandma-session", "吃药", "20:12", repeat_rule, reminder_date, "小明"
                )
                self.assertFalse(first_updated)
                self.assertTrue(second_updated)
                self.assertEqual(first["reminder_id"], second["reminder_id"])
            self.assertEqual(len(store.list_reminders("grandma-session")), 3)

    def test_different_date_or_time_is_a_different_event(self):
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            store.upsert_reminder("s", "吃药", "20:12", "once", "2026-08-16", "小明")
            store.upsert_reminder("s", "吃药", "20:13", "once", "2026-08-16", "小明")
            store.upsert_reminder("s", "吃药", "20:12", "once", "2026-08-17", "小明")
            self.assertEqual(len(store.list_reminders("s")), 3)

    def test_persists_and_completes_reminder(self):
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            reminder = store.create_reminder("web-1", "一次性复诊提醒", "12:00", "once")
            self.assertEqual(store.list_reminders("web-1")[0]["title"], "一次性复诊提醒")
            self.assertTrue(store.complete_reminder(reminder["reminder_id"]))
            self.assertEqual(store.list_reminders("web-1"), [])

    def test_deletes_named_reminder_without_affecting_other_task(self):
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            store.create_reminder("web-1", "吃药", "08:00", "daily")
            store.create_reminder("web-1", "复诊", "10:00", "daily")
            self.assertEqual(store.delete_matching_reminders("web-1", "吃药"), 1)
            self.assertEqual([item["title"] for item in store.list_reminders("web-1")], ["复诊"])

    def test_family_member_reminder_is_stored_with_the_recipient(self):
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            recipient_session = store.member_session_id("family-a", "王秀芬")
            store.create_reminder(
                recipient_session, "吃饭", "12:00", "once", "2026-08-13", created_by="小明"
            )
            reminders = store.find_reminders_for_recall(recipient_session, "吃饭", "2026-08-13")
            self.assertEqual(len(reminders), 1)
            self.assertEqual(reminders[0]["created_by"], "小明")
            self.assertEqual(store.list_reminders(store.member_session_id("family-a", "小明")), [])

    def test_spoken_grandparent_resolves_to_their_private_reminder_session(self):
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            store.add_household_member("family-a", "王秀芬", age=70)
            store.add_household_member("family-a", "小明", age=12)
            store.set_family_relationship("family-a", "王秀芬", "小明", "孙子")
            recipient = store.find_member_by_spoken_relation("family-a", "小明", "奶奶")
            target_session = store.member_session_id("family-a", recipient["member_name"])
            store.create_reminder(target_session, "吃饭", "12:00", "once", "2026-08-13", "小明")
            self.assertEqual(store.list_reminders(target_session)[0]["created_by"], "小明")


if __name__ == "__main__":
    unittest.main()
