"""Static checks for Simulation Lab API and documentation integration."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "backend" / "server.py"
API = ROOT / "frontend" / "src" / "lib" / "api.ts"
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

    def test_readme_documents_default_off_simulation_lab_gate(self):
        text = README.read_text(encoding="utf-8")

        self.assertIn("EDGE_SIMULATION_LAB_ENABLED", text)
        self.assertIn("/api/simulation-lab/status", text)
        self.assertIn("endpoint path, method, and result schema version", text)
        self.assertIn("default-hidden", text)
        self.assertIn("ORB backtesting", text)
        self.assertIn("/api/simulation-lab/orb/backtest", text)
        self.assertIn("buying-power allocation experiments", text)
        self.assertIn("/api/simulation-lab/buying-power/allocation", text)
        self.assertIn("stop vs trailing-stop vs DCA comparisons", text)
        self.assertIn("/api/simulation-lab/stop-trailing-dca/compare", text)


if __name__ == "__main__":
    unittest.main()
