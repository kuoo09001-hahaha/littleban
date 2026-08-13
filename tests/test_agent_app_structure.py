import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_AGENT_PATH = PROJECT_ROOT / "HDZB_agent" / "main_agent.py"


class AgentAppStructureTest(unittest.TestCase):
    def _parse_main_agent(self):
        source = MAIN_AGENT_PATH.read_text(encoding="utf-8")
        return ast.parse(source)

    def test_main_agent_creates_fastapi_app_once(self):
        tree = self._parse_main_agent()

        app_assignments = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(target, ast.Name) and target.id == "app" for target in node.targets):
                continue
            if isinstance(node.value, ast.Call) and getattr(node.value.func, "id", None) == "FastAPI":
                app_assignments.append(node.lineno)

        self.assertEqual(len(app_assignments), 1)

    def test_core_agent_routes_remain_registered(self):
        tree = self._parse_main_agent()
        registered_routes = set()

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                if not isinstance(decorator.func, ast.Attribute):
                    continue
                if not isinstance(decorator.func.value, ast.Name):
                    continue
                if decorator.func.value.id != "app":
                    continue
                if decorator.args and isinstance(decorator.args[0], ast.Constant):
                    registered_routes.add((decorator.func.attr, decorator.args[0].value))

        expected_routes = {
            ("post", "/agent/chat"),
        }

        self.assertTrue(expected_routes.issubset(registered_routes))


if __name__ == "__main__":
    unittest.main()
