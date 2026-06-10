"""Behavior tests for Scanner Workbench watch-intent validation."""
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scanner_workbench_catalog import validate_scanner_watch_intent  # noqa: E402


class ScannerWorkbenchWatchIntentTests(unittest.TestCase):
    def test_validation_sanitizes_stale_ids_and_reports_invalid_entries(self):
        result = validate_scanner_watch_intent(
            {
                "scanners": ["orb_volume_gap_breakout", "missing_scanner", "orb_volume_gap_breakout"],
                "tickers": ["SPY", "BADTICKER"],
                "strategies": ["orb_momentum_continuation", "missing_strategy"],
                "indicators": ["opening_range", "missing_indicator"],
                "collections": ["legacy_collection_tab"],
            }
        )

        self.assertEqual(result["schema_version"], "edge.scanner_workbench.watch_intent_validation.v1")
        self.assertEqual(result["catalog_schema_version"], "edge.scanner_workbench.v1")
        self.assertFalse(result["valid"])
        self.assertEqual(result["invalid_count"], 4)
        self.assertEqual(result["ignored_fields"], ["collections"])
        self.assertEqual(result["sanitized_intent"]["scanners"], ["orb_volume_gap_breakout"])
        self.assertEqual(result["sanitized_intent"]["tickers"], ["SPY"])
        self.assertEqual(result["sanitized_intent"]["strategies"], ["orb_momentum_continuation"])
        self.assertEqual(result["sanitized_intent"]["indicators"], ["opening_range"])
        self.assertEqual(result["invalid_selections"]["scanners"], ["missing_scanner"])
        self.assertEqual(result["invalid_selections"]["tickers"], ["BADTICKER"])
        self.assertEqual(result["invalid_selections"]["strategies"], ["missing_strategy"])
        self.assertEqual(result["invalid_selections"]["indicators"], ["missing_indicator"])

    def test_validation_accepts_empty_watch_intent(self):
        result = validate_scanner_watch_intent({})

        self.assertTrue(result["valid"])
        self.assertEqual(result["selected_count"], 0)
        self.assertEqual(result["invalid_count"], 0)
        self.assertEqual(result["sanitized_intent"]["scanners"], [])
        self.assertEqual(result["sanitized_intent"]["tickers"], [])
        self.assertEqual(result["sanitized_intent"]["strategies"], [])
        self.assertEqual(result["sanitized_intent"]["indicators"], [])

    def test_validation_expands_strategy_dependencies_for_bot_watch_plan(self):
        result = validate_scanner_watch_intent({"strategies": ["squeeze_entry_long_1h"]})

        self.assertTrue(result["valid"])
        self.assertEqual(result["sanitized_intent"]["strategies"], ["squeeze_entry_long_1h"])
        self.assertEqual(result["sanitized_intent"]["scanners"], [])
        self.assertEqual(result["sanitized_intent"]["indicators"], [])
        self.assertEqual(result["expanded_intent"]["strategies"], ["squeeze_entry_long_1h"])
        self.assertEqual(
            result["expanded_intent"]["scanners"],
            ["bb_kc_squeeze_anchored_vwap", "current_bullish_momentum"],
        )
        self.assertEqual(
            result["expanded_intent"]["indicators"],
            ["atr", "bollinger_bands", "keltner_channels", "relative_volume"],
        )
        self.assertEqual(result["expanded_counts"]["scanners"], 2)
        self.assertEqual(result["expanded_counts"]["indicators"], 4)


if __name__ == "__main__":
    unittest.main()
