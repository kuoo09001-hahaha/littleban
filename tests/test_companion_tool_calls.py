import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class CompanionToolCallsTest(unittest.TestCase):
    def test_builds_tool_messages_with_each_call_id(self):
        from agents.companion_agent import CompanionAgent

        agent = CompanionAgent(tools=[], memory=None)
        tool_results = [
            {
                "tool_call_id": "call_weather",
                "tool_name": "get_weather",
                "arguments": {"location": "上海"},
                "result": "上海晴天",
            },
            {
                "tool_call_id": "call_location",
                "tool_name": "get_location",
                "arguments": {"query": "附近医院"},
                "result": "附近有社区医院",
            },
        ]

        messages = agent._build_tool_result_messages(tool_results)

        self.assertEqual(
            messages,
            [
                {
                    "role": "tool",
                    "content": "上海晴天",
                    "tool_call_id": "call_weather",
                },
                {
                    "role": "tool",
                    "content": "附近有社区医院",
                    "tool_call_id": "call_location",
                },
            ],
        )

    def test_handle_tool_calls_preserves_each_call_id(self):
        import asyncio

        from agents.companion_agent import CompanionAgent

        async def execute_weather(args):
            return f"{args['location']}晴天"

        async def execute_location(args):
            return f"{args['query']}：社区医院"

        class TestCompanionAgent(CompanionAgent):
            async def _get_tool_final_response(self, original_messages, tool_message, tool_results, session_id):
                return "工具执行完成"

        agent = TestCompanionAgent(tools=[], memory=None)
        agent.available_functions = {
            "get_weather": execute_weather,
            "get_location": execute_location,
        }

        message = {
            "tool_calls": [
                {
                    "id": "call_weather",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"location": "上海"}',
                    },
                },
                {
                    "id": "call_location",
                    "function": {
                        "name": "get_location",
                        "arguments": '{"query": "附近医院"}',
                    },
                },
            ]
        }

        result = asyncio.run(agent._handle_tool_calls(message, "session-1", []))

        self.assertTrue(result["tool_used"])
        self.assertEqual(
            [item["tool_call_id"] for item in result["tool_results"]],
            ["call_weather", "call_location"],
        )
        self.assertEqual(
            [item["result"] for item in result["tool_results"]],
            ["上海晴天", "附近医院：社区医院"],
        )

    def test_action_tool_result_returns_to_main_llm_and_keeps_backend_state(self):
        import asyncio

        from agents.companion_agent import CompanionAgent

        class ActionService:
            def execute(self, name, args, context):
                return {
                    "content": "提醒已真实写入数据库",
                    "direct_response": "已为王秀芬设置提醒。",
                    "command_type": "SET_ALARM",
                    "reminder_persisted": True,
                    "reminder": {"reminder_id": 7},
                }

        class TestCompanionAgent(CompanionAgent):
            async def _get_tool_final_response(self, original_messages, tool_message, tool_results, session_id):
                self.final_tool_results = tool_results
                return "记住啦，我会提醒王秀芬。"

        agent = TestCompanionAgent(tools=[], memory=None, action_service=ActionService())
        message = {
            "tool_calls": [{
                "id": "call_reminder",
                "function": {
                    "name": "set_reminder",
                    "arguments": '{"recipient_ref":"奶奶","task":"吃药","date":"2026-08-16","time":"12:00"}',
                },
            }]
        }

        result = asyncio.run(agent._handle_tool_calls(
            message,
            "session-1",
            [],
            {"family_id": "family-1", "actor_name": "小明", "input_text": "提醒奶奶吃药"},
        ))

        self.assertEqual(result["response"], "记住啦，我会提醒王秀芬。")
        self.assertEqual(agent.final_tool_results[0]["result"], "提醒已真实写入数据库")
        self.assertTrue(result["reminder_persisted"])
        self.assertEqual(result["reminder"]["reminder_id"], 7)

    def test_action_result_can_continue_to_a_dependent_tool_round(self):
        import asyncio

        from agents.companion_agent import CompanionAgent

        class ActionService:
            def execute(self, name, args, context):
                return {"content": f"已执行{name}", "direct_response": f"已执行{name}"}

        class TestCompanionAgent(CompanionAgent):
            async def _continue_tool_conversation(
                self, original_messages, tool_message, tool_results, session_id,
                tools, tool_context, remaining_tool_rounds,
            ):
                self.continued_with = tool_results
                return {
                    "success": True, "response": "王刚今年52岁。", "session_id": session_id,
                    "tool_used": True,
                    "tool_results": [{"tool_call_id": "query", "tool_name": "query_member_profile", "arguments": {}, "result": "52岁"}],
                }

        agent = TestCompanionAgent([], memory=None, action_service=ActionService())
        message = {"tool_calls": [{
            "id": "save", "function": {
                "name": "save_family_relationship",
                "arguments": '{"relation":"爸爸","target_name":"王刚"}',
            },
        }]}
        result = asyncio.run(agent._handle_tool_calls(
            message, "session-1", [], {"family_id": "f", "actor_name": "小明"},
            [{"type": "function", "function": {"name": "query_member_profile"}}], 2,
        ))

        self.assertEqual(agent.continued_with[0]["tool_name"], "save_family_relationship")
        self.assertEqual(result["response"], "王刚今年52岁。")
        self.assertEqual(len(result["tool_results"]), 2)


if __name__ == "__main__":
    unittest.main()
