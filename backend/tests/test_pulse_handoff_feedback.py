"""Tests for structured Pulse handoff feedback handling."""
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pulse_client import PulseClient  # noqa: E402


class PulseHandoffFeedbackTests(unittest.TestCase):
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
