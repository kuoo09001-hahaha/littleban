import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class PromptBuilderTest(unittest.TestCase):
    def test_prompt_includes_mode_and_device_policy(self):
        from domain.device_config import DeviceConfig
        from domain.modes import get_mode_profile
        from services.prompt_builder import PromptBuilder

        prompt = PromptBuilder().build_system_prompt(
            mode_profile=get_mode_profile("child"),
            device_config=DeviceConfig(
                device_id="toy-001",
                volume=55,
                light_profile="soft",
                wake_method="tap_head",
                usage_start="08:00",
                usage_end="21:30",
                content_policy="需要家长知情后再处理定位和联系人信息",
            ),
        )

        self.assertIn("儿童模式", prompt)
        self.assertIn("使用时段：08:00-21:30", prompt)
        self.assertIn("唤醒方式：tap_head", prompt)
        self.assertIn("内容策略：需要家长知情后再处理定位和联系人信息", prompt)

    def test_prompt_locks_the_product_name_to_xiaoban(self):
        from services.prompt_builder import PromptBuilder

        prompt = PromptBuilder().build_system_prompt()
        self.assertIn("家庭陪伴助手“小伴”", prompt)
        self.assertIn("绝不能自称“智宝”", prompt)
        self.assertNotIn('AI陪伴助手"智宝"', prompt)

    def test_prompt_includes_current_chatting_member(self):
        from services.prompt_builder import PromptBuilder

        prompt = PromptBuilder().build_system_prompt(actor_name="小明")
        self.assertIn("当前聊天人：小明", prompt)
        self.assertIn("用户说“我”", prompt)

    def test_prompt_includes_only_persistent_fact_summary(self):
        from services.prompt_builder import PromptBuilder

        prompt = PromptBuilder().build_system_prompt(actor_name="小明", persistent_context="喜欢：游泳；爷爷：王刚")
        self.assertIn("已确认的长期重点信息：喜欢：游泳；爷爷：王刚", prompt)


if __name__ == "__main__":
    unittest.main()
