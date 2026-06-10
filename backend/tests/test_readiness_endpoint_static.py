"""Static checks for Edge readiness endpoint semantics."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "backend" / "server.py"


class ReadinessEndpointStaticTests(unittest.TestCase):
    def test_readiness_endpoint_reports_dependency_checks(self):
        text = SERVER.read_text(encoding="utf-8")

        self.assertIn('@api_router.get("/ready")', text)
        self.assertIn("async def readiness", text)
        self.assertIn("_readiness_checks", text)
        self.assertIn("READINESS_CHECK_DETAILS", text)
        self.assertIn("def _readiness_check_details", text)
        self.assertIn('"scheduler_initialized"', text)
        self.assertIn('"scheduler_task_alive"', text)
        self.assertIn('"price_fetcher_initialized"', text)
        self.assertIn('"mongo_available"', text)
        self.assertIn('"demo_mode"', text)
        self.assertIn('"label"', text)
        self.assertIn('"description"', text)
        self.assertIn('"required"', text)
        self.assertIn('"ready": ready', text)
        self.assertIn('"failing_checks": failing_checks', text)
        self.assertIn('"failing_check_details": failing_check_details', text)
        self.assertIn('"check_details": check_details', text)
        self.assertIn('if key != "demo_mode" and not value', text)

    def test_readiness_endpoint_returns_503_when_not_ready(self):
        text = SERVER.read_text(encoding="utf-8")

        self.assertIn("status_code=503", text)
        self.assertIn('"ready": ready', text)
        self.assertIn("raise HTTPException(status_code=503", text)


if __name__ == "__main__":
    unittest.main()
