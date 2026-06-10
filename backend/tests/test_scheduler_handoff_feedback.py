"""Behavior tests for scheduler-level Pulse handoff feedback propagation."""
import asyncio
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from automation import (  # noqa: E402
    AutomationAction,
    AutomationController,
    AutomationMode,
    AutomationSettings,
)
from scheduler import EvaluationScheduler  # noqa: E402


class FakeMarketHours:
    def __init__(self, open_: bool = True, reason: str = "regular_session"):
        self.open = open_
        self.reason = reason

    def get_market_for_symbol(self, symbol: str) -> str:
        return "NYSE"

    def market_status(self, market: str) -> dict:
        return {"market": market, "open": self.open, "reason": self.reason}


class FakePulseClient:
    def __init__(self, result: dict):
        self.result = result
        self.payloads = []

    async def send_handoff_command(self, payload: dict) -> dict:
        self.payloads.append(payload)
        return self.result


class SchedulerHandoffFeedbackTests(unittest.TestCase):
    def _scheduler(self, *, pulse_result: dict, market_open: bool = True) -> EvaluationScheduler:
        scheduler = object.__new__(EvaluationScheduler)
        scheduler.pulse = FakePulseClient(pulse_result)
        scheduler.market_hours = FakeMarketHours(open_=market_open, reason="after_close")
        scheduler.automation = AutomationController(
            settings=AutomationSettings(
                global_enabled=True,
                mode=AutomationMode.PAPER,
                default_ticker_enabled=True,
                min_confidence=0.1,
                cooldown_seconds=0,
            ),
            state_path=Path("unused.json"),
        )
        return scheduler

    def test_handoff_feedback_helper_preserves_pulse_rejection_for_decision_feed(self):
        scheduler = self._scheduler(
            pulse_result={
                "sent": False,
                "status": "rejected",
                "reason": "risk_limit",
                "endpoint": "/api/edge/handoff",
                "status_code": 200,
            }
        )

        result = asyncio.run(
            scheduler._handoff_to_pulse_with_feedback(
                symbol="aapl",
                action=AutomationAction.BUY,
                confidence=0.8,
                reason="test signal",
                orb_session="market_open",
            )
        )

        self.assertFalse(result["sent"])
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["reason"], "risk_limit")
        self.assertEqual(scheduler.automation.last_handoff["handoff_status"], "rejected")
        self.assertEqual(scheduler.automation.last_handoff["pulse_feedback"]["reason"], "risk_limit")
        self.assertEqual(scheduler.pulse.payloads[0]["symbol"], "AAPL")

    def test_handoff_feedback_helper_returns_suppressed_market_context(self):
        scheduler = self._scheduler(pulse_result={"sent": True, "status": "accepted"}, market_open=False)

        result = asyncio.run(
            scheduler._handoff_to_pulse_with_feedback(
                symbol="SPY",
                action=AutomationAction.EMERGENCY_EXIT,
                confidence=0.95,
                reason="risk threshold",
            )
        )

        self.assertFalse(result["sent"])
        self.assertEqual(result["status"], "suppressed")
        self.assertEqual(result["reason"], "market_closed:after_close")
        self.assertEqual(result["market_status"]["reason"], "after_close")
        self.assertEqual(len(scheduler.pulse.payloads), 0)
        self.assertEqual(scheduler.automation.last_suppressed["suppressed_reason"], "market_closed:after_close")


if __name__ == "__main__":
    unittest.main()
