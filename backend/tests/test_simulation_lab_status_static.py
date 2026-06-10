"""Static checks for Simulation Lab API and documentation integration."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "backend" / "server.py"
API = ROOT / "frontend" / "src" / "lib" / "api.ts"
CHART_WORKSPACE = ROOT / "frontend" / "src" / "components" / "dashboards" / "ChartWorkspace.tsx"
SETTINGS = ROOT / "frontend" / "src" / "components" / "dashboards" / "SettingsDashboard.tsx"
README = ROOT / "README.md"


class SimulationLabStatusStaticTests(unittest.TestCase):
    def test_server_exposes_simulation_lab_status_route(self):
        text = SERVER.read_text(encoding="utf-8")

        self.assertIn("from simulation_lab import (", text)
        self.assertIn("simulation_lab_status,", text)
        self.assertIn('@api_router.get("/simulation-lab/status")', text)
        self.assertIn("return simulation_lab_status()", text)

    def test_server_exposes_gated_orb_backtest_route(self):
        text = SERVER.read_text(encoding="utf-8")

        self.assertIn("SimulationLabOrbBacktestRequest", text)
        self.assertIn("require_simulation_lab_enabled()", text)
        self.assertIn("run_orb_backtest_replay", text)
        self.assertIn("target_r_multiple", text)
        self.assertIn('@api_router.post("/simulation-lab/orb/backtest")', text)

    def test_server_exposes_gated_buying_power_allocation_route(self):
        text = SERVER.read_text(encoding="utf-8")

        self.assertIn("SimulationLabAllocationCandidate", text)
        self.assertIn("SimulationLabBuyingPowerAllocationRequest", text)
        self.assertIn("run_buying_power_allocation_experiment", text)
        self.assertIn('@api_router.post("/simulation-lab/buying-power/allocation")', text)

    def test_server_exposes_gated_stop_trailing_dca_route(self):
        text = SERVER.read_text(encoding="utf-8")

        self.assertIn("SimulationLabStopTrailingDcaRequest", text)
        self.assertIn("SimulationLabStopTrailingDcaBar", text)
        self.assertIn("run_stop_trailing_dca_comparison", text)
        self.assertIn('@api_router.post("/simulation-lab/stop-trailing-dca/compare")', text)

    def test_frontend_api_can_fetch_simulation_lab_status(self):
        text = API.read_text(encoding="utf-8")

        self.assertIn("async getSimulationLabStatus()", text)
        self.assertIn("fetchJSON('/api/simulation-lab/status')", text)
        self.assertIn("async runSimulationLabOrbBacktest", text)
        self.assertIn("fetchJSON('/api/simulation-lab/orb/backtest'", text)
        self.assertIn("async runSimulationLabBuyingPowerAllocation", text)
        self.assertIn("fetchJSON('/api/simulation-lab/buying-power/allocation'", text)
        self.assertIn("async runSimulationLabStopTrailingDcaComparison", text)
        self.assertIn("fetchJSON('/api/simulation-lab/stop-trailing-dca/compare'", text)

    def test_chart_workspace_retains_last_simulation_lab_result_summary(self):
        text = CHART_WORKSPACE.read_text(encoding="utf-8")

        self.assertIn("simulationLabResult", text)
        self.assertIn("setSimulationLabResult", text)
        self.assertIn("Last lab result", text)
        self.assertIn("formatSimulationLabResultTitle", text)
        self.assertIn("formatSimulationLabResultMetric", text)
        self.assertIn("schema_version", text)
        self.assertIn("summary", text)
        self.assertIn("run_id", text)
        self.assertIn("input_fp", text)
        self.assertIn("breakouts", text)
        self.assertIn("scored_breakouts", text)
        self.assertIn("avg_reward_r", text)
        self.assertIn("target_hits", text)
        self.assertIn("stop_hits", text)
        self.assertIn("avg_realized_r", text)
        self.assertIn("allocated_notional", text)
        self.assertIn("fill_ratio", text)
        self.assertIn("unfilled_requested", text)
        self.assertIn("position_limited", text)
        self.assertIn("post_cap_fill", text)
        self.assertIn("'ratio'", text)
        self.assertIn("best_plan", text)
        self.assertIn("best_pnl_pct", text)
        self.assertIn("worst_pnl_pct", text)
        self.assertIn("'percent'", text)

    def test_readme_documents_default_off_simulation_lab_gate(self):
        text = README.read_text(encoding="utf-8")

        self.assertIn("EDGE_SIMULATION_LAB_ENABLED", text)
        self.assertIn("/api/simulation-lab/status", text)
        self.assertIn("endpoint path, method, and result schema version", text)
        self.assertIn("default-hidden", text)
        self.assertIn("ORB backtesting", text)
        self.assertIn("/api/simulation-lab/orb/backtest", text)
        self.assertIn("risk/reward scoring", text)
        self.assertIn("target/stop/open outcome scoring", text)
        self.assertIn("target_r_multiple", text)
        self.assertIn("buying-power allocation experiments", text)
        self.assertIn("/api/simulation-lab/buying-power/allocation", text)
        self.assertIn("aggregate fill-ratio summaries", text)
        self.assertIn("position-cap constraint attribution", text)
        self.assertIn("buying_power_exhausted", text)
        self.assertIn("post-capacity fill ratios", text)
        self.assertIn("stop vs trailing-stop vs DCA comparisons", text)
        self.assertIn("/api/simulation-lab/stop-trailing-dca/compare", text)
        self.assertIn("normalized P&L percentage", text)

    def test_settings_dashboard_surfaces_simulation_lab_status(self):
        text = SETTINGS.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")

        self.assertIn("SimulationLabStatus", text)
        self.assertIn("simulationLabStatus", text)
        self.assertIn("fetch('/api/simulation-lab/status')", text)
        self.assertIn("Simulation Lab status", text)
        self.assertIn("EDGE_SIMULATION_LAB_ENABLED", text)
        self.assertIn("default_hidden", text)
        self.assertIn("disabled_reason", text)
        self.assertIn('RuntimeDetail label="disabled_reason"', text)
        self.assertIn("Experiment catalog", text)
        self.assertIn("formatSimulationLabBoolean", text)
        self.assertIn("formatSimulationLabExperimentEndpoint", text)
        self.assertIn("formatSimulationLabResultMetadataFields", text)
        self.assertIn("result_schema_version", text)
        self.assertIn("result_metadata_fields", text)
        self.assertIn("runnable", text)
        self.assertIn("Simulation Lab status in Settings", readme)
        self.assertIn("disabled reason", readme)


if __name__ == "__main__":
    unittest.main()
