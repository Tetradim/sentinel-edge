from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from support_resistance import (  # noqa: E402
    SupportResistanceDirectiveState,
    build_support_resistance_levels,
    evaluate_support_resistance_position,
)


def _bar(timestamp: datetime, open_: float, high: float, low: float, close: float, volume: float = 1000.0):
    return {
        "timestamp": timestamp.isoformat(),
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


def _sample_bars():
    prior = datetime(2026, 6, 23, 15, 58)
    current = datetime(2026, 6, 24, 4, 0)
    bars = [
        _bar(prior, 101.0, 103.0, 99.0, 102.0),
        _bar(prior + timedelta(minutes=1), 102.0, 104.0, 100.0, 101.0),
        _bar(current, 101.0, 102.5, 100.5, 102.0),
        _bar(current.replace(hour=9, minute=30), 102.0, 104.0, 101.5, 103.5),
        _bar(current.replace(hour=9, minute=31), 103.5, 105.0, 102.8, 104.5),
        _bar(current.replace(hour=9, minute=32), 104.5, 104.8, 103.0, 103.2),
        _bar(current.replace(hour=9, minute=33), 103.2, 106.0, 102.6, 105.5),
        _bar(current.replace(hour=9, minute=34), 105.5, 105.8, 103.7, 104.0),
        _bar(current.replace(hour=9, minute=35), 104.0, 107.5, 103.9, 107.0),
        _bar(current.replace(hour=9, minute=36), 107.0, 107.2, 102.0, 102.5),
        _bar(current.replace(hour=9, minute=37), 102.5, 108.2, 101.8, 107.8),
    ]
    return bars


class SupportResistanceTests(unittest.TestCase):
    def test_build_levels_includes_seeded_and_swing_levels(self):
        result = build_support_resistance_levels(
            symbol="SPY",
            bars=_sample_bars(),
            current_price=107.8,
            settings={"opening_range_minutes": 5, "swing_window": 1},
        )

        self.assertEqual(result["schema_version"], "edge.support_resistance.levels.v1")
        self.assertEqual(result["symbol"], "SPY")
        kinds = {item["kind"] for item in result["items"]}
        self.assertIn("opening_range_high", kinds)
        self.assertIn("opening_range_low", kinds)
        self.assertIn("session_high", kinds)
        self.assertIn("session_low", kinds)
        self.assertIn("prior_day_high", kinds)
        self.assertIn("prior_day_low", kinds)
        self.assertIn("premarket_high", kinds)
        self.assertIn("premarket_low", kinds)
        self.assertIn("vwap", kinds)
        self.assertIn("atr_upper", kinds)
        self.assertIn("atr_lower", kinds)
        self.assertIn("swing_high", kinds)
        self.assertIn("swing_low", kinds)

    def test_new_intraday_high_reranks_nearest_actionable_level(self):
        older = build_support_resistance_levels(
            symbol="SPY",
            bars=_sample_bars()[:-1],
            current_price=102.5,
            settings={"opening_range_minutes": 5, "swing_window": 1},
        )
        newer = build_support_resistance_levels(
            symbol="SPY",
            bars=_sample_bars(),
            current_price=107.8,
            settings={"opening_range_minutes": 5, "swing_window": 1},
        )

        self.assertNotEqual(older["items"][0]["id"], newer["items"][0]["id"])
        self.assertEqual(newer["items"][0]["rank"], 1)
        self.assertLessEqual(newer["items"][0]["distance_pct"], newer["items"][1]["distance_pct"])

    def test_long_call_support_break_closes_position(self):
        directive = evaluate_support_resistance_position(
            position={
                "position_id": "AAPL-20260624-200-C",
                "underlying": "AAPL",
                "option_side": "call",
                "quantity": 4,
                "expiry": "2026-06-24",
                "strike": 200.0,
                "entry_price": 2.4,
            },
            levels=[
                {"id": "opening_range_low", "kind": "opening_range_low", "role": "support", "price": 198.0}
            ],
            current_price=197.8,
            settings={"break_confirmation": "tick_break"},
        )

        self.assertEqual(directive["action"], "close_position")
        self.assertEqual(directive["reason_code"], "call_support_break")
        self.assertEqual(directive["position"]["underlying"], "AAPL")
        self.assertIn("created_at", directive)
        self.assertTrue(directive["execution_hint"]["immediate"])

    def test_long_put_resistance_break_closes_position(self):
        directive = evaluate_support_resistance_position(
            position={
                "position_id": "TSLA-20260624-325-P",
                "underlying": "TSLA",
                "option_side": "put",
                "quantity": 2,
                "expiry": "2026-06-24",
                "strike": 325.0,
                "entry_price": 4.1,
            },
            levels=[
                {"id": "premarket_high", "kind": "premarket_high", "role": "resistance", "price": 330.0}
            ],
            current_price=330.25,
            settings={"break_confirmation": "tick_break"},
        )

        self.assertEqual(directive["action"], "close_position")
        self.assertEqual(directive["reason_code"], "put_resistance_break")
        self.assertTrue(directive["execution_hint"]["immediate"])

    def test_long_call_resistance_break_scales_in(self):
        directive = evaluate_support_resistance_position(
            position={
                "position_id": "NVDA-20260624-150-C",
                "underlying": "NVDA",
                "option_side": "call",
                "quantity": 8,
                "expiry": "2026-06-24",
                "strike": 150.0,
                "entry_price": 1.6,
            },
            levels=[
                {"id": "session_high", "kind": "session_high", "role": "resistance", "price": 152.0}
            ],
            current_price=152.2,
            settings={"scale_in_fraction": 0.25},
        )

        self.assertEqual(directive["action"], "request_scale_in")
        self.assertEqual(directive["reason_code"], "call_resistance_break")
        self.assertEqual(directive["sizing_hint"]["mode"], "buying_power_fraction")
        self.assertEqual(directive["sizing_hint"]["fraction"], 0.25)
        self.assertEqual(directive["sizing_hint"]["minimum_contracts"], 1)

    def test_long_put_support_break_scales_in(self):
        directive = evaluate_support_resistance_position(
            position={
                "position_id": "QQQ-20260624-500-P",
                "underlying": "QQQ",
                "option_side": "put",
                "quantity": 1,
                "expiry": "2026-06-24",
                "strike": 500.0,
                "entry_price": 3.2,
            },
            levels=[
                {"id": "prior_day_low", "kind": "prior_day_low", "role": "support", "price": 496.0}
            ],
            current_price=495.85,
            settings={"scale_in_fraction": 0.25},
        )

        self.assertEqual(directive["action"], "request_scale_in")
        self.assertEqual(directive["reason_code"], "put_support_break")
        self.assertEqual(directive["sizing_hint"]["fraction"], 0.25)

    def test_directive_id_is_deterministic_for_position_action_level_and_session(self):
        position = {
            "position_id": "NVDA-20260624-150-C",
            "underlying": "NVDA",
            "option_side": "call",
            "quantity": 8,
            "expiry": "2026-06-24",
            "strike": 150.0,
            "entry_price": 1.6,
        }
        level = {"id": "session_high", "kind": "session_high", "role": "resistance", "price": 152.0}

        first = evaluate_support_resistance_position(
            position=position,
            levels=[level],
            current_price=152.2,
            settings={"session_id": "2026-06-24-regular"},
        )
        second = evaluate_support_resistance_position(
            position=position,
            levels=[level],
            current_price=152.25,
            settings={"session_id": "2026-06-24-regular"},
        )

        self.assertEqual(first["directive_id"], second["directive_id"])
        self.assertIn("NVDA-20260624-150-C", first["directive_id"])
        self.assertIn("request_scale_in", first["directive_id"])
        self.assertIn("session_high", first["directive_id"])
        self.assertIn("2026-06-24-regular", first["directive_id"])

    def test_scale_in_state_allows_only_one_add_per_level_by_default(self):
        state = SupportResistanceDirectiveState()
        position = {
            "position_id": "NVDA-20260624-150-C",
            "underlying": "NVDA",
            "option_side": "call",
            "quantity": 8,
            "expiry": "2026-06-24",
            "strike": 150.0,
            "entry_price": 1.6,
        }
        level = {"id": "session_high", "kind": "session_high", "role": "resistance", "price": 152.0}

        first = evaluate_support_resistance_position(
            position=position,
            levels=[level],
            current_price=152.2,
            settings={"session_id": "2026-06-24-regular"},
            state=state,
        )
        second = evaluate_support_resistance_position(
            position=position,
            levels=[level],
            current_price=152.4,
            settings={"session_id": "2026-06-24-regular"},
            state=state,
        )

        self.assertIsNotNone(first)
        self.assertIsNone(second)

    def test_scale_in_state_enforces_max_adds_and_cooldown(self):
        state = SupportResistanceDirectiveState()
        position = {
            "position_id": "AAPL-20260624-200-C",
            "underlying": "AAPL",
            "option_side": "call",
            "quantity": 4,
            "expiry": "2026-06-24",
            "strike": 200.0,
            "entry_price": 2.4,
        }
        settings = {
            "session_id": "2026-06-24-regular",
            "one_scale_in_per_level": False,
            "max_scale_ins_per_position": 1,
            "scale_in_cooldown_seconds": 60,
            "now": "2026-06-24T14:30:00+00:00",
        }

        first = evaluate_support_resistance_position(
            position=position,
            levels=[{"id": "session_high", "kind": "session_high", "role": "resistance", "price": 202.0}],
            current_price=202.3,
            settings=settings,
            state=state,
        )
        second = evaluate_support_resistance_position(
            position=position,
            levels=[{"id": "swing_high_4", "kind": "swing_high", "role": "resistance", "price": 203.0}],
            current_price=203.3,
            settings={**settings, "now": "2026-06-24T14:30:30+00:00"},
            state=state,
        )
        third = evaluate_support_resistance_position(
            position=position,
            levels=[{"id": "swing_high_5", "kind": "swing_high", "role": "resistance", "price": 204.0}],
            current_price=204.3,
            settings={**settings, "max_scale_ins_per_position": 2, "now": "2026-06-24T14:31:05+00:00"},
            state=state,
        )

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertIsNotNone(third)

    def test_candle_close_break_requires_configured_confirming_closes(self):
        position = {
            "position_id": "SPY-20260624-500-P",
            "underlying": "SPY",
            "option_side": "put",
            "quantity": 1,
            "expiry": "2026-06-24",
            "strike": 500.0,
            "entry_price": 3.2,
        }
        level = {"id": "session_low", "kind": "session_low", "role": "support", "price": 496.0}
        bars = [
            _bar(datetime(2026, 6, 24, 9, 31), 497.0, 497.5, 495.8, 496.2),
            _bar(datetime(2026, 6, 24, 9, 32), 496.2, 496.5, 495.6, 495.9),
            _bar(datetime(2026, 6, 24, 9, 33), 495.9, 496.1, 495.4, 495.8),
        ]

        one_close = evaluate_support_resistance_position(
            position=position,
            levels=[level],
            current_price=495.8,
            settings={"break_confirmation": "candle_close_break", "confirming_closes": 2},
            bars=bars[:2],
        )
        two_closes = evaluate_support_resistance_position(
            position=position,
            levels=[level],
            current_price=495.8,
            settings={"break_confirmation": "candle_close_break", "confirming_closes": 2},
            bars=bars,
        )

        self.assertIsNone(one_close)
        self.assertIsNotNone(two_closes)
        self.assertEqual(two_closes["reason_code"], "put_support_break")

    def test_invalid_break_confirmation_and_close_count_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "break_confirmation"):
            evaluate_support_resistance_position(
                position={"position_id": "AAPL-1-C", "underlying": "AAPL", "option_side": "call", "quantity": 1},
                levels=[{"id": "session_high", "role": "resistance", "price": 202.0}],
                current_price=202.3,
                settings={"break_confirmation": "buffer_volume_break"},
            )

        with self.assertRaisesRegex(ValueError, "confirming_closes"):
            evaluate_support_resistance_position(
                position={"position_id": "AAPL-1-C", "underlying": "AAPL", "option_side": "call", "quantity": 1},
                levels=[{"id": "session_high", "role": "resistance", "price": 202.0}],
                current_price=202.3,
                settings={"break_confirmation": "candle_close_break", "confirming_closes": 0},
                bars=[_bar(datetime(2026, 6, 24, 9, 31), 201.0, 202.5, 200.5, 202.3)],
            )


if __name__ == "__main__":
    unittest.main()
