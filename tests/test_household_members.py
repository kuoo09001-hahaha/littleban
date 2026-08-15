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

    def test_family_graph_derives_reverse_and_cross_generation_relationships(self):
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            for name, age in (("小明", 12), ("王刚", 42), ("王芳", 40), ("王秀芬", 68), ("王建国", 70)):
                store.add_household_member("family-a", name, age=age)
            store.set_family_relationship("family-a", "小明", "王刚", "爸爸")
            store.set_family_relationship("family-a", "小明", "王芳", "妈妈")
            store.set_family_relationship("family-a", "小明", "王秀芬", "奶奶")
            store.set_family_relationship("family-a", "小明", "王建国", "爷爷")

            self.assertEqual(store.find_related_member("family-a", "王刚", "妈妈")["member_name"], "王秀芬")
            self.assertEqual(store.find_related_member("family-a", "王刚", "爸爸")["member_name"], "王建国")
            self.assertEqual(store.find_member_by_spoken_relation("family-a", "王秀芬", "儿子")["member_name"], "王刚")
            # 小明未提供性别时，图中保存中性的“孙辈/孩子”，但用户以
            # 单数“孙子/儿子”查询且候选唯一时仍能安全解析。
            self.assertEqual(store.find_member_by_spoken_relation("family-a", "王秀芬", "孙子")["member_name"], "小明")
            self.assertEqual(store.find_member_by_spoken_relation("family-a", "王芳", "儿子")["member_name"], "小明")
            self.assertIsNone(store.find_related_member("family-a", "王刚", "老伴"))

            grandma_edges = store.list_member_relationships("family-a", "王秀芬")
            self.assertTrue(any(item["edge_type"] == "derived" and item["evidence"] for item in grandma_edges))

    def test_family_graph_rebuild_removes_stale_derived_edges(self):
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            for name in ("小明", "王刚", "王秀芬", "李秀兰"):
                store.add_household_member("family-a", name)
            store.set_family_relationship("family-a", "小明", "王刚", "爸爸")
            store.set_family_relationship("family-a", "小明", "王秀芬", "奶奶")
            self.assertEqual(store.find_related_member("family-a", "王刚", "妈妈")["member_name"], "王秀芬")

            store.set_family_relationship("family-a", "小明", "李秀兰", "奶奶")
            self.assertEqual(store.find_related_member("family-a", "王刚", "妈妈")["member_name"], "李秀兰")
            self.assertFalse(any(
                item["target_name"] == "王秀芬" and item["relation"] == "妈妈"
                for item in store.list_member_relationships("family-a", "王刚")
            ))

    def test_neutral_relation_does_not_guess_when_multiple_candidates_exist(self):
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            for name in ("王芳", "小明", "小红"):
                store.add_household_member("family-a", name)
            store.set_family_relationship("family-a", "小明", "王芳", "妈妈")
            store.set_family_relationship("family-a", "小红", "王芳", "妈妈")
            self.assertIsNone(store.find_member_by_spoken_relation("family-a", "王芳", "儿子"))

    def test_switched_member_context_contains_the_whole_family_graph(self):
        from services.family_fact_service import format_persistent_context
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            for name in ("小明", "王刚", "王芳", "王秀芬"):
                store.add_household_member("family-a", name)
            store.set_family_relationship("family-a", "小明", "王刚", "爸爸")
            store.set_family_relationship("family-a", "小明", "王芳", "妈妈")
            store.set_family_relationship("family-a", "小明", "王秀芬", "奶奶")

            context = format_persistent_context(
                store.get_household_member("family-a", "王芳"),
                store.list_member_relationships("family-a", "王芳"),
                [],
                store.list_family_relationship_graph("family-a"),
            )

            self.assertIn("家庭关系图", context)
            self.assertIn("小明的爸爸是王刚（明确）", context)
            self.assertIn("王刚的妈妈是王秀芬（安全推导）", context)
            self.assertNotIn("王刚的老伴是王芳", context)


if __name__ == "__main__":
    unittest.main()
