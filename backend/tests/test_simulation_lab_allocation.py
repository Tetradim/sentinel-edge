"""Behavior tests for Simulation Lab buying-power allocation experiments."""
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
    run_buying_power_allocation_experiment,
    simulation_lab_status,
)


class SimulationLabAllocationTests(unittest.TestCase):
    def test_confidence_weighted_allocation_respects_reserve_and_position_cap(self):
        result = run_buying_power_allocation_experiment(
            buying_power=10000.0,
            cash_reserve_pct=0.10,
            max_position_pct=0.40,
            mode="confidence_weighted",
            candidates=[
                {"symbol": "aapl", "confidence": 0.90, "requested_notional": 7000.0},
                {"symbol": "msft", "confidence": 0.60, "requested_notional": 7000.0},
                {"symbol": "nvda", "confidence": 0.30, "requested_notional": 7000.0},
            ],
        )

        self.assertEqual(result["schema_version"], "edge.simulation_lab.buying_power_allocation.v1")
        self.assertEqual(result["mode"], "confidence_weighted")
        self.assertEqual(result["summary"]["candidate_count"], 3)
        self.assertEqual(result["summary"]["allocated_count"], 3)
        self.assertEqual(result["summary"]["allocated_notional"], 8500.0)
        self.assertEqual(result["summary"]["unallocated_notional"], 500.0)
        self.assertEqual([item["symbol"] for item in result["allocations"]], ["AAPL", "MSFT", "NVDA"])
        self.assertEqual([item["allocated_notional"] for item in result["allocations"]], [4000.0, 3000.0, 1500.0])

    def test_equal_weight_allocation_keeps_unused_capacity_when_request_is_smaller_than_slice(self):
        result = run_buying_power_allocation_experiment(
            buying_power=9000.0,
            cash_reserve_pct=0.0,
            max_position_pct=0.50,
            mode="equal_weight",
            candidates=[
                {"symbol": "spy", "confidence": 0.70, "requested_notional": 1000.0},
                {"symbol": "qqq", "confidence": 0.70, "requested_notional": 5000.0},
                {"symbol": "iwm", "confidence": 0.70, "requested_notional": 5000.0},
            ],
        )

        self.assertEqual(result["mode"], "equal_weight")
        self.assertEqual([item["allocated_notional"] for item in result["allocations"]], [1000.0, 3000.0, 3000.0])
        self.assertEqual(result["summary"]["allocated_notional"], 7000.0)
        self.assertEqual(result["summary"]["unallocated_notional"], 2000.0)

    def test_buying_power_allocation_is_runnable_only_when_lab_is_enabled(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(SIMULATION_LAB_ENV_FLAG, None)
            with self.assertRaises(SimulationLabDisabledError):
                require_simulation_lab_enabled()
            status = simulation_lab_status()
            experiment = next(item for item in status["experiments"] if item["id"] == "buying_power_allocation")
            self.assertFalse(experiment["runnable"])

        with patch.dict(os.environ, {SIMULATION_LAB_ENV_FLAG: "true"}):
            require_simulation_lab_enabled()
            status = simulation_lab_status()
            experiment = next(item for item in status["experiments"] if item["id"] == "buying_power_allocation")
            self.assertEqual(experiment["status"], "available")
            self.assertTrue(experiment["runnable"])


if __name__ == "__main__":
    unittest.main()
