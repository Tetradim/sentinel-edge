"""Behavior tests for Edge readiness detail payloads."""
import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

import server  # noqa: E402


class ReadinessDetailsTests(unittest.TestCase):
    def test_check_details_include_names_and_operator_metadata(self):
        details = server._readiness_check_details(
            {
                "scheduler_initialized": False,
                "demo_mode": True,
                "new_runtime_check": False,
            }
        )

        self.assertEqual(details["scheduler_initialized"]["name"], "scheduler_initialized")
        self.assertEqual(details["scheduler_initialized"]["label"], "Scheduler initialized")
        self.assertTrue(details["scheduler_initialized"]["required"])
        self.assertFalse(details["scheduler_initialized"]["ready"])
        self.assertEqual(details["demo_mode"]["name"], "demo_mode")
        self.assertFalse(details["demo_mode"]["required"])
        self.assertEqual(details["new_runtime_check"]["label"], "New Runtime Check")

    def test_refresh_readiness_payload_includes_failing_check_details(self):
        previous_scheduler = server.scheduler
        previous_scheduler_task = server.scheduler_task
        previous_price_fetcher = server.price_fetcher
        previous_edge = server.edge
        previous_db = server.db
        previous_demo_mode = server.DEMO_MODE
        try:
            server.scheduler = None
            server.scheduler_task = None
            server.price_fetcher = None
            server.edge = None
            server.db = None
            server.DEMO_MODE = False

            state = server._refresh_readiness_metrics()
        finally:
            server.scheduler = previous_scheduler
            server.scheduler_task = previous_scheduler_task
            server.price_fetcher = previous_price_fetcher
            server.edge = previous_edge
            server.db = previous_db
            server.DEMO_MODE = previous_demo_mode

        self.assertFalse(state["ready"])
        self.assertIn("failing_check_details", state)
        self.assertEqual(
            [detail["name"] for detail in state["failing_check_details"]],
            state["failing_checks"],
        )
        self.assertTrue(all(detail["required"] for detail in state["failing_check_details"]))
        self.assertIn("Scheduler initialized", [detail["label"] for detail in state["failing_check_details"]])
        self.assertEqual(state["status"], "not_ready")
        self.assertRegex(state["timestamp"], r"^\d{4}-\d{2}-\d{2}T.*Z$")


if __name__ == "__main__":
    unittest.main()
