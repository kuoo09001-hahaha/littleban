import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class AgentToolAvailabilityTest(unittest.TestCase):
    def test_does_not_offer_simulated_location_as_agent_tool(self):
        from agents.companion_agent import CompanionAgent

        agent = CompanionAgent(tools=[], memory=None)
        tool_names = {tool["function"]["name"] for tool in agent._build_tools_description()}
        self.assertNotIn("get_location", tool_names)


if __name__ == "__main__":
    unittest.main()
