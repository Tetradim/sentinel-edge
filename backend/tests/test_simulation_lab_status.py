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
