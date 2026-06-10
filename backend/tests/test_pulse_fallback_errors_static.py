"""Static checks for Pulse account fallback error visibility."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
PNL_TRACKING = ROOT / "frontend" / "src" / "components" / "dashboards" / "PnLTracking.tsx"
PORTFOLIO_ANALYTICS = ROOT / "frontend" / "src" / "components" / "dashboards" / "PortfolioAnalytics.tsx"


class PulseFallbackErrorsStaticTests(unittest.TestCase):
    def test_pnl_tracking_surfaces_live_pulse_error_reason(self):
        text = PNL_TRACKING.read_text(encoding="utf-8")

        self.assertIn("error?: string;", text)
        self.assertIn("setError(typeof data.error === 'string' ? data.error : 'Pulse account data unavailable')", text)
        self.assertIn("{error && (", text)
        self.assertIn('role="alert"', text)
        self.assertIn("{error}", text)

    def test_portfolio_analytics_surfaces_live_pulse_error_reason(self):
        text = PORTFOLIO_ANALYTICS.read_text(encoding="utf-8")

        self.assertIn("setError(typeof data.error === 'string' ? data.error : 'Pulse portfolio data unavailable')", text)
        self.assertIn("{error && (", text)
        self.assertIn('role="alert"', text)
        self.assertIn("{error}", text)


if __name__ == "__main__":
    unittest.main()
