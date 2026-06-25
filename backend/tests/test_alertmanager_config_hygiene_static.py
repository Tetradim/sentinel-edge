"""Dependency-free hygiene checks for Alertmanager configuration."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
ALERTMANAGER = ROOT / "prometheus" / "alertmanager.yml"


class AlertmanagerConfigHygieneStaticTests(unittest.TestCase):
    def test_root_route_has_default_receiver(self):
        text = ALERTMANAGER.read_text(encoding="utf-8")
        root_route = text[text.index("route:"):text.index("  routes:")]
        receiver_block = text[text.index("receivers:"):text.index("inhibit_rules:")]

        root_receiver = re.search(r"^  receiver: '([^']+)'$", root_route, re.MULTILINE)
        self.assertIsNotNone(root_receiver)
        self.assertIn(f"- name: '{root_receiver.group(1)}'", receiver_block)

    def test_automation_route_comment_matches_route(self):
        text = ALERTMANAGER.read_text(encoding="utf-8")
        route_start = text.index('component = "automation"')
        route = text[max(0, route_start - 320):text.index("receiver: 'automation-alerts'", route_start)]

        self.assertIn("Automation delivery failures", route)
        self.assertNotIn("Critical risk events", route)

    def test_automation_receiver_comment_matches_receiver(self):
        text = ALERTMANAGER.read_text(encoding="utf-8")
        receiver_start = text.index("- name: 'automation-alerts'")
        receiver = text[max(0, receiver_start - 160):receiver_start]

        self.assertIn("Automation alerts", receiver)
        self.assertNotIn("calls Sentinel Edge webhook which calls send_override", receiver)

    def test_child_routes_have_single_receiver_and_optional_continue(self):
        text = ALERTMANAGER.read_text(encoding="utf-8")
        route_block = text[text.index("  routes:"):text.index("receivers:")]
        route_starts = [m.start() for m in re.finditer(r"^    - ", route_block, re.MULTILINE)]
        self.assertGreaterEqual(len(route_starts), 2)

        for index, start in enumerate(route_starts):
            end = route_starts[index + 1] if index + 1 < len(route_starts) else len(route_block)
            route = route_block[start:end]
            self.assertEqual(route.count("receiver:"), 1, msg=route)
            if "matchers:" in route:
                self.assertRegex(route, r"continue: (true|false)", msg=route)


if __name__ == "__main__":
    unittest.main()
