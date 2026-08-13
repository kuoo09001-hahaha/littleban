import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class HouseholdMembersTest(unittest.TestCase):
    def test_members_are_scoped_to_one_family(self):
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            store.add_household_member("family-a", "奶奶")
            store.add_household_member("family-a", "爸爸")
            store.add_household_member("family-b", "妈妈")
            self.assertEqual([item["member_name"] for item in store.list_household_members("family-a")], ["奶奶", "爸爸"])
            self.assertEqual([item["member_name"] for item in store.list_household_members("family-b")], ["妈妈"])

    def test_removing_member_keeps_other_family_roster_intact(self):
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            store.add_household_member("family-a", "奶奶")
            store.add_household_member("family-a", "爸爸")
            store.add_household_member("family-b", "奶奶")
            self.assertTrue(store.remove_household_member("family-a", "奶奶"))
            self.assertEqual([item["member_name"] for item in store.list_household_members("family-a")], ["爸爸"])
            self.assertEqual([item["member_name"] for item in store.list_household_members("family-b")], ["奶奶"])

    def test_relationships_are_scoped_to_the_speaking_family_member(self):
        from storage.sqlite_store import SQLiteStore
        from services.health_memory_service import inverse_relation

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            store.add_household_member("family-a", "奶奶", age=70)
            store.add_household_member("family-a", "爸爸", age=40)
            store.add_household_member("family-a", "小明", age=8)
            store.set_family_relationship("family-a", "奶奶", "小明", "孙子")
            store.set_family_relationship("family-a", "爸爸", "小明", "儿子")
            member = store.find_related_member("family-a", "奶奶", "孙子")
            self.assertEqual(member["member_name"], "小明")
            self.assertEqual(member["age"], 8)
            self.assertEqual(store.find_related_member("family-a", "爸爸", "儿子")["member_name"], "小明")
            self.assertEqual(inverse_relation("爸爸", "儿子"), "爸爸")
            store.set_family_relationship("family-a", "小明", "爸爸", inverse_relation("爸爸", "儿子"))
            self.assertEqual(store.find_related_member("family-a", "小明", "爸爸")["member_name"], "爸爸")

    def test_can_resolve_spoken_grandparent_from_reverse_relationship(self):
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            store.add_household_member("family-a", "王秀芬", age=70)
            store.add_household_member("family-a", "小明", age=12)
            store.set_family_relationship("family-a", "王秀芬", "小明", "孙子")
            self.assertEqual(
                store.find_member_by_spoken_relation("family-a", "小明", "奶奶")["member_name"], "王秀芬"
            )

    def test_repairs_a_name_with_an_accidentally_attached_age_word(self):
        from storage.sqlite_store import SQLiteStore
        from services.family_fact_service import normalize_person_name

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            store.add_household_member("family-a", "小明", age=12)
            store.add_household_member("family-a", "王秀芬", age=68)
            store.add_household_member("family-a", "王秀芬今年")
            store.set_family_relationship("family-a", "小明", "王秀芬今年", "奶奶")
            self.assertEqual(normalize_person_name("王秀芬今年"), "王秀芬")
            self.assertTrue(store.repair_relationship_target("family-a", "小明", "王秀芬今年", "王秀芬"))
            self.assertEqual(store.find_related_member("family-a", "小明", "奶奶")["member_name"], "王秀芬")

    def test_removing_member_deletes_their_private_and_family_memory(self):
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            family_id, name = "family-a", "王奶奶"
            session_id = "web-family-a-%E7%8E%8B%E5%A5%B6%E5%A5%B6"
            store.add_household_member(family_id, name, age=70)
            store.add_health_event(family_id, name, "头疼", session_id)
            store.add_activity_event(family_id, name, "买菜", session_id)
            store.create_reminder(session_id, "吃药", "08:00", "daily")
            store.set_session_location(session_id, 31.2, 121.5, "上海")
            self.assertTrue(store.remove_household_member(family_id, name))
            self.assertIsNone(store.get_household_member(family_id, name))
            self.assertEqual(store.find_recent_health_events(family_id, name, (datetime.now() - timedelta(days=1)).isoformat()), [])
            self.assertEqual(store.find_recent_activity_events(family_id, name, "买菜", (datetime.now() - timedelta(days=1)).isoformat()), [])
            self.assertEqual(store.list_reminders(session_id), [])
            self.assertIsNone(store.get_session_location(session_id))

    def test_member_can_be_found_by_exact_name_within_family(self):
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            store.add_household_member("family-a", "小明", age=8)
            self.assertEqual(store.get_household_member("family-a", "小明")["age"], 8)

    def test_persistent_facts_and_relationships_are_scoped_to_member(self):
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            store.add_household_member("family-a", "小明", age=12)
            store.add_household_member("family-a", "王刚")
            store.set_family_relationship("family-a", "小明", "王刚", "爷爷")
            store.upsert_family_fact("family-a", "小明", "喜欢", "游泳", "web-family-a-%E5%B0%8F%E6%98%8E")
            self.assertEqual(store.list_member_relationships("family-a", "小明")[0]["target_name"], "王刚")
            self.assertEqual(store.list_family_facts("family-a", "小明")[0]["fact_value"], "游泳")


if __name__ == "__main__":
    unittest.main()
