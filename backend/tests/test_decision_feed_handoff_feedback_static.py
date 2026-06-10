"""Static checks for Pulse handoff feedback visibility in the Decision Feed."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCHEDULER = ROOT / "backend" / "scheduler.py"
TYPES = ROOT / "frontend" / "src" / "types" / "index.ts"
DECISION_FEED = ROOT / "frontend" / "src" / "components" / "dashboards" / "DecisionFeed.tsx"
README = ROOT / "README.md"


class DecisionFeedHandoffFeedbackStaticTests(unittest.TestCase):
    def test_scheduler_attaches_structured_handoff_result_to_decision_entries(self):
        text = SCHEDULER.read_text(encoding="utf-8")

        self.assertIn("async def _handoff_to_pulse_with_feedback", text)
        self.assertIn("handoff_result: Dict[str, Any] = {", text)
        self.assertIn("handoff_result = await self._handoff_to_pulse_with_feedback(", text)
        self.assertIn('"handoff_sent": handoff_sent', text)
        self.assertIn('"handoff_status": handoff_result.get("status")', text)
        self.assertIn('"handoff_reason": handoff_result.get("reason")', text)
        self.assertIn('"pulse_feedback": handoff_result', text)

    def test_decision_feed_surfaces_pulse_feedback_summary(self):
        types = TYPES.read_text(encoding="utf-8")
        feed = DECISION_FEED.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")

        self.assertIn("export interface PulseFeedback", types)
        self.assertIn("pulse_feedback?: PulseFeedback", types)
        self.assertIn("handoff_status?: string", types)
        self.assertIn("handoff_reason?: string", types)
        self.assertIn("formatPulseDecisionFeedback", feed)
        self.assertIn("entry.handoff_status", feed)
        self.assertIn("entry.pulse_feedback", feed)
        self.assertIn("Pulse", feed)
        self.assertIn("Decision Feed Pulse feedback visibility", readme)


if __name__ == "__main__":
    unittest.main()
