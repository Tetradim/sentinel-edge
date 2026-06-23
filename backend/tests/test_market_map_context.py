from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chart_workspace import build_market_map_context  # noqa: E402


class MarketMapContextTests(unittest.TestCase):
    def test_context_blocks_when_levels_are_missing(self):
        result = build_market_map_context(symbol="SPY", latest_price=100.0, levels=[])

        self.assertEqual(result["schema_version"], "edge.market_map.context.v1")
        self.assertEqual(result["status"], "block")
        self.assertIn("No Market Map levels available", result["reasons"])

    def test_context_reviews_when_price_is_far_from_vwap(self):
        result = build_market_map_context(
            symbol="SPY",
            latest_price=110.0,
            levels=[{"kind": "vwap", "label": "VWAP", "price": 100.0}],
        )

        self.assertEqual(result["status"], "review")
        self.assertIn("Price is extended from VWAP", result["reasons"])

    def test_context_accepts_when_price_is_near_vwap(self):
        result = build_market_map_context(
            symbol="SPY",
            latest_price=100.25,
            levels=[{"kind": "vwap", "label": "VWAP", "price": 100.0}],
        )

        self.assertEqual(result["status"], "pass")
        self.assertIn("Price is near VWAP", result["reasons"])


if __name__ == "__main__":
    unittest.main()
