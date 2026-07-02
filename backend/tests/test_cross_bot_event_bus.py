"""Tests for the Cross Bot Event Bus contract."""
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _request(headers: dict[str, str] | None = None) -> Request:
    encoded_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/bus/edge-actions",
            "headers": encoded_headers,
        }
    )


class CrossBotEventBusTests(unittest.TestCase):
    def test_store_publishes_and_reads_recent_edge_actions(self):
        from shared.bot_event_bus import BotEvent, EventBusStore

        with tempfile.TemporaryDirectory() as temp_dir:
            store = EventBusStore(Path(temp_dir))
            published = store.publish(
                BotEvent(
                    event_type="edge.action",
                    source_bot="sentinel-edge",
                    target_bots=["sentinel-pulse"],
                    correlation_id="edge:SPY:stop_buying:market_open:123:test",
                    dedupe_key="edge:SPY:stop_buying:market_open:123:test",
                    payload={
                        "contract_version": "edge.action.v1",
                        "symbol": "SPY",
                        "action": "stop_buying",
                    },
                )
            )

            recent = store.recent(event_type="edge.action")

        self.assertEqual(recent[0]["event_id"], published.event_id)
        self.assertEqual(recent[0]["payload"]["action"], "stop_buying")
        self.assertEqual(recent[0]["target_bots"], ["sentinel-pulse"])

    def test_edge_action_payload_preserves_handoff_context(self):
        from shared.bot_event_bus import build_edge_action_event_payload

        payload = build_edge_action_event_payload(
            {
                "symbol": "SPY",
                "action": "stop_buying",
                "confidence": 0.92,
                "reason": "Bearish ORB/signal risk",
                "mode": "paper",
                "orb_session": "market_open",
                "idempotency_key": "edge:SPY:stop_buying:market_open:123:test",
                "created_at": 1760000000.0,
                "metadata": {"trend": "bearish"},
            },
            feedback={"sent": False, "status": "suppressed"},
        )

        self.assertEqual(payload["contract_version"], "edge.action.v1")
        self.assertEqual(payload["symbol"], "SPY")
        self.assertEqual(payload["action"], "stop_buying")
        self.assertEqual(payload["metadata"]["trend"], "bearish")
        self.assertEqual(payload["pulse_feedback"]["status"], "suppressed")

    def test_manual_edge_action_route_fails_closed_without_operator_secret(self):
        from bot_event_bus_routes import publish_edge_action
        import asyncio

        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": ""}):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    publish_edge_action(
                        _request(),
                        {
                            "symbol": "QQQ",
                            "action": "tighten_trailing_stop",
                            "confidence": 0.88,
                            "idempotency_key": "edge:QQQ:tighten_trailing_stop:market_open:123:test",
                        },
                    )
                )

        self.assertEqual(503, raised.exception.status_code)
        self.assertIn("EDGE_OPERATOR_ACTION_SECRET", raised.exception.detail)

    def test_manual_edge_action_route_rejects_wrong_operator_secret(self):
        from bot_event_bus_routes import publish_edge_action
        import asyncio

        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    publish_edge_action(
                        _request({"X-Edge-Operator-Secret": "wrong-secret"}),
                        {
                            "symbol": "QQQ",
                            "action": "tighten_trailing_stop",
                            "confidence": 0.88,
                            "idempotency_key": "edge:QQQ:tighten_trailing_stop:market_open:123:test",
                        },
                    )
                )

        self.assertEqual(401, raised.exception.status_code)

    def test_manual_edge_action_route_publishes_event_with_operator_secret(self):
        old_event_dir = os.environ.get("BOT_EVENT_BUS_DIR")
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["BOT_EVENT_BUS_DIR"] = temp_dir
            from bot_event_bus_routes import publish_edge_action
            import asyncio

            with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
                result = asyncio.run(
                    publish_edge_action(
                        _request({"X-Edge-Operator-Secret": "correct-secret"}),
                        {
                            "symbol": "QQQ",
                            "action": "tighten_trailing_stop",
                            "confidence": 0.88,
                            "idempotency_key": "edge:QQQ:tighten_trailing_stop:market_open:123:test",
                        },
                    )
                )

        if old_event_dir is None:
            os.environ.pop("BOT_EVENT_BUS_DIR", None)
        else:
            os.environ["BOT_EVENT_BUS_DIR"] = old_event_dir

        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["event"]["event_type"], "edge.action")
        self.assertEqual(result["event"]["payload"]["symbol"], "QQQ")
        self.assertIn("sentinel-pulse", result["event"]["target_bots"])
        self.assertNotIn("sentinel-chain", result["event"]["target_bots"])
        self.assertNotIn("sentinel-flare", result["event"]["target_bots"])

    def test_generic_event_publish_route_requires_operator_secret(self):
        from bot_event_bus_routes import publish_bot_event
        from shared.bot_event_bus import BotEvent
        import asyncio

        event = BotEvent(
            event_type="edge.action",
            source_bot="manual-test",
            target_bots=["sentinel-pulse"],
            payload={"symbol": "SPY", "action": "buy"},
        )

        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    publish_bot_event(
                        _request({"X-Edge-Operator-Secret": "wrong-secret"}),
                        event,
                    )
                )

        self.assertEqual(401, raised.exception.status_code)


if __name__ == "__main__":
    unittest.main()
