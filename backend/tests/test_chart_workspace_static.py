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
        self.assertIn("orb_session_status?: OrbSessionStatus", types)

    def test_chart_workspace_snapshot_panel_surfaces_orb_session_context(self):
        dashboard = CHART_DASHBOARD.read_text(encoding="utf-8")

        self.assertIn("orbSessionStatus = snapshot?.orb_session_status", dashboard)
        self.assertIn("Metric label=\"ORB session\"", dashboard)
        self.assertIn("Metric label=\"ORB status\"", dashboard)
        self.assertIn("formatOrbSessionStatus", dashboard)

    def test_chart_workspace_snapshot_panel_lists_all_orb_sessions(self):
        dashboard = CHART_DASHBOARD.read_text(encoding="utf-8")

        self.assertIn("orbSessionEntries", dashboard)
        self.assertIn("ORB sessions", dashboard)
        self.assertIn("formatOrbSessionLevelSummary", dashboard)
        self.assertIn("session.timeframes", dashboard)
        self.assertIn("session.levels", dashboard)

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
        self.assertIn("runSimulationLabBuyingPowerAllocation", dashboard)
        self.assertIn("runSimulationLabStopTrailingDcaComparison", dashboard)
        self.assertIn("runAllocationExperiment", dashboard)
        self.assertIn("buildAllocationCandidates", dashboard)
        self.assertIn("Buying Power", dashboard)
        self.assertIn("PlotlyChart", dashboard)

    def test_chart_workspace_exposes_custom_layout_persistence(self):
        dashboard = CHART_DASHBOARD.read_text(encoding="utf-8")

        self.assertIn("CHART_WORKSPACE_LAYOUT_STORAGE_KEY", dashboard)
        self.assertIn("sentinel-edge.chart-workspace.layout.v1", dashboard)
        self.assertIn("layoutMode", dashboard)
        self.assertIn("panelVisibility", dashboard)
        self.assertIn("localStorage.getItem", dashboard)
        self.assertIn("localStorage.setItem", dashboard)
        self.assertIn("localStorage.removeItem", dashboard)
        self.assertIn("Analysis", dashboard)
        self.assertIn("Execution", dashboard)
        self.assertIn("Research", dashboard)
        self.assertIn("Oscillators", dashboard)
        self.assertIn("Lab", dashboard)
        self.assertIn("Snapshot", dashboard)
        self.assertIn("2xl:grid-cols-[minmax(0,1fr)_280px]", dashboard)
        self.assertNotIn("lg:grid-cols-[minmax(0,1fr)_280px]", dashboard)

    def test_chart_workspace_hides_simulation_lab_until_enabled(self):
        dashboard = CHART_DASHBOARD.read_text(encoding="utf-8")

        self.assertIn("getSimulationLabStatus", dashboard)
        self.assertIn("simulationLabStatus", dashboard)
        self.assertIn("simulationLabEnabled", dashboard)
        self.assertIn("visiblePanelOptions", dashboard)
        self.assertIn("panelVisibility.lab && simulationLabEnabled", dashboard)
        self.assertIn("option.id !== 'lab' || simulationLabEnabled", dashboard)

    def test_chart_workspace_surfaces_simulation_lab_catalog_metadata(self):
        dashboard = CHART_DASHBOARD.read_text(encoding="utf-8")

        self.assertIn("simulationLabExperiments", dashboard)
        self.assertIn("Lab catalog", dashboard)
        self.assertIn("formatSimulationLabEndpoint", dashboard)
        self.assertIn("result_schema_version", dashboard)
        self.assertIn("endpoint_path", dashboard)
        self.assertIn("http_method", dashboard)

    def test_chart_workspace_orb_replay_can_select_orb_session(self):
        dashboard = CHART_DASHBOARD.read_text(encoding="utf-8")

        self.assertIn("ChartWorkspaceOrbReplaySession", dashboard)
        self.assertIn("ORB_REPLAY_SESSION_OPTIONS", dashboard)
        self.assertIn("premarket_30m", dashboard)
        self.assertIn("market_open", dashboard)
        self.assertIn("Premarket 30m", dashboard)
        self.assertIn("Market open", dashboard)
        self.assertIn("orbReplaySession", dashboard)
        self.assertIn("setOrbReplaySession", dashboard)
        self.assertIn('aria-label="ORB replay session"', dashboard)
        self.assertIn("session_id: orbReplaySession", dashboard)
        self.assertIn("timeframe_minutes: selectedOrbReplaySession.timeframeMinutes", dashboard)
        self.assertNotIn("session_id: 'market_open'", dashboard)

    def test_chart_workspace_exposes_persistent_chart_preferences(self):
        dashboard = CHART_DASHBOARD.read_text(encoding="utf-8")

        self.assertIn("CHART_WORKSPACE_PREFERENCES_STORAGE_KEY", dashboard)
        self.assertIn("sentinel-edge.chart-workspace.preferences.v1", dashboard)
        self.assertIn("ChartWorkspacePreferencesState", dashboard)
        self.assertIn("barLimit", dashboard)
        self.assertIn("readChartWorkspacePreferences", dashboard)
        self.assertIn("persistChartWorkspacePreferences", dashboard)
        self.assertIn("normalizeChartWorkspacePreferences", dashboard)
        self.assertIn("setBarLimit", dashboard)
        self.assertIn("showOrbOverlays", dashboard)
        self.assertIn("toggleOrbOverlays", dashboard)
        self.assertIn("includeOrbOverlays", dashboard)
        self.assertIn("ORB overlays", dashboard)
        self.assertIn('type="radio"', dashboard)
        self.assertIn('name="chart-type"', dashboard)
        self.assertIn("120 bars", dashboard)
        self.assertIn("240 bars", dashboard)
        self.assertIn("390 bars", dashboard)

    def test_chart_workspace_exposes_persistent_orb_session_overlay_filters(self):
        dashboard = CHART_DASHBOARD.read_text(encoding="utf-8")

        self.assertIn("ChartWorkspaceOrbOverlaySession", dashboard)
        self.assertIn("ORB_OVERLAY_SESSION_OPTIONS", dashboard)
        self.assertIn("orbOverlaySessions", dashboard)
        self.assertIn("toggleOrbOverlaySession", dashboard)
        self.assertIn("includeOrbOverlaySession", dashboard)
        self.assertIn("normalizeOrbOverlaySessions", dashboard)
        self.assertIn("Premarket ORB", dashboard)
        self.assertIn("Market open ORB", dashboard)
        self.assertIn("premarket_30m", dashboard)
        self.assertIn("market_open", dashboard)

    def test_readme_documents_chart_workspace_endpoint(self):
        text = README.read_text(encoding="utf-8")

        self.assertIn("/api/chart-workspace/{symbol}", text)
        self.assertIn("EMA/SMA, RSI, MACD", text)
        self.assertIn("ORB overlays", text)
        self.assertIn("per-session ORB overlay filters", text)
        self.assertIn("Analysis/Execution/Research layouts", text)
        self.assertIn("persistent symbol, chart-type, indicator, and range preferences", text)
        self.assertIn("toggleable ORB overlays", text)


if __name__ == "__main__":
    unittest.main()
