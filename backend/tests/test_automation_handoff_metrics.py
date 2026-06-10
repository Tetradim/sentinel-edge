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


if __name__ == "__main__":
    unittest.main()
