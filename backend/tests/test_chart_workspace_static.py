"""Static checks for Chart Workspace API and frontend integration."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CHART_WORKSPACE = ROOT / "backend" / "chart_workspace.py"
SERVER = ROOT / "backend" / "server.py"
API = ROOT / "frontend" / "src" / "lib" / "api.ts"
TYPES = ROOT / "frontend" / "src" / "types" / "index.ts"
OPERATIONS_PANEL = ROOT / "frontend" / "src" / "components" / "asset-command" / "components" / "OperationsPanel.tsx"
ASSET_DATA = ROOT / "frontend" / "src" / "components" / "asset-command" / "data.ts"
ASSET_TYPES = ROOT / "frontend" / "src" / "components" / "asset-command" / "types.ts"
CHART_DASHBOARD = ROOT / "frontend" / "src" / "components" / "dashboards" / "ChartWorkspace.tsx"
README = ROOT / "README.md"


class ChartWorkspaceStaticTests(unittest.TestCase):
    def test_backend_defines_chart_workspace_snapshot_builder(self):
        text = CHART_WORKSPACE.read_text(encoding="utf-8")

        self.assertIn('CHART_WORKSPACE_SCHEMA_VERSION = "edge.chart_workspace.snapshot.v1"', text)
        self.assertIn("def build_chart_workspace_payload", text)
        self.assertIn("def _ema_series", text)
        self.assertIn("def _sma_series", text)
        self.assertIn("def _rsi_series", text)
        self.assertIn("def _macd_points", text)

    def test_server_exposes_chart_workspace_route(self):
        text = SERVER.read_text(encoding="utf-8")

        self.assertIn("from chart_workspace import build_chart_workspace_payload", text)
        self.assertIn('@api_router.get("/chart-workspace/{symbol}")', text)
        self.assertIn("await fetcher.get_ohlcv", text)
        self.assertIn("scheduler.orb.get_session_status", text)

    def test_frontend_api_and_types_include_chart_workspace_contract(self):
        api = API.read_text(encoding="utf-8")
        types = TYPES.read_text(encoding="utf-8")

        self.assertIn("async getChartWorkspace", api)
        self.assertIn("fetchJSON<ChartWorkspaceSnapshot>", api)
        self.assertIn("export interface ChartWorkspaceSnapshot", types)
        self.assertIn("export type ChartWorkspaceIndicatorId", types)

    def test_operations_deck_exposes_chart_workspace_tab(self):
        panel = OPERATIONS_PANEL.read_text(encoding="utf-8")
        data = ASSET_DATA.read_text(encoding="utf-8")
        types = ASSET_TYPES.read_text(encoding="utf-8")
        dashboard = CHART_DASHBOARD.read_text(encoding="utf-8")

        self.assertIn("ChartWorkspace", panel)
        self.assertIn("activeView === 'charts'", panel)
        self.assertIn("{ id: 'charts', label: 'Chart Workspace'", data)
        self.assertIn("'charts'", types)
        self.assertIn("runSimulationLabOrbBacktest", dashboard)
        self.assertIn("runSimulationLabStopTrailingDcaComparison", dashboard)
        self.assertIn("PlotlyChart", dashboard)

    def test_readme_documents_chart_workspace_endpoint(self):
        text = README.read_text(encoding="utf-8")

        self.assertIn("/api/chart-workspace/{symbol}", text)
        self.assertIn("EMA/SMA, RSI, MACD", text)
        self.assertIn("ORB overlays", text)


if __name__ == "__main__":
    unittest.main()
