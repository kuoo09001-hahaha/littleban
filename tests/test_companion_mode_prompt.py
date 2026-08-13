import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class CompanionModePromptTest(unittest.TestCase):
    def test_child_mode_prompt_contains_child_profile_rules(self):
        from agents.companion_agent import CompanionAgent
        from domain.modes import get_mode_profile

        agent = CompanionAgent(tools=[], memory=None)

        prompt = agent._build_system_prompt(get_mode_profile("child"))

        self.assertIn("儿童模式", prompt)
        self.assertIn("不主动索要住址、学校、电话等隐私信息", prompt)
        self.assertIn("安全、活泼、简短", prompt)

    def test_elder_mode_prompt_contains_elder_profile_rules(self):
        from agents.companion_agent import CompanionAgent
        from domain.modes import get_mode_profile

        agent = CompanionAgent(tools=[], memory=None)

        prompt = agent._build_system_prompt(get_mode_profile("elder"))

        self.assertIn("长辈模式", prompt)
        self.assertIn("温和、清楚、慢节奏", prompt)
        self.assertIn("健康相关回复只做生活提醒", prompt)


if __name__ == "__main__":
    unittest.main()
