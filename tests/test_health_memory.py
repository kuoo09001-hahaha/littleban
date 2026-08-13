import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class HealthMemoryTest(unittest.TestCase):
    def test_family_scoped_time_aware_retrieval(self):
        from storage.sqlite_store import SQLiteStore
        from services.health_memory_service import format_events

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            two_days_ago = (datetime.now() - timedelta(days=2)).isoformat()
            store.add_health_event("family-a", "奶奶", "头疼", "grandma-session", occurred_at=two_days_ago)
            events = store.find_recent_health_events("family-a", "奶奶", (datetime.now() - timedelta(days=3)).isoformat())
            self.assertEqual(len(events), 1)
            self.assertIn("头疼", format_events("奶奶", events))
            self.assertEqual(store.find_recent_health_events("family-b", "奶奶", (datetime.now() - timedelta(days=3)).isoformat()), [])

    def test_activity_is_shared_across_sessions_and_matches_relation_name(self):
        from storage.sqlite_store import SQLiteStore
        from services.health_memory_service import format_activity_events

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            store.add_activity_event("family-a", "王奶奶", "买菜", "grandma-session")
            events = store.find_recent_activity_events("family-a", "奶奶", "买菜", (datetime.now() - timedelta(days=1)).isoformat())
            self.assertEqual(len(events), 1)
            self.assertIn("去买菜", format_activity_events("奶奶", "买菜", events))
            self.assertEqual(store.find_recent_activity_events("family-b", "奶奶", "买菜", (datetime.now() - timedelta(days=1)).isoformat()), [])

    def test_activity_expires_after_four_hours_and_is_not_returned(self):
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            store.add_activity_event("family-a", "奶奶", "买菜", "grandma-session")
            with store._connect() as conn:
                conn.execute("UPDATE activity_events SET expires_at = ?", ((datetime.now() - timedelta(seconds=1)).isoformat(),))
            events = store.find_recent_activity_events("family-a", "奶奶", "买菜", (datetime.now() - timedelta(days=1)).isoformat())
            self.assertEqual(events, [])
            self.assertEqual(store.purge_expired_events()["activity_events"], 1)

    def test_memory_policy_normalizes_synonyms_and_filters_negated_activity(self):
        from services.health_memory_service import extract_activity, extract_symptom

        self.assertEqual(extract_symptom("我脑袋有点疼"), "头疼")
        self.assertEqual(extract_symptom("我好像有点发热"), "发烧")
        self.assertEqual(extract_activity("我出门采购点菜"), "买菜")
        self.assertEqual(extract_activity("我去泳池游个泳"), "游泳")
        self.assertEqual(extract_activity("我今天没去买菜"), None)
        self.assertEqual(extract_activity("孩子没有去学校"), None)

    def test_latest_health_event_has_stable_tiebreaker(self):
        from storage.sqlite_store import SQLiteStore

        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteStore(Path(directory) / "agent.db")
            timestamp = datetime.now().isoformat()
            store.add_health_event("family-a", "奶奶", "头疼", "s-1", occurred_at=timestamp)
            store.add_health_event("family-a", "奶奶", "头晕", "s-2", occurred_at=timestamp)
            events = store.find_recent_health_events("family-a", "奶奶", (datetime.now() - timedelta(days=1)).isoformat())
            self.assertEqual(events[0]["symptom"], "头晕")

if __name__ == "__main__":
    unittest.main()
