"""Behavior tests for explicit ORB session tracking."""
from datetime import datetime
from pathlib import Path
import sys
import unittest
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orb import ORBTracker  # noqa: E402


ET = ZoneInfo("America/New_York")


class ORBSessionModelTests(unittest.TestCase):
    def test_premarket_and_market_open_sessions_are_tracked_separately(self):
        tracker = ORBTracker()

        tracker.update("SPY", 100.0, datetime(2026, 6, 10, 9, 5, tzinfo=ET))
        tracker.update("SPY", 101.0, datetime(2026, 6, 10, 9, 20, tzinfo=ET))
        tracker.update("SPY", 102.0, datetime(2026, 6, 10, 9, 31, tzinfo=ET))

        sessions = tracker.get_session_levels("SPY")
        self.assertIn("premarket_30m", sessions)
        self.assertIn("market_open", sessions)

        premarket = sessions["premarket_30m"][30]
        self.assertEqual(premarket.session_id, "premarket_30m")
        self.assertTrue(premarket.locked)
        self.assertEqual(premarket.high, 101.0)
        self.assertEqual(premarket.low, 100.0)

        market_open = sessions["market_open"][5]
        self.assertEqual(market_open.session_id, "market_open")
        self.assertFalse(market_open.locked)
        self.assertEqual(market_open.high, 102.0)
        self.assertEqual(market_open.low, 102.0)

        legacy_levels = tracker.get_levels("SPY")
        self.assertIs(legacy_levels, sessions["market_open"])

    def test_session_status_exposes_configured_sessions_and_active_market_open(self):
        tracker = ORBTracker()
        tracker.update("SPY", 100.0, datetime(2026, 6, 10, 9, 5, tzinfo=ET))

        status = tracker.get_session_status("SPY", now=datetime(2026, 6, 10, 9, 35, tzinfo=ET))

        self.assertEqual(status["active_session"], "market_open")
        self.assertEqual(status["active_label"], "Market open ORB")
        self.assertIn("premarket_30m", status["sessions"])
        self.assertIn("market_open", status["sessions"])
        self.assertEqual(status["sessions"]["premarket_30m"]["timeframes"], ["30m"])
        self.assertEqual(status["sessions"]["market_open"]["timeframes"], ["5m", "15m", "30m"])

    def test_decision_context_captures_signal_and_reference_orb_sessions(self):
        tracker = ORBTracker()

        tracker.update("SPY", 100.0, datetime(2026, 6, 10, 9, 5, tzinfo=ET))
        tracker.update("SPY", 101.0, datetime(2026, 6, 10, 9, 20, tzinfo=ET))
        tracker.update("SPY", 102.0, datetime(2026, 6, 10, 9, 31, tzinfo=ET))

        context = tracker.get_decision_context("SPY", now=datetime(2026, 6, 10, 9, 35, tzinfo=ET))

        self.assertEqual(context["active_session"], "market_open")
        self.assertEqual(context["signal_session"], "market_open")
        self.assertEqual(context["signal_timeframe"], "15m")
        self.assertEqual(context["signal_level"]["high"], 102.0)
        self.assertEqual(context["signal_level"]["low"], 102.0)
        self.assertTrue(context["signal_level"]["is_valid"])
        self.assertEqual(context["reference_sessions"]["premarket_30m"]["30m"]["high"], 101.0)
        self.assertEqual(context["reference_sessions"]["premarket_30m"]["30m"]["low"], 100.0)


if __name__ == "__main__":
    unittest.main()
