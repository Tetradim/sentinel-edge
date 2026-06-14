"""Static checks for readiness Prometheus observability."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "backend" / "server.py"
METRICS = ROOT / "backend" / "metrics.py"
ALERTS = ROOT / "prometheus" / "alerts" / "sentinel_edge_rules.yml"


class ReadinessMetricsStaticTests(unittest.TestCase):
    def test_readiness_metrics_are_defined_with_low_cardinality_labels(self):
        text = METRICS.read_text(encoding="utf-8")

        self.assertIn("edge_readiness_status", text)
        self.assertIn("edge_readiness_check_status", text)
        self.assertIn('["check"]', text)
        self.assertNotIn('["symbol", "check"]', text)
        self.assertNotIn('["client", "check"]', text)

    def test_readiness_endpoint_updates_metrics(self):
        text = SERVER.read_text(encoding="utf-8")

        self.assertIn("edge_readiness_status", text)
        self.assertIn("edge_readiness_check_status", text)
        self.assertIn("_publish_readiness_metrics(checks, ready)", text)
        self.assertIn('edge_readiness_check_status.labels(check=check_name).set(1 if check_ready else 0)', text)

    def test_metrics_scrape_refreshes_readiness_metrics(self):
        text = SERVER.read_text(encoding="utf-8")

        metrics_start = text.index('@app.get("/metrics"')
        metrics_text = text[metrics_start:text.index("# \u2500", metrics_start)]

        self.assertIn("_refresh_readiness_metrics()", metrics_text)
        self.assertLess(
            metrics_text.index("_refresh_readiness_metrics()"),
            metrics_text.index("generate_latest(REGISTRY)"),
        )

    def test_alert_rule_fires_when_edge_is_not_ready(self):
        text = ALERTS.read_text(encoding="utf-8")

        self.assertIn("EdgeRuntimeNotReady", text)
        self.assertIn("edge_readiness_status == 0", text)
        self.assertIn("component: engine", text)

    def test_alert_rule_identifies_failed_readiness_check(self):
        text = ALERTS.read_text(encoding="utf-8")

        self.assertIn("EdgeReadinessCheckFailed", text)
        self.assertIn("edge_readiness_check_status == 0", text)
        self.assertIn("{{ $labels.check }}", text)
        self.assertIn('runbook_url: "docs/runbooks/edge-runtime-not-ready.md"', text)


if __name__ == "__main__":
    unittest.main()
