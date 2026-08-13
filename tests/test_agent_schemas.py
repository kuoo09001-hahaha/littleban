import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class AgentSchemasTest(unittest.TestCase):
    def test_agent_request_defaults_to_companion(self):
        from schemas.agent import AgentRequest

        request = AgentRequest(message="你好")

        self.assertEqual(request.message, "你好")
        self.assertIsNone(request.session_id)
        self.assertEqual(request.agent_type, "companion")
        self.assertIsNone(request.mode)

    def test_agent_request_accepts_mode(self):
        from schemas.agent import AgentRequest

        request = AgentRequest(message="讲个故事", mode="child")

        self.assertEqual(request.mode, "child")

    def test_agent_response_defaults_optional_fields(self):
        from schemas.agent import AgentResponse

        response = AgentResponse(
            response="你好",
            session_id="session-1",
            agent_type="companion",
            success=True,
        )

        self.assertFalse(response.tool_used)
        self.assertIsNone(response.tool_results)
        self.assertIsNone(response.command_type)
        self.assertIsNone(response.metadata)

    def test_weather_query_defaults_to_normal_mode(self):
        from schemas.agent import WeatherQueryRequest

        request = WeatherQueryRequest(location="上海")

        self.assertEqual(request.location, "上海")
        self.assertFalse(request.test_mode)


if __name__ == "__main__":
    unittest.main()
