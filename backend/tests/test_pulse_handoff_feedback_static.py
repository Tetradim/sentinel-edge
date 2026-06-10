"""Static checks for structured Pulse handoff feedback plumbing."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
PULSE_CLIENT = ROOT / "backend" / "pulse_client.py"
SCHEDULER = ROOT / "backend" / "scheduler.py"
AUTOMATION = ROOT / "backend" / "automation.py"


class PulseHandoffFeedbackStaticTests(unittest.TestCase):
    def test_pulse_client_returns_structured_handoff_feedback(self):
        text = PULSE_CLIENT.read_text(encoding="utf-8")

        self.assertIn("PulseHandoffRequest", text)
        self.assertIn("invalid_handoff_contract", text)
        self.assertIn("Idempotency-Key", text)
        self.assertIn("X-Edge-Mode", text)
        self.assertIn("X-Edge-Contract-Version", text)
        self.assertIn("def normalise_handoff_feedback", text)
        self.assertIn("async def _post_with_feedback", text)
        self.assertIn('"status": "accepted"', text)
        self.assertIn('"status": "rejected"', text)
        self.assertIn('"status": "failed"', text)
        self.assertIn("legacy_handoff_payload", text)

    def test_scheduler_records_structured_handoff_feedback(self):
        text = SCHEDULER.read_text(encoding="utf-8")

        self.assertIn("handoff_result = await self.pulse.send_handoff_command(command.payload())", text)
        self.assertIn("self.automation.record_sent(command, handoff_result)", text)
        self.assertIn('handoff_result.get("sent", False)', text)

    def test_automation_status_preserves_pulse_feedback(self):
        text = AUTOMATION.read_text(encoding="utf-8")

        self.assertIn("pulse_feedback", text)
        self.assertIn("handoff_status", text)
        self.assertIn('metric_result = "sent" if status == "accepted" else status', text)


if __name__ == "__main__":
    unittest.main()
