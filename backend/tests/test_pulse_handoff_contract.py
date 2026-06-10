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

    def test_contract_restricts_handoff_session_contexts_to_known_edge_values(self):
        for orb_session in ("premarket_30m", "market_open", "puzzle_key"):
            with self.subTest(orb_session=orb_session):
                request = PulseHandoffRequest.from_edge_payload(valid_payload(orb_session=orb_session))
                self.assertEqual(request.model_dump(mode="json", exclude_none=True)["orb_session"], orb_session)

        for orb_session in ("", "unknown_session"):
            with self.subTest(orb_session=orb_session):
                with self.assertRaises(ValidationError) as ctx:
                    PulseHandoffRequest.from_edge_payload(valid_payload(orb_session=orb_session))
                self.assertIn("orb_session", str(ctx.exception))

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

    def test_stop_handoffs_require_matching_stop_type(self):
        stop_cases = [
            ("regular_stop", "regular", {}),
            ("trailing_stop", "trailing", {"trailing_percent": 1.25}),
            ("tighten_stop", "tighten", {}),
            ("tighten_trailing_stop", "tighten_trailing", {"trailing_percent": 0.5}),
        ]

        for action, stop_type, extras in stop_cases:
            with self.subTest(action=action, case="missing_stop_type"):
                with self.assertRaises(ValidationError) as ctx:
                    PulseHandoffRequest.from_edge_payload(valid_payload(action=action, stop_type=None, **extras))
                self.assertIn("stop_type", str(ctx.exception))

            wrong_stop_type = "regular" if stop_type != "regular" else "trailing"
            with self.subTest(action=action, case="wrong_stop_type"):
                with self.assertRaises(ValidationError) as ctx:
                    PulseHandoffRequest.from_edge_payload(
                        valid_payload(action=action, stop_type=wrong_stop_type, **extras)
                    )
                self.assertIn(stop_type, str(ctx.exception))

            request = PulseHandoffRequest.from_edge_payload(
                valid_payload(action=action, stop_type=stop_type, **extras)
            )
            self.assertEqual(request.model_dump(mode="json", exclude_none=True)["stop_type"], stop_type)

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

    def test_contract_document_exposes_field_semantics_for_pulse_acceptance(self):
        document = pulse_handoff_contract_document()

        self.assertIn("field_semantics", document)
        self.assertIn("feedback_semantics", document)
        field_semantics = document["field_semantics"]
        self.assertTrue(field_semantics["idempotency_key"]["required"])
        self.assertEqual(field_semantics["idempotency_key"]["transport_header"], "Idempotency-Key")
        self.assertIn("action", field_semantics["idempotency_key"]["dedupe_scope"])
        self.assertEqual(field_semantics["mode"]["allowed_values"], ["paper", "live"])
        self.assertEqual(field_semantics["mode"]["recommend_only_semantics"], "suppressed_by_edge")
        self.assertIn("trailing_percent", field_semantics["action"]["conditional_fields"]["trailing_stop"])
        self.assertIn("stop_type", field_semantics["action"]["conditional_fields"]["regular_stop"])
        self.assertIn("stop_type", field_semantics["action"]["conditional_fields"]["tighten_stop"])
        self.assertIn("stop_type", field_semantics["action"]["conditional_fields"]["tighten_trailing_stop"])
        self.assertIn("dca", field_semantics["action"]["conditional_fields"]["dca"])
        self.assertEqual(field_semantics["trailing_percent"]["unit"], "percent")
        self.assertIn("action=regular_stop", field_semantics["stop_type"]["required_when"])
        self.assertIn("action=tighten_stop", field_semantics["stop_type"]["required_when"])
        self.assertIn("action=dca", field_semantics["dca"]["required_when"])

        feedback_semantics = document["feedback_semantics"]
        self.assertEqual(feedback_semantics["accepted"]["edge_sent"], True)
        self.assertEqual(feedback_semantics["rejected"]["edge_sent"], False)
        self.assertEqual(feedback_semantics["failed"]["edge_sent"], False)

    def test_contract_document_distinguishes_orb_sessions_from_strategy_contexts(self):
        document = pulse_handoff_contract_document()
        orb_session_semantics = document["field_semantics"]["orb_session"]

        self.assertEqual(orb_session_semantics["known_orb_session_values"], ["premarket_30m", "market_open"])
        self.assertNotIn("puzzle_key", orb_session_semantics["known_orb_session_values"])
        self.assertIn("puzzle_key", orb_session_semantics["strategy_context_values"])
        self.assertIn("non-ORB", orb_session_semantics["strategy_context_values"]["puzzle_key"])


if __name__ == "__main__":
    unittest.main()
