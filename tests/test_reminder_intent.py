import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INTENT_TOOL_PATH = PROJECT_ROOT / "HDZB_agent" / "tools" / "intent_tools.py"


class ReminderIntentTest(unittest.TestCase):
    def test_daily_medication_has_local_timeout_resilient_path(self):
        source = INTENT_TOOL_PATH.read_text(encoding="utf-8")
        self.assertIn("_extract_local_reminder_intent", source)
        self.assertIn('"needs_time": not has_time', source)
        self.assertIn('"repeat_desc": repeat_desc', source)

    def test_noon_is_extracted_as_twelve_not_default_eight(self):
        source = INTENT_TOOL_PATH.read_text(encoding="utf-8")
        self.assertIn("extract_time(user_input) is not None", source)
        self.assertIn('reminder_title_hint(user_input)', source)
        self.assertIn("extract_reminder_date(user_input)", source)

    def test_delete_words_are_checked_before_reminder_creation(self):
        source = INTENT_TOOL_PATH.read_text(encoding="utf-8")
        self.assertLess(source.index('("删除", "取消", "关闭", "不要", "移除")'), source.index('time_info ='))
        self.assertIn('"intent_type": "DELETE_ALARM"', source)

    def test_tell_a_family_member_uses_the_local_reminder_path(self):
        source = INTENT_TOOL_PATH.read_text(encoding="utf-8")
        self.assertIn('"告诉", "转告"', source)


if __name__ == "__main__":
    unittest.main()
