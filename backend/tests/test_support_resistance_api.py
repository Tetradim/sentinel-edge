from datetime import datetime, timedelta
from pathlib import Path
import os
import sys
import tempfile
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server import api_router  # noqa: E402
from shared.bot_event_bus import event_bus  # noqa: E402


def _bar(timestamp: datetime, open_: float, high: float, low: float, close: float, volume: float = 1000.0):
    return {
        "timestamp": timestamp.isoformat(),
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


def _bars():
    current = datetime(2026, 6, 24, 9, 30)
    return [
        _bar(current - timedelta(days=1), 99.0, 101.0, 98.0, 100.0),
        _bar(current, 100.0, 101.0, 99.2, 100.8),
        _bar(current + timedelta(minutes=1), 100.8, 102.0, 100.2, 101.7),
        _bar(current + timedelta(minutes=2), 101.7, 102.4, 100.7, 101.0),
        _bar(current + timedelta(minutes=3), 101.0, 103.2, 100.8, 103.0),
    ]


def _client():
    app = FastAPI()
    app.include_router(api_router)
    return TestClient(app)


class SupportResistanceApiTests(unittest.TestCase):
    def test_evaluate_endpoint_returns_levels_and_directive(self):
        response = _client().post(
            "/api/support-resistance/evaluate",
            json={
                "symbol": "SPY",
                "bars": _bars(),
                "current_price": 103.4,
                "position": {
                    "position_id": "SPY-20260624-103-C",
                    "underlying": "SPY",
                    "option_side": "call",
                    "quantity": 2,
                    "expiry": "2026-06-24",
                    "strike": 103.0,
                    "entry_price": 1.3,
                },
                "settings": {"opening_range_minutes": 5},
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["schema_version"], "edge.support_resistance.evaluation.v1")
        self.assertEqual(body["symbol"], "SPY")
        self.assertGreater(len(body["levels"]["items"]), 0)
        self.assertEqual(body["directive"]["schema_version"], "edge.sr.directive.v1")
        self.assertEqual(body["directive"]["action"], "request_scale_in")

    def test_evaluate_endpoint_can_emit_consolidation_directive_event(self):
        previous_event_dir = os.environ.get("BOT_EVENT_BUS_DIR")
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["BOT_EVENT_BUS_DIR"] = temp_dir
            response = _client().post(
                "/api/support-resistance/evaluate",
                json={
                    "symbol": "QQQ",
                    "bars": _bars(),
                    "current_price": 97.8,
                    "emit_event": True,
                    "position": {
                        "position_id": "QQQ-20260624-498-C",
                        "underlying": "QQQ",
                        "option_side": "call",
                        "quantity": 3,
                        "expiry": "2026-06-24",
                        "strike": 498.0,
                        "entry_price": 2.2,
                    },
                    "levels": [
                        {
                            "id": "opening_range_low",
                            "kind": "opening_range_low",
                            "role": "support",
                            "price": 98.0,
                        }
                    ],
                },
            )
            events = event_bus.recent(event_type="edge.sr.directive.v1")

        if previous_event_dir is None:
            os.environ.pop("BOT_EVENT_BUS_DIR", None)
        else:
            os.environ["BOT_EVENT_BUS_DIR"] = previous_event_dir

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["directive"]["action"], "close_position")
        self.assertIsNotNone(body["event"])
        self.assertEqual(events[0]["event_type"], "edge.sr.directive.v1")
        self.assertEqual(events[0]["target_bots"], ["consolidation"])
        self.assertEqual(events[0]["payload"]["action"], "close_position")


if __name__ == "__main__":
    unittest.main()
