"""Static checks for Edge readiness alert runbook coverage."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
ALERTS = ROOT / "prometheus" / "alerts" / "sentinel_edge_rules.yml"
RUNBOOK = ROOT / "docs" / "runbooks" / "edge-runtime-not-ready.md"


class ReadinessRunbookStaticTests(unittest.TestCase):
    def test_readiness_alert_links_to_runbook(self):
        text = ALERTS.read_text(encoding="utf-8")

        self.assertIn("EdgeRuntimeNotReady", text)
        self.assertIn('runbook_url: "docs/runbooks/edge-runtime-not-ready.md"', text)

    def test_readiness_runbook_has_actionable_triage_steps(self):
        text = RUNBOOK.read_text(encoding="utf-8")

        self.assertIn("Edge Runtime Not Ready", text)
        self.assertIn("/api/ready", text)
        self.assertIn("ErrorDetails.Message", text)
        self.assertIn("detail.failing_check_details", text)
        self.assertIn("Select-Object name, label, description", text)
        self.assertIn("edge_readiness_check_status", text)
        self.assertIn("scheduler_task_alive", text)
        self.assertIn("price_fetcher_initialized", text)
        self.assertIn("mongo_available", text)
        self.assertIn("Launch-Sentinel-Edge-Local.ps1", text)
        self.assertIn("Pause automation", text)


if __name__ == "__main__":
    unittest.main()
