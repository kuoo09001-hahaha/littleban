import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class HarnessRunnerTest(unittest.TestCase):
    def test_retries_transport_failure_and_records_step(self):
        from harness import HarnessRunner

        calls = []

        def flaky_post(url, payload, timeout):
            calls.append(payload)
            if len(calls) == 1:
                raise RuntimeError("temporary connection failure")
            return {"response": "好的", "tool_used": False, "metadata": {"trace_id": "trace-1"}}

        runner = HarnessRunner(flaky_post, retries=1)
        response, step = runner.run_turn("http://agent/chat", {"session_id": "s-1"}, timeout=1)
        self.assertEqual(response["response"], "好的")
        self.assertEqual(step["attempts"], 2)
        self.assertTrue(step["success"])
        self.assertEqual(step["trace_id"], "trace-1")


if __name__ == "__main__":
    unittest.main()
