"""Behavior tests for the Simulation Lab feature gate contract."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from simulation_lab import SIMULATION_LAB_ENV_FLAG, simulation_lab_status  # noqa: E402


class SimulationLabStatusTests(unittest.TestCase):
    def test_simulation_lab_is_disabled_and_hidden_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(SIMULATION_LAB_ENV_FLAG, None)

            status = simulation_lab_status()

        self.assertFalse(status["enabled"])
        self.assertTrue(status["default_hidden"])
        self.assertEqual(status["env_flag"], "EDGE_SIMULATION_LAB_ENABLED")
        self.assertEqual(
            [experiment["id"] for experiment in status["experiments"]],
            ["orb_backtest", "buying_power_allocation", "stop_trailing_dca"],
        )
        self.assertTrue(all(experiment["state"] == "hidden" for experiment in status["experiments"]))
        self.assertTrue(all(experiment["runnable"] is False for experiment in status["experiments"]))
        experiments = {experiment["id"]: experiment for experiment in status["experiments"]}
        self.assertEqual(experiments["orb_backtest"]["http_method"], "POST")
        self.assertEqual(experiments["orb_backtest"]["endpoint_path"], "/api/simulation-lab/orb/backtest")
        self.assertEqual(experiments["orb_backtest"]["result_schema_version"], "edge.simulation_lab.orb_backtest.v1")
        self.assertEqual(
            experiments["buying_power_allocation"]["endpoint_path"],
            "/api/simulation-lab/buying-power/allocation",
        )
        self.assertEqual(
            experiments["buying_power_allocation"]["result_schema_version"],
            "edge.simulation_lab.buying_power_allocation.v1",
        )
        self.assertEqual(
            experiments["stop_trailing_dca"]["endpoint_path"],
            "/api/simulation-lab/stop-trailing-dca/compare",
        )
        self.assertEqual(
            experiments["stop_trailing_dca"]["result_schema_version"],
            "edge.simulation_lab.stop_trailing_dca.v1",
        )

    def test_simulation_lab_can_be_enabled_by_environment(self):
        with patch.dict(os.environ, {SIMULATION_LAB_ENV_FLAG: "true"}):
            status = simulation_lab_status()

        self.assertTrue(status["enabled"])
        self.assertFalse(status["default_hidden"])
        self.assertTrue(all(experiment["state"] == "visible" for experiment in status["experiments"]))
        orb_experiment = next(experiment for experiment in status["experiments"] if experiment["id"] == "orb_backtest")
        self.assertEqual(orb_experiment["status"], "available")
        self.assertTrue(orb_experiment["runnable"])


if __name__ == "__main__":
    unittest.main()
