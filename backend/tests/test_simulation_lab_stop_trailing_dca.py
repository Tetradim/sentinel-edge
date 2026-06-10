"""Behavior tests for Simulation Lab stop/trailing-stop/DCA comparisons."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from simulation_lab import (  # noqa: E402
    SIMULATION_LAB_ENV_FLAG,
    SimulationLabDisabledError,
    require_simulation_lab_enabled,
    run_stop_trailing_dca_comparison,
    simulation_lab_status,
)


class SimulationLabStopTrailingDcaTests(unittest.TestCase):
    def test_comparison_ranks_trailing_stop_above_stop_and_dca(self):
        result = run_stop_trailing_dca_comparison(
            entry_price=100.0,
            quantity=1.0,
            stop_loss_pct=0.05,
            trailing_pct=0.05,
            dca_steps=1,
            dca_drop_pct=0.03,
            price_path=[
                {"timestamp": "2026-06-09T13:31:00Z", "high": 104.0, "low": 101.0, "close": 103.0},
                {"timestamp": "2026-06-09T13:32:00Z", "high": 106.0, "low": 102.0, "close": 105.0},
                {"timestamp": "2026-06-09T13:33:00Z", "high": 105.0, "low": 100.5, "close": 101.0},
                {"timestamp": "2026-06-09T13:34:00Z", "high": 96.0, "low": 94.0, "close": 95.0},
            ],
        )

        plans = {plan["plan"]: plan for plan in result["plans"]}

        self.assertEqual(result["schema_version"], "edge.simulation_lab.stop_trailing_dca.v1")
        self.assertEqual(result["summary"]["plan_count"], 3)
        self.assertEqual(result["summary"]["best_plan"], "trailing_stop")
        self.assertEqual(result["summary"]["worst_plan"], "dca")
        self.assertEqual(result["summary"]["best_pnl"], 0.7)
        self.assertEqual(result["summary"]["worst_pnl"], -7.0)

        self.assertEqual(plans["regular_stop"]["exit_reason"], "stop_loss")
        self.assertEqual(plans["regular_stop"]["exit_price"], 95.0)
        self.assertEqual(plans["regular_stop"]["pnl"], -5.0)

        self.assertEqual(plans["trailing_stop"]["exit_reason"], "trailing_stop")
        self.assertEqual(plans["trailing_stop"]["exit_price"], 100.7)
        self.assertEqual(plans["trailing_stop"]["pnl"], 0.7)

        self.assertEqual(plans["dca"]["exit_reason"], "final_close")
        self.assertEqual(plans["dca"]["dca_fills"], 1)
        self.assertEqual(plans["dca"]["average_entry_price"], 98.5)
        self.assertEqual(plans["dca"]["quantity"], 2.0)
        self.assertEqual(plans["dca"]["pnl"], -7.0)

    def test_dca_plan_can_fill_multiple_ladder_steps(self):
        result = run_stop_trailing_dca_comparison(
            entry_price=100.0,
            quantity=2.0,
            stop_loss_pct=0.08,
            trailing_pct=0.08,
            dca_steps=2,
            dca_drop_pct=0.02,
            price_path=[
                {"timestamp": "2026-06-09T13:31:00Z", "high": 101.0, "low": 98.0, "close": 99.0},
                {"timestamp": "2026-06-09T13:32:00Z", "high": 99.0, "low": 96.0, "close": 97.0},
                {"timestamp": "2026-06-09T13:33:00Z", "high": 104.0, "low": 97.0, "close": 103.0},
            ],
        )

        dca = next(plan for plan in result["plans"] if plan["plan"] == "dca")

        self.assertEqual(dca["dca_fills"], 2)
        self.assertEqual(dca["average_entry_price"], 98.0)
        self.assertEqual(dca["quantity"], 6.0)
        self.assertEqual(dca["pnl"], 30.0)
        self.assertEqual([fill["price"] for fill in dca["fills"]], [98.0, 96.0])

    def test_stop_trailing_dca_is_runnable_only_when_lab_is_enabled(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(SIMULATION_LAB_ENV_FLAG, None)
            with self.assertRaises(SimulationLabDisabledError):
                require_simulation_lab_enabled()
            status = simulation_lab_status()
            experiment = next(item for item in status["experiments"] if item["id"] == "stop_trailing_dca")
            self.assertEqual(experiment["status"], "available")
            self.assertFalse(experiment["runnable"])

        with patch.dict(os.environ, {SIMULATION_LAB_ENV_FLAG: "true"}):
            require_simulation_lab_enabled()
            status = simulation_lab_status()
            experiment = next(item for item in status["experiments"] if item["id"] == "stop_trailing_dca")
            self.assertEqual(experiment["status"], "available")
            self.assertTrue(experiment["runnable"])


if __name__ == "__main__":
    unittest.main()
