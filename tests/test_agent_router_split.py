import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = PROJECT_ROOT / "HDZB_agent"
MAIN_AGENT_PATH = AGENT_ROOT / "main_agent.py"
WEATHER_ROUTER_PATH = AGENT_ROOT / "api" / "weather.py"
PERSONAL_INFO_ROUTER_PATH = AGENT_ROOT / "api" / "personal_info.py"
SESSIONS_ROUTER_PATH = AGENT_ROOT / "api" / "sessions.py"
MEMORY_ROUTER_PATH = AGENT_ROOT / "api" / "memory.py"
STATUS_ROUTER_PATH = AGENT_ROOT / "api" / "status.py"
DEVICES_ROUTER_PATH = AGENT_ROOT / "api" / "devices.py"


def parse_file(path: Path):
    return ast.parse(path.read_text(encoding="utf-8"))


def route_paths(path: Path):
    tree = parse_file(path)
    routes = set()

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
            if decorator.func.value.id != "router":
                continue
            if decorator.args and isinstance(decorator.args[0], ast.Constant):
                routes.add((decorator.func.attr, decorator.args[0].value))

    return routes


class AgentRouterSplitTest(unittest.TestCase):
    def test_main_agent_includes_extracted_routers(self):
        tree = parse_file(MAIN_AGENT_PATH)
        include_router_calls = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "include_router":
                continue
            if not isinstance(node.func.value, ast.Name) or node.func.value.id != "app":
                continue
            if node.args and isinstance(node.args[0], ast.Name):
                include_router_calls.append(node.args[0].id)

        self.assertIn("weather_router", include_router_calls)
        self.assertIn("personal_info_router", include_router_calls)
        self.assertIn("sessions_router", include_router_calls)
        self.assertIn("memory_router", include_router_calls)
        self.assertIn("status_router", include_router_calls)
        self.assertIn("devices_router", include_router_calls)

    def test_weather_router_preserves_public_route(self):
        self.assertIn(("post", "/agent/weather/query"), route_paths(WEATHER_ROUTER_PATH))

    def test_personal_info_router_preserves_public_routes(self):
        self.assertTrue(
            {
                ("post", "/agent/personal_info/add"),
                ("get", "/agent/personal_info/{person_name}"),
                ("get", "/agent/personal_info"),
            }.issubset(route_paths(PERSONAL_INFO_ROUTER_PATH))
        )

    def test_sessions_router_preserves_public_routes(self):
        self.assertTrue(
            {
                ("get", "/agent/sessions/{session_id}"),
                ("delete", "/agent/sessions/{session_id}"),
                ("get", "/agent/sessions"),
            }.issubset(route_paths(SESSIONS_ROUTER_PATH))
        )

    def test_memory_router_preserves_public_routes(self):
        self.assertTrue(
            {
                ("get", "/agent/memory/{session_id}"),
                ("post", "/agent/memory/{session_id}/important"),
            }.issubset(route_paths(MEMORY_ROUTER_PATH))
        )

    def test_status_router_preserves_public_routes(self):
        self.assertTrue(
            {
                ("get", "/agent/debug/{session_id}"),
                ("get", "/agent/health"),
                ("get", "/agent/metrics"),
                ("get", "/"),
            }.issubset(route_paths(STATUS_ROUTER_PATH))
        )

    def test_devices_router_exposes_mode_routes(self):
        self.assertTrue(
            {
                ("get", "/agent/devices/{device_id}/mode"),
                ("put", "/agent/devices/{device_id}/mode"),
                ("get", "/agent/devices/{device_id}/config"),
                ("put", "/agent/devices/{device_id}/config"),
            }.issubset(route_paths(DEVICES_ROUTER_PATH))
        )


if __name__ == "__main__":
    unittest.main()
