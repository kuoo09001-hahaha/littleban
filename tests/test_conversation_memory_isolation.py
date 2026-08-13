import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))


class ConversationMemoryIsolationTest(unittest.TestCase):
    def test_langchain_messages_do_not_cross_sessions(self):
        from memory.conversation_memory import EnhancedConversationMemory

        memory = EnhancedConversationMemory(window_size=2)
        memory.save_context("我是甲", "你好甲", "session-a")
        memory.save_context("我是乙", "你好乙", "session-b")

        session_a_messages = memory.get_memory_as_messages("session-a")
        session_b_messages = memory.get_memory_as_messages("session-b")

        self.assertEqual(len(session_a_messages), 2)
        self.assertEqual(len(session_b_messages), 2)
        self.assertIn("甲", session_a_messages[0].content)
        self.assertIn("乙", session_b_messages[0].content)


if __name__ == "__main__":
    unittest.main()
