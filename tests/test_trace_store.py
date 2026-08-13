import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class TraceStoreTest(unittest.TestCase):
    def test_records_tool_execution_and_filters_by_session(self):
        from observability.tracing import TraceStore

        store = TraceStore()
        trace = store.record(
            session_id="session-a",
            input_text="北京天气",
            result={
                "success": True,
                "response": "北京晴天。",
                "tool_used": True,
                "tool_results": [{
                    "tool_name": "get_weather",
                    "arguments": {"location": "北京"},
                    "result": "晴天",
                }],
            },
            total_latency_ms=12.345,
            mode="elder",
        )

        self.assertTrue(trace["trace_id"])
        self.assertEqual(trace["total_latency_ms"], 12.35)
        self.assertEqual(trace["steps"][0]["tool"], "get_weather")
        self.assertEqual(store.list(session_id="other"), [])
        self.assertEqual(store.list(session_id="session-a")[0]["trace_id"], trace["trace_id"])


if __name__ == "__main__":
    unittest.main()
