"""Behavior tests for Chart Workspace snapshot payloads."""
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chart_workspace import build_chart_workspace_payload  # noqa: E402


class ChartWorkspacePayloadTests(unittest.TestCase):
    def test_payload_computes_indicator_series_and_orb_overlays(self):
        result = build_chart_workspace_payload(
            symbol="spy",
            bars=[
                {"timestamp": "2026-06-09T13:30:00Z", "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.0, "volume": 1000},
                {"timestamp": "2026-06-09T13:31:00Z", "open": 10.0, "high": 11.5, "low": 9.9, "close": 11.0, "volume": 1100},
                {"timestamp": "2026-06-09T13:32:00Z", "open": 11.0, "high": 12.5, "low": 10.8, "close": 12.0, "volume": 1200},
                {"timestamp": "2026-06-09T13:33:00Z", "open": 12.0, "high": 13.5, "low": 11.8, "close": 13.0, "volume": 1300},
                {"timestamp": "2026-06-09T13:34:00Z", "open": 13.0, "high": 14.5, "low": 12.8, "close": 14.0, "volume": 1400},
            ],
            indicators=["ema_3", "sma_3", "rsi_3", "macd"],
            limit=4,
            orb_status={
                "active_session": "market_open",
                "active_label": "Market open ORB",
                "active_status": "locked",
                "sessions": {
                    "market_open": {
                        "label": "Market open ORB",
                        "levels": {
                            "30m": {
                                "high": 14.5,
                                "low": 9.5,
                                "range_width": 5.0,
                                "locked": True,
                                "is_valid": True,
                                "date": "2026-06-09",
                            }
                        },
                    }
                }
            },
        )

        self.assertEqual(result["schema_version"], "edge.chart_workspace.snapshot.v1")
        self.assertEqual(result["symbol"], "SPY")
        self.assertEqual(result["summary"]["bar_count"], 4)
        self.assertEqual(result["bars"][0]["close"], 11.0)
        self.assertEqual(result["bars"][-1]["timestamp"], "2026-06-09T09:34:00-04:00")

        self.assertEqual(result["indicators"]["sma_3"]["points"][-1]["value"], 13.0)
        self.assertEqual(result["indicators"]["ema_3"]["points"][-1]["value"], 13.0625)
        self.assertEqual(result["indicators"]["rsi_3"]["points"][-1]["value"], 100.0)
        self.assertIn("histogram", result["indicators"]["macd"]["points"][-1])

        self.assertEqual(result["orb_overlays"][0]["session_id"], "market_open")
        self.assertEqual(result["orb_overlays"][0]["timeframe"], "30m")
        self.assertEqual(result["orb_overlays"][0]["high"], 14.5)
        self.assertEqual(result["orb_overlays"][0]["low"], 9.5)
        self.assertEqual(result["orb_session_status"]["active_session"], "market_open")
        self.assertEqual(result["orb_session_status"]["active_label"], "Market open ORB")
        self.assertEqual(result["orb_session_status"]["active_status"], "locked")

    def test_payload_rejects_unknown_indicators(self):
        with self.assertRaises(ValueError):
            build_chart_workspace_payload(
                symbol="SPY",
                bars=[
                    {"timestamp": "2026-06-09T13:30:00Z", "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.0},
                ],
                indicators=["vwap"],
            )


if __name__ == "__main__":
    unittest.main()
