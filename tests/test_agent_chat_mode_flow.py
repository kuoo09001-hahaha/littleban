import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_AGENT_PATH = PROJECT_ROOT / "HDZB_agent" / "main_agent.py"


class AgentChatModeFlowTest(unittest.TestCase):
    def test_chat_endpoint_resolves_mode_and_returns_metadata(self):
        source = MAIN_AGENT_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)

        chat_function = None
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "agent_chat_endpoint":
                chat_function = node
                break

        self.assertIsNotNone(chat_function)

        names = {node.id for node in ast.walk(chat_function) if isinstance(node, ast.Name)}
        constants = {node.value for node in ast.walk(chat_function) if isinstance(node, ast.Constant)}

        self.assertIn("resolved_mode", names)
        self.assertIn("get_mode_profile", names)
        self.assertIn("mode_profile", names)
        self.assertIn("device_config", names)
        self.assertIn("mode", constants)
        self.assertIn("mode_source", constants)


if __name__ == "__main__":
    unittest.main()
