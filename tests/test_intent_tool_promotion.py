import json
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class IntentToolPromotionTest(unittest.TestCase):
    def test_fallback_llm_alarm_becomes_executable_command(self):
        from agents.companion_agent import CompanionAgent

        intent = {
            "intent_type": "SET_ALARM",
            "is_system_command": True,
            "alarm_info": {
                "display_time": "10:00",
                "date_value": "20260816",
                "name": "出门",
                "repeat_desc": "once",
            },
        }
        result = CompanionAgent._promote_intent_tool_result(
            [{"tool_name": "intent_analyzer", "result": json.dumps(intent, ensure_ascii=False)}],
            "xiaoming-session",
        )
        self.assertEqual(result["command_type"], "SET_ALARM")
        self.assertEqual(result["alarm_control"]["action"], "set")

    def test_non_alarm_tool_result_is_not_promoted(self):
        from agents.companion_agent import CompanionAgent

        result = CompanionAgent._promote_intent_tool_result(
            [{"tool_name": "intent_analyzer", "result": '{"intent_type":"NONE","is_system_command":false}'}],
            "session",
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
