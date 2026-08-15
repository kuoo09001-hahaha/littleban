import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class AgentActionServiceTest(unittest.TestCase):
    def setUp(self):
        from services.agent_action_service import AgentActionService
        from storage.sqlite_store import SQLiteStore

        self.temp = tempfile.TemporaryDirectory()
        self.store = SQLiteStore(Path(self.temp.name) / "agent.db")
        self.service = AgentActionService(self.store)
        self.family_id = "family-tools"
        self.store.add_household_member(self.family_id, "小明", age=12)
        self.store.add_household_member(self.family_id, "王秀芬", age=68)
        self.store.set_family_relationship(self.family_id, "小明", "王秀芬", "奶奶")
        self.context = {
            "family_id": self.family_id,
            "actor_name": "小明",
            "session_id": self.store.member_session_id(self.family_id, "小明"),
            "input_text": "明天20:12提醒我奶奶吃降压药",
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_function_tool_sets_recipient_reminder_idempotently(self):
        args = {
            "recipient_ref": "奶奶", "canonical_action": "服用",
            "canonical_object": "降压药", "task": "吃降压药",
            "date": "2026-08-16", "time": "20:12", "repeat": "once",
        }
        first = self.service.execute("set_reminder", args, self.context)
        second = self.service.execute("set_reminder", args, self.context)
        self.assertEqual(first["reminder"]["reminder_id"], second["reminder"]["reminder_id"])
        self.assertEqual(first["alarm_control"]["recipient_name"], "王秀芬")
        self.assertEqual(len(self.store.list_reminders(self.store.member_session_id(self.family_id, "王秀芬"))), 1)

    def test_generic_reminder_title_is_not_repeated_in_confirmation(self):
        from datetime import date
        from services.reminder_slot_service import format_reminder_date

        target_date = date.today().isoformat()
        result = self.service.execute(
            "set_reminder",
            {
                "recipient_ref": "self", "canonical_action": "提醒",
                "canonical_object": "", "task": "提醒",
                "date": target_date, "time": "21:00", "repeat": "once",
            },
            {**self.context, "input_text": "帮我设置一个提醒"},
        )

        self.assertEqual(
            result["direct_response"],
            f"好的，已为小明设置{format_reminder_date(target_date)}21:00的提醒。",
        )
        self.assertNotIn("提醒提醒", result["direct_response"])

    def test_specific_reminder_uses_colon_before_task(self):
        from datetime import date
        from services.reminder_slot_service import format_reminder_date

        target_date = date.today().isoformat()
        result = self.service.execute(
            "set_reminder",
            {
                "recipient_ref": "奶奶", "canonical_action": "服用",
                "canonical_object": "降压药", "task": "吃降压药",
                "date": target_date, "time": "21:05", "repeat": "once",
            },
            {**self.context, "input_text": "提醒奶奶吃降压药"},
        )

        self.assertEqual(
            result["direct_response"],
            f"好的，已为王秀芬设置{format_reminder_date(target_date)}21:05的提醒：服用降压药。",
        )

    def test_relationship_query_never_writes_a_fake_member(self):
        result = self.service.execute("query_family_relationship", {"relation": "奶奶"}, self.context)
        self.assertIn("王秀芬", result["direct_response"])
        self.assertIsNone(self.store.get_household_member(self.family_id, "谁吗"))

    def test_switched_member_can_query_relationship_derived_from_family_graph(self):
        self.store.add_household_member(self.family_id, "王刚", age=42)
        self.store.set_family_relationship(self.family_id, "小明", "王刚", "爸爸")
        wanggang_context = {
            **self.context,
            "actor_name": "王刚",
            "session_id": self.store.member_session_id(self.family_id, "王刚"),
            "input_text": "你知道我妈妈是谁吗",
        }

        result = self.service.execute("query_family_relationship", {"relation": "妈妈"}, wanggang_context)

        self.assertIn("王秀芬", result["direct_response"])

    def test_same_turn_relationship_write_runs_before_dependent_profile_query(self):
        import asyncio
        from agents.companion_agent import CompanionAgent

        class TestAgent(CompanionAgent):
            async def _get_tool_final_response(self, original_messages, tool_message, tool_results, session_id):
                return "已经处理完成。"

        agent = TestAgent([], memory=None, action_service=self.service)
        message = {
            "tool_calls": [
                {
                    "id": "query-first",
                    "function": {"name": "query_member_profile", "arguments": '{"subject_ref":"爸爸"}'},
                },
                {
                    "id": "save-second",
                    "function": {
                        "name": "save_family_relationship",
                        "arguments": '{"relation":"爸爸","target_name":"王刚","target_age":52}',
                    },
                },
            ]
        }
        context = {**self.context, "input_text": "我爸爸是王刚，你知道他几岁吗"}

        result = asyncio.run(agent._handle_tool_calls(message, context["session_id"], [], context))

        self.assertEqual([item["tool_name"] for item in result["tool_results"]], [
            "save_family_relationship", "query_member_profile",
        ])
        self.assertIn("52岁", result["tool_results"][1]["result"])

    def test_health_record_and_query_share_family_context(self):
        grandma_context = {**self.context, "actor_name": "王秀芬", "input_text": "我有点头疼、头晕"}
        self.service.execute(
            "record_health_event", {"subject_ref": "self", "symptoms": ["头疼", "头晕"]}, grandma_context
        )
        result = self.service.execute("query_health_events", {"subject_ref": "奶奶", "days": 7}, self.context)
        self.assertIn("头疼", result["direct_response"])
        self.assertIn("头晕", result["direct_response"])

    def test_preference_change_replaces_the_opposite_state(self):
        grandma = {**self.context, "actor_name": "王秀芬", "input_text": "我一直爱吃鱼"}
        self.service.execute(
            "save_preference",
            {"subject_ref": "self", "category": "food", "polarity": "like", "item": "鱼"},
            grandma,
        )
        grandma["input_text"] = "我现在不爱吃鱼了"
        self.service.execute(
            "save_preference",
            {"subject_ref": "self", "category": "food", "polarity": "dislike", "item": "鱼"},
            grandma,
        )

        result = self.service.execute("query_preferences", {"subject_ref": "奶奶"}, self.context)
        self.assertIn("不喜欢鱼", result["direct_response"])
        self.assertNotIn("；饮食方面喜欢鱼", result["direct_response"])
        preference_facts = [
            item for item in self.store.list_family_facts(self.family_id, "王秀芬")
            if item["fact_key"] == "偏好:food" and item["fact_value"].endswith(":鱼")
        ]
        self.assertEqual([item["fact_value"] for item in preference_facts], ["dislike:鱼"])

    def test_age_and_long_term_health_support_updates(self):
        grandma = {**self.context, "actor_name": "王秀芬", "input_text": "我今年69岁，有高血压"}
        first = self.service.execute(
            "update_member_profile",
            {
                "subject_ref": "self", "age": 69,
                "health_changes": [{"condition": "高血压", "status": "active"}],
            },
            grandma,
        )
        self.assertIn("年龄更新为69岁", first["direct_response"])
        self.assertEqual(self.store.get_household_member(self.family_id, "王秀芬")["age"], 69)

        grandma["input_text"] = "医生说高血压已经恢复了"
        second = self.service.execute(
            "update_member_profile",
            {
                "subject_ref": "self",
                "health_changes": [{"condition": "高血压", "status": "resolved"}],
            },
            grandma,
        )
        self.assertIn("标记为已解除", second["direct_response"])
        conditions = [
            item for item in self.store.list_family_facts(self.family_id, "王秀芬")
            if item["fact_key"] == "长期健康情况"
        ]
        self.assertEqual(conditions, [])

        profile = self.service.execute("query_member_profile", {"subject_ref": "奶奶"}, self.context)
        self.assertIn("69岁", profile["direct_response"])
        self.assertNotIn("高血压", profile["direct_response"])

    def test_recent_symptom_recovery_keeps_history(self):
        grandma = {**self.context, "actor_name": "王秀芬", "input_text": "我头疼"}
        self.service.execute("record_health_event", {"subject_ref": "self", "symptoms": ["头疼"]}, grandma)
        grandma["input_text"] = "我的头疼已经好了"
        resolved = self.service.execute(
            "resolve_health_event", {"subject_ref": "self", "symptoms": ["头疼"]}, grandma
        )
        self.assertEqual(resolved["resolved_health_events"], 1)
        queried = self.service.execute("query_health_events", {"subject_ref": "奶奶", "days": 7}, self.context)
        self.assertIn("头疼", queried["direct_response"])
        self.assertIn("已经好了", queried["direct_response"])

    def test_main_llm_sees_real_tools_not_nested_intent_analyzer(self):
        from agents.companion_agent import CompanionAgent

        agent = CompanionAgent([], memory=object(), action_service=self.service)
        tool_names = {item["function"]["name"] for item in agent._build_tools_description()}
        self.assertIn("set_reminder", tool_names)
        self.assertIn("save_family_relationship", tool_names)
        self.assertIn("query_health_events", tool_names)
        self.assertIn("save_preference", tool_names)
        self.assertIn("query_preferences", tool_names)
        self.assertIn("update_member_profile", tool_names)
        self.assertIn("resolve_health_event", tool_names)
        self.assertIn("query_member_profile", tool_names)
        self.assertNotIn("add_personal_info", tool_names)
        self.assertNotIn("recall_personal_info", tool_names)
        self.assertNotIn("intent_analyzer", tool_names)


if __name__ == "__main__":
    unittest.main()
