"""Static coverage for correlation risk recommendation UI and docs."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
MARKET_BREADTH = ROOT / "frontend" / "src" / "components" / "dashboards" / "MarketBreadth.tsx"
RUNBOOK = ROOT / "docs" / "runbooks" / "correlation-cluster.md"
README = ROOT / "README.md"


class CorrelationRiskRecommendationUiStaticTests(unittest.TestCase):
    def test_market_breadth_surfaces_cluster_risk_recommendation(self):
        text = MARKET_BREADTH.read_text(encoding="utf-8")
        runbook = RUNBOOK.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")

        self.assertIn("risk_recommendation", text)
        self.assertIn("trailing_stop_action", text)
        self.assertIn("operator_summary", text)
        self.assertIn("Risk recommendation", text)
        self.assertIn("tighten_trailing_global", text)
        self.assertIn("review_trailing_stops", text)
        self.assertIn("observe_momentum", text)
        self.assertIn("risk_recommendation", runbook)
        self.assertIn("trailing_stop_action", runbook)
        self.assertIn("correlation risk recommendation", readme)


if __name__ == "__main__":
    unittest.main()
