"""Static checks for command-bus test endpoint gating."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "backend" / "server.py"
README = ROOT / "README.md"
DOCKER_COMPOSE = ROOT / "docker-compose.yml"


class TestCommandEndpointGateStaticTests(unittest.TestCase):
    def test_command_bus_test_endpoints_are_env_gated(self):
        text = SERVER.read_text(encoding="utf-8")

        self.assertIn("def _test_command_endpoints_enabled() -> bool:", text)
        self.assertIn('os.getenv("EDGE_TEST_COMMAND_ENDPOINTS_ENABLED", "false")', text)
        self.assertIn("def _require_test_command_endpoints_enabled() -> None:", text)
        self.assertEqual(text.count("\n    _require_test_command_endpoints_enabled()"), 3)

        for route in (
            '@api_router.post("/test/pulse-command")',
            '@api_router.post("/test/send-command")',
            '@api_router.get("/test/commands")',
        ):
            start = text.index(route)
            next_route = text.find("\n@api_router.", start + 1)
            segment = text[start : next_route if next_route != -1 else len(text)]
            self.assertIn("_require_test_command_endpoints_enabled()", segment)

    def test_docs_and_compose_keep_command_bus_test_endpoints_disabled(self):
        readme = README.read_text(encoding="utf-8")
        compose = DOCKER_COMPOSE.read_text(encoding="utf-8")

        self.assertIn("EDGE_TEST_COMMAND_ENDPOINTS_ENABLED", readme)
        self.assertIn("disabled by default", readme.lower())
        self.assertIn("EDGE_TEST_COMMAND_ENDPOINTS_ENABLED=false", compose)


if __name__ == "__main__":
    unittest.main()
