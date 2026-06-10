"""Behavior tests for Simulation Lab ORB backtest replay."""
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
    run_orb_backtest_replay,
    simulation_lab_status,
)


class SimulationLabOrbBacktestTests(unittest.TestCase):
    def test_orb_replay_reports_first_market_open_bullish_breakout(self):
        result = run_orb_backtest_replay(
            symbol="spy",
            session_id="market_open",
            timeframe_minutes=5,
            bars=[
                {"timestamp": "2026-06-10T09:30:00-04:00", "high": 100.0, "low": 99.0, "close": 99.5},
                {"timestamp": "2026-06-10T09:31:00-04:00", "high": 101.0, "low": 99.5, "close": 100.5},
                {"timestamp": "2026-06-10T09:34:00-04:00", "high": 100.8, "low": 100.0, "close": 100.7},
                {"timestamp": "2026-06-10T09:35:00-04:00", "high": 101.5, "low": 100.8, "close": 101.4},
                {"timestamp": "2026-06-10T09:36:00-04:00", "high": 102.0, "low": 101.2, "close": 101.8},
            ],
        )

        self.assertEqual(result["schema_version"], "edge.simulation_lab.orb_backtest.v1")
        self.assertEqual(result["symbol"], "SPY")
        self.assertEqual(result["session_id"], "market_open")
        self.assertEqual(result["timeframe_minutes"], 5)
        self.assertEqual(result["summary"]["sessions"], 1)
        self.assertEqual(result["summary"]["completed_sessions"], 1)
        self.assertEqual(result["summary"]["breakouts"], 1)
        self.assertEqual(result["summary"]["bullish_breakouts"], 1)
        self.assertEqual(result["summary"]["bearish_breakouts"], 0)
        self.assertEqual(result["days"][0]["orb_high"], 101.0)
        self.assertEqual(result["days"][0]["orb_low"], 99.0)
        self.assertEqual(result["days"][0]["breakout"]["direction"], "bullish")
        self.assertEqual(result["days"][0]["breakout"]["price"], 101.5)

    def test_orb_replay_supports_premarket_30m_session(self):
        result = run_orb_backtest_replay(
            symbol="qqq",
            session_id="premarket_30m",
            timeframe_minutes=30,
            bars=[
                {"timestamp": "2026-06-10T09:00:00-04:00", "high": 50.0, "low": 49.0, "close": 49.5},
                {"timestamp": "2026-06-10T09:15:00-04:00", "high": 51.0, "low": 48.0, "close": 50.5},
                {"timestamp": "2026-06-10T09:30:00-04:00", "high": 52.0, "low": 50.0, "close": 51.5},
            ],
        )

        self.assertEqual(result["session_id"], "premarket_30m")
        self.assertEqual(result["days"][0]["orb_high"], 51.0)
        self.assertEqual(result["days"][0]["orb_low"], 48.0)
        self.assertEqual(result["days"][0]["breakout"]["direction"], "bullish")
        self.assertEqual(result["days"][0]["breakout"]["price"], 52.0)

    def test_orb_backtest_is_runnable_only_when_lab_is_enabled(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(SIMULATION_LAB_ENV_FLAG, None)
            with self.assertRaises(SimulationLabDisabledError):
                require_simulation_lab_enabled()
            status = simulation_lab_status()
            orb_experiment = next(item for item in status["experiments"] if item["id"] == "orb_backtest")
            self.assertFalse(orb_experiment["runnable"])

        with patch.dict(os.environ, {SIMULATION_LAB_ENV_FLAG: "true"}):
            require_simulation_lab_enabled()
            status = simulation_lab_status()
            orb_experiment = next(item for item in status["experiments"] if item["id"] == "orb_backtest")
            self.assertEqual(orb_experiment["status"], "available")
            self.assertTrue(orb_experiment["runnable"])


if __name__ == "__main__":
    unittest.main()
