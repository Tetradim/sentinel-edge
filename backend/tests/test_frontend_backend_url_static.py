"""Static checks that dashboard API calls honor the configured backend URL."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "frontend" / "src" / "lib" / "api.ts"
PNL_TRACKING = ROOT / "frontend" / "src" / "components" / "dashboards" / "PnLTracking.tsx"
PORTFOLIO_ANALYTICS = ROOT / "frontend" / "src" / "components" / "dashboards" / "PortfolioAnalytics.tsx"
SETTINGS = ROOT / "frontend" / "src" / "components" / "dashboards" / "SettingsDashboard.tsx"


class FrontendBackendUrlStaticTests(unittest.TestCase):
    def test_pulse_account_dashboards_use_shared_api_client(self):
        api_text = API.read_text(encoding="utf-8")
        pnl_text = PNL_TRACKING.read_text(encoding="utf-8")
        portfolio_text = PORTFOLIO_ANALYTICS.read_text(encoding="utf-8")

        self.assertIn("async getPulseAccount()", api_text)
        self.assertIn("fetchJSON('/api/pulse/account')", api_text)
        self.assertIn("import { api } from '@/lib/api'", pnl_text)
        self.assertIn("api.getPulseAccount()", pnl_text)
        self.assertNotIn("fetch('/api/pulse/account')", pnl_text)
        self.assertIn("import { api } from '@/lib/api'", portfolio_text)
        self.assertIn("api.getPulseAccount()", portfolio_text)
        self.assertNotIn("fetch('/api/pulse/account')", portfolio_text)

    def test_settings_dashboard_uses_shared_api_client_for_runtime_calls(self):
        api_text = API.read_text(encoding="utf-8")
        settings_text = SETTINGS.read_text(encoding="utf-8")

        self.assertIn("async getPulseHandoffSchema()", api_text)
        self.assertIn("async getNotificationsStatus()", api_text)
        self.assertIn("async validateConfig(config: any)", api_text)
        self.assertIn("import { api } from '@/lib/api'", settings_text)
        self.assertIn("api.getMarketDataProviders()", settings_text)
        self.assertIn("api.getAutomationStatus()", settings_text)
        self.assertIn("api.getTickers()", settings_text)
        self.assertIn("api.getPulseHandoffSchema()", settings_text)
        self.assertIn("api.getSimulationLabStatus()", settings_text)
        self.assertIn("api.getNotificationsStatus()", settings_text)
        self.assertIn("api.updateAutomationSettings(patch)", settings_text)
        self.assertIn("api.updateTickerAutomation(symbol, enabled)", settings_text)
        self.assertIn("api.validateConfig(config)", settings_text)
        self.assertNotIn("fetch('/api/", settings_text)
        self.assertNotIn("fetch(`/api/", settings_text)


if __name__ == "__main__":
    unittest.main()
