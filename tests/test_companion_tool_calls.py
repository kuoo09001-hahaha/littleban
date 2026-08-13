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


if __name__ == "__main__":
    unittest.main()
