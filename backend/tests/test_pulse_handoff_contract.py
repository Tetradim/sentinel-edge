"""Tests for the Edge -> Pulse structured handoff request contract."""
from pathlib import Path
import sys
import unittest

from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.handoff import PulseHandoffRequest, pulse_handoff_contract_document  # noqa: E402


def valid_payload(**overrides):
    payload = {
        "symbol": "aapl",
        "action": "buy",
        "confidence": 0.875,
        "reason": "Bullish ORB/signal confluence",
        "mode": "paper",
        "orb_session": "market_open",
        "stop_type": None,
        "trailing_percent": None,
        "dca": None,
        "idempotency_key": "edge:AAPL:buy:market_open:123:test",
        "source": "sentinel_edge",
        "created_at": 1760000000.0,
        "metadata": {"signal_strength": 8.75},
    }
    payload.update(overrides)
    return payload


class PulseHandoffContractTests(unittest.TestCase):
    def test_contract_normalises_paper_handoff_payload(self):
        request = PulseHandoffRequest.from_edge_payload(valid_payload())

        payload = request.model_dump(mode="json", exclude_none=True)

        self.assertEqual(payload["contract_version"], "edge.pulse.handoff.v1")
        self.assertEqual(payload["symbol"], "AAPL")
        self.assertEqual(payload["action"], "buy")
        self.assertEqual(payload["mode"], "paper")
        self.assertEqual(payload["idempotency_key"], "edge:AAPL:buy:market_open:123:test")
        self.assertEqual(payload["source"], "sentinel_edge")
        self.assertEqual(payload["metadata"]["signal_strength"], 8.75)

    def test_contract_rejects_recommend_only_mode(self):
        with self.assertRaises(ValidationError) as ctx:
            PulseHandoffRequest.from_edge_payload(valid_payload(mode="recommend_only"))

        self.assertIn("mode", str(ctx.exception))

    def test_contract_requires_idempotency_key(self):
        with self.assertRaises(ValidationError) as ctx:
            PulseHandoffRequest.from_edge_payload(valid_payload(idempotency_key=""))

        self.assertIn("idempotency_key", str(ctx.exception))

    def test_trailing_handoff_requires_positive_trailing_percent(self):
        with self.assertRaises(ValidationError) as ctx:
            PulseHandoffRequest.from_edge_payload(
                valid_payload(action="trailing_stop", stop_type="trailing", trailing_percent=None)
            )

        self.assertIn("trailing_percent", str(ctx.exception))

    def test_dca_handoff_requires_and_preserves_dca_plan(self):
        with self.assertRaises(ValidationError) as ctx:
            PulseHandoffRequest.from_edge_payload(valid_payload(action="dca", dca=None))
        self.assertIn("dca", str(ctx.exception))

        request = PulseHandoffRequest.from_edge_payload(
            valid_payload(
                action="dca",
                dca={"steps": 2, "interval_seconds": 60, "allocation_pct": 25.0},
            )
        )

        payload = request.model_dump(mode="json", exclude_none=True)
        self.assertEqual(payload["dca"]["steps"], 2)
        self.assertEqual(payload["dca"]["interval_seconds"], 60)
        self.assertEqual(payload["dca"]["allocation_pct"], 25.0)

    def test_contract_document_exposes_request_and_response_shapes(self):
        document = pulse_handoff_contract_document()

        self.assertEqual(document["contract_version"], "edge.pulse.handoff.v1")
        self.assertEqual(document["endpoint_env"], "PULSE_HANDOFF_ENDPOINT")
        self.assertEqual(document["recommended_endpoint"], "/api/edge/handoff")
        self.assertIn("request_schema", document)
        self.assertIn("response_contract", document)
        self.assertIn("transport_headers", document)
        self.assertIn("Idempotency-Key", document["transport_headers"])
        self.assertIn("X-Edge-Mode", document["transport_headers"])
        self.assertIn("X-Edge-Contract-Version", document["transport_headers"])
        self.assertIn("accepted_response", document["response_contract"])
        self.assertIn("rejected_response", document["response_contract"])
        self.assertIn("idempotency_key", document["request_schema"]["properties"])
        self.assertIn("trailing_percent", document["request_schema"]["properties"])
        self.assertIn("dca", document["request_schema"]["properties"])


if __name__ == "__main__":
    unittest.main()
