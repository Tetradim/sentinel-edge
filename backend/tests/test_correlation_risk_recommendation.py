"""Tests for correlation risk recommendation payloads."""

import asyncio
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from correlation import CorrelationEngine


class CorrelationRiskRecommendationTests(unittest.TestCase):
    def test_high_strength_bearish_cluster_recommends_global_trailing_tighten(self):
        engine = CorrelationEngine(
            db=None,
            pulse_overrides_enabled=False,
            window_sec=120,
            min_symbols=3,
            cooldown_sec=300,
        )

        for symbol in ["SPY", "QQQ", "NVDA", "AAPL", "TSLA", "AMZN"]:
            asyncio.run(engine.record_signal(symbol, "SELL", 0.9))

        cluster = engine.get_latest_cluster()

        self.assertIsNotNone(cluster)
        self.assertEqual(len(engine.get_recent_clusters()), 1)
        self.assertEqual(cluster["count"], 6)
        self.assertNotIn("_cooldown_update", cluster)
        recommendation = cluster["risk_recommendation"]
        self.assertEqual(recommendation["action"], "tighten_trailing_global")
        self.assertEqual(recommendation["priority"], "high")
        self.assertEqual(recommendation["scope"], "global")
        self.assertEqual(recommendation["trailing_stop_action"], "tighten")
        self.assertIn("pause new long entries", recommendation["operator_summary"])

    def test_medium_bearish_cluster_recommends_symbol_trailing_review(self):
        engine = CorrelationEngine(
            db=None,
            pulse_overrides_enabled=False,
            window_sec=120,
            min_symbols=3,
            cooldown_sec=300,
        )

        for symbol in ["SPY", "QQQ", "NVDA"]:
            asyncio.run(engine.record_signal(symbol, "STOP_BUYING", 0.8))

        cluster = engine.get_latest_cluster()

        self.assertIsNotNone(cluster)
        recommendation = cluster["risk_recommendation"]
        self.assertEqual(recommendation["action"], "review_trailing_stops")
        self.assertEqual(recommendation["priority"], "medium")
        self.assertEqual(recommendation["scope"], "cluster_symbols")
        self.assertEqual(recommendation["trailing_stop_action"], "review")

    def test_bullish_cluster_recommends_observation_without_stop_change(self):
        engine = CorrelationEngine(
            db=None,
            pulse_overrides_enabled=False,
            window_sec=120,
            min_symbols=3,
            cooldown_sec=300,
        )

        for symbol in ["SPY", "QQQ", "NVDA"]:
            asyncio.run(engine.record_signal(symbol, "BUY", 0.8))

        cluster = engine.get_latest_cluster()

        self.assertIsNotNone(cluster)
        recommendation = cluster["risk_recommendation"]
        self.assertEqual(recommendation["action"], "observe_momentum")
        self.assertEqual(recommendation["priority"], "low")
        self.assertEqual(recommendation["scope"], "watchlist")
        self.assertEqual(recommendation["trailing_stop_action"], "maintain")


if __name__ == "__main__":
    unittest.main()
