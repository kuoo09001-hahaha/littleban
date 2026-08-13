"""Regression scenario: family members can set reminders for one another."""

import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class FamilyReminderScenarioTest(unittest.TestCase):
    """Models the same separate pages/sessions that the web UI uses."""

    def test_xiaoming_and_wangxiufen_can_set_cross_member_reminders(self):
        from services.family_fact_service import extract_named_age, extract_named_relationship
        from services.health_memory_service import inverse_relation
        from services.reminder_slot_service import extract_reminder_date, extract_reminder_task, extract_time
        from storage.sqlite_store import SQLiteStore

        xiaoming_message = "我奶奶是王秀芬今年68岁，你帮我提醒她明天中午12点到知春路地铁站等我。"
        wangxiufen_message = "我老伴是王刚，你帮我提醒他我明天中午12点去找我们孙子小明。"
        tell_spouse_message = "告诉我老伴王刚明天中午12点我要去找我们孙子了。"
        expected_date = (date.today() + timedelta(days=1)).isoformat()

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            family_id = "scenario-family"
            store.add_household_member(family_id, "小明", age=12)

            # Turn 1: 小明 establishes his grandmother and creates a reminder
            # in her own web session, rather than in his own session.
            relation, grandmother = extract_named_relationship(xiaoming_message)
            name, age = extract_named_age(xiaoming_message)
            self.assertEqual((relation, grandmother, name, age), ("奶奶", "王秀芬", "王秀芬", 68))
            store.add_household_member(family_id, grandmother, age=age)
            store.set_family_relationship(family_id, "小明", grandmother, relation)
            store.set_family_relationship(family_id, grandmother, "小明", inverse_relation("小明", relation) or "孙子")
            grandmother_session = store.member_session_id(family_id, grandmother)
            store.create_reminder(
                grandmother_session,
                extract_reminder_task(xiaoming_message, "小明"),
                extract_time(xiaoming_message),
                "once",
                extract_reminder_date(xiaoming_message),
                created_by="小明",
            )
            self.assertEqual(store.list_reminders(store.member_session_id(family_id, "小明")), [])
            grandmother_reminder = store.list_reminders(grandmother_session)[0]
            self.assertEqual(grandmother_reminder["reminder_time"], "12:00")
            self.assertEqual(grandmother_reminder["reminder_date"], expected_date)
            self.assertEqual(grandmother_reminder["title"], "到知春路地铁站等小明")
            self.assertEqual(grandmother_reminder["created_by"], "小明")

            # Turn 2: 王秀芬 establishes her spouse and creates a reminder in
            # 王刚's page/session. “他” resolves to the just-mentioned spouse.
            relation, spouse = extract_named_relationship(wangxiufen_message)
            self.assertEqual((relation, spouse), ("老伴", "王刚"))
            store.add_household_member(family_id, spouse)
            store.set_family_relationship(family_id, grandmother, spouse, relation)
            store.set_family_relationship(family_id, spouse, grandmother, inverse_relation(grandmother, relation) or "老伴")
            spouse_session = store.member_session_id(family_id, spouse)
            store.create_reminder(
                spouse_session,
                extract_reminder_task(wangxiufen_message, grandmother),
                extract_time(wangxiufen_message),
                "once",
                extract_reminder_date(wangxiufen_message),
                created_by=grandmother,
            )
            self.assertEqual(store.list_reminders(grandmother_session)[0]["title"], "到知春路地铁站等小明")
            spouse_reminder = store.list_reminders(spouse_session)[0]
            self.assertEqual(spouse_reminder["title"], "王秀芬要去找我们孙子小明")
            self.assertEqual(spouse_reminder["created_by"], "王秀芬")
            self.assertEqual(spouse_reminder["reminder_date"], expected_date)
            self.assertEqual(extract_reminder_task(tell_spouse_message, "秀英"), "秀英要去找我们孙子")


if __name__ == "__main__":
    unittest.main()
