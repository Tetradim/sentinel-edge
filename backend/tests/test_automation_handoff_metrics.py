"""Tests for autonomous handoff Prometheus metrics."""
from pathlib import Path
import sys
import unittest

from prometheus_client import generate_latest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from automation import (  # noqa: E402
    AutomationAction,
    AutomationController,
    AutomationMode,
    AutomationSettings,
    HandoffCommand,
)


class AutomationHandoffMetricsTests(unittest.TestCase):
    def _controller(self) -> AutomationController:
        return AutomationController(settings=AutomationSettings(), state_path=Path("unused.json"))

    def _command(self, action: AutomationAction = AutomationAction.BUY) -> HandoffCommand:
        return HandoffCommand(
            symbol="AAPL",
            action=action,
            confidence=0.8,
            reason="test signal",
            mode=AutomationMode.PAPER,
        )

    def test_suppressed_handoff_records_bounded_reason_metric(self):
        controller = self._controller()

        controller.record_suppressed(self._command(), "market_closed:after_close")

        metrics = generate_latest().decode("utf-8")
        self.assertIn(
            'edge_automation_handoffs_total{action="buy",mode="paper",reason="market_closed_after_close",result="suppressed"}',
            metrics,
        )

    def test_sent_and_failed_handoffs_record_result_metrics(self):
        controller = self._controller()

        controller.record_sent(self._command(), True)
        controller.record_sent(self._command(AutomationAction.STOP_BUYING), False)

        metrics = generate_latest().decode("utf-8")
        self.assertIn(
            'edge_automation_handoffs_total{action="buy",mode="paper",reason="pulse_accepted",result="sent"}',
            metrics,
        )
        self.assertIn(
            'edge_automation_handoffs_total{action="stop_buying",mode="paper",reason="pulse_send_failed",result="failed"}',
            metrics,
        )

    def test_rejected_handoff_preserves_pulse_feedback(self):
        controller = self._controller()

        controller.record_sent(
            self._command(),
            {
                "sent": False,
                "status": "rejected",
                "reason": "risk_limit",
                "endpoint": "/api/edge/handoff",
                "status_code": 200,
                "response": {"accepted": False, "reason": "risk_limit"},
            },
        )

        self.assertFalse(controller.last_handoff["sent"])
        self.assertEqual(controller.last_handoff["handoff_status"], "rejected")
        self.assertEqual(controller.last_handoff["pulse_feedback"]["reason"], "risk_limit")

        metrics = generate_latest().decode("utf-8")
        self.assertIn(
            'edge_automation_handoffs_total{action="buy",mode="paper",reason="risk_limit",result="rejected"}',
            metrics,
        )

    def test_handoff_payload_embeds_canonical_execution_intent_metadata(self):
        command = HandoffCommand(
            symbol="aapl",
            action=AutomationAction.TRAILING_STOP,
            confidence=0.91,
            reason="bullish continuation with protected exit",
            mode=AutomationMode.PAPER,
            stop_type="trailing",
            trailing_percent=0.75,
            metadata={"price": 123.45},
        )

        payload = command.payload()
        intent = payload["metadata"]["execution_intent"]

        self.assertEqual("edge.pulse.handoff.v1", payload["contract_version"])
        self.assertNotIn("target_bot", payload)
        self.assertEqual("edge.execution_intent.v1", intent["contract_version"])
        self.assertEqual(command.idempotency_key, intent["intent_id"])
        self.assertEqual("sentinel-edge", intent["source_bot"])
        self.assertEqual("sentinel-pulse", intent["target_bot"])
        self.assertEqual("AAPL", intent["symbol"])
        self.assertEqual("trailing_stop", intent["action"])
        self.assertEqual("paper", intent["mode"])
        self.assertEqual("bullish continuation with protected exit", intent["reason"])
        self.assertEqual(command.idempotency_key, intent["idempotency_key"])
        self.assertEqual({"type": "edge_runtime_policy"}, intent["quantity_policy"])
        self.assertEqual({"type": "trailing", "trailing_percent": 0.75}, intent["trailing_policy"])
        self.assertIsNone(intent["max_notional"])
        self.assertIsNone(intent["expires_at"])
        self.assertEqual(123.45, payload["metadata"]["price"])


if __name__ == "__main__":
    unittest.main()
