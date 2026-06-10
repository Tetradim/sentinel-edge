"""Tests for structured Pulse handoff feedback handling."""
import asyncio
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pulse_client import PulseClient  # noqa: E402


class PulseHandoffFeedbackTests(unittest.TestCase):
    def test_invalid_handoff_payload_is_suppressed_before_transport(self):
        async def run():
            client = PulseClient(base_url="http://pulse.invalid")
            client.pulse_available = True
            client.send_decision = AsyncMock(return_value=True)
            try:
                result = await client.send_handoff_command(
                    {
                        "symbol": "AAPL",
                        "action": "buy",
                        "confidence": 0.8,
                        "reason": "test",
                        "mode": "recommend_only",
                        "orb_session": "market_open",
                        "idempotency_key": "edge:AAPL:buy:test",
                        "source": "sentinel_edge",
                        "created_at": 1760000000.0,
                        "metadata": {},
                    }
                )
                return result, client.send_decision.await_count
            finally:
                await client.aclose()

        with self.assertLogs("pulse_client", level="WARNING"):
            result, send_count = asyncio.run(run())

        self.assertFalse(result["sent"])
        self.assertEqual(result["status"], "suppressed")
        self.assertEqual(result["reason"], "invalid_handoff_contract")
        self.assertEqual(send_count, 0)

    def test_invalid_handoff_feedback_validation_errors_are_json_safe(self):
        async def run():
            client = PulseClient(base_url="http://pulse.invalid")
            client.pulse_available = True
            client.send_decision = AsyncMock(return_value=True)
            try:
                return await client.send_handoff_command(
                    {
                        "symbol": "AAPL",
                        "action": "trailing_stop",
                        "confidence": 0.8,
                        "reason": "test",
                        "mode": "paper",
                        "orb_session": "market_open",
                        "stop_type": "trailing",
                        "idempotency_key": "edge:AAPL:trailing_stop:test",
                        "source": "sentinel_edge",
                        "created_at": 1760000000.0,
                        "metadata": {},
                    }
                )
            finally:
                await client.aclose()

        with self.assertLogs("pulse_client", level="WARNING"):
            result = asyncio.run(run())

        self.assertEqual(result["reason"], "invalid_handoff_contract")
        self.assertIn("validation_errors", result)
        try:
            json.dumps(result["validation_errors"])
        except TypeError as exc:
            self.fail(f"validation_errors must be JSON serializable: {exc}")

    def test_acceptance_feedback_preserves_pulse_response(self):
        result = PulseClient.normalise_handoff_feedback(
            endpoint="/api/edge/handoff",
            status_code=202,
            response_body={"accepted": True, "handoff_id": "ph-123"},
        )

        self.assertTrue(result["sent"])
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["reason"], "pulse_accepted")
        self.assertEqual(result["endpoint"], "/api/edge/handoff")
        self.assertEqual(result["status_code"], 202)
        self.assertEqual(result["response"]["handoff_id"], "ph-123")

    def test_rejection_feedback_preserves_rejection_reason(self):
        result = PulseClient.normalise_handoff_feedback(
            endpoint="/api/edge/handoff",
            status_code=200,
            response_body={"accepted": False, "reason": "risk_limit", "message": "Buying power exhausted"},
        )

        self.assertFalse(result["sent"])
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["reason"], "risk_limit")
        self.assertEqual(result["response"]["message"], "Buying power exhausted")

    def test_failed_status_is_not_treated_as_rejection(self):
        result = PulseClient.normalise_handoff_feedback(
            endpoint="/api/edge/handoff",
            status_code=200,
            response_body={"status": "failed", "error": "schema_mismatch"},
        )

        self.assertFalse(result["sent"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["reason"], "schema_mismatch")

    def test_legacy_payload_preserves_stop_trail_and_dca_fields(self):
        payload = {
            "reason": "scale in",
            "confidence": 0.9,
            "idempotency_key": "edge:AAPL:dca:test",
            "source": "sentinel_edge",
            "mode": "paper",
            "orb_session": "market_open",
            "stop_type": "trailing",
            "trailing_percent": 1.25,
            "dca": {"steps": 2, "interval_seconds": 60},
            "metadata": {"source": "test"},
        }

        legacy = PulseClient.legacy_handoff_payload(payload)

        self.assertEqual(legacy["stop_type"], "trailing")
        self.assertEqual(legacy["trailing_percent"], 1.25)
        self.assertEqual(legacy["dca"], {"steps": 2, "interval_seconds": 60})


if __name__ == "__main__":
    unittest.main()
