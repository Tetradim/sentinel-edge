"""Static checks for low-cardinality automation handoff metrics."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
METRICS = ROOT / "backend" / "metrics.py"
AUTOMATION = ROOT / "backend" / "automation.py"
RULES = ROOT / "prometheus" / "rules.yml"


class AutomationHandoffMetricsStaticTests(unittest.TestCase):
    def test_metric_uses_bounded_labels(self):
        text = METRICS.read_text(encoding="utf-8")
        start = text.index("edge_automation_handoffs_total")
        metric_block = text[start:text.index(")", start) + 1]

        self.assertIn("edge_automation_handoffs_total", metric_block)
        self.assertIn('["action", "mode", "result", "reason"]', metric_block)
        self.assertNotIn('"symbol"', metric_block)

    def test_automation_records_sent_failed_rejected_and_suppressed_results(self):
        text = AUTOMATION.read_text(encoding="utf-8")

        self.assertIn("edge_automation_handoffs_total", text)
        self.assertIn('"sent" if accepted else "failed"', text)
        self.assertIn('"sent" if status == "accepted" else status', text)
        self.assertIn('_record_handoff_metric(command, "suppressed", reason)', text)
        self.assertIn('.replace(":", "_")', text)
        self.assertIn('sent.get("reason")', text)
        self.assertIn('sent.get("rejection_reason")', text)

    def test_handoff_outcomes_have_recording_rule(self):
        text = RULES.read_text(encoding="utf-8")

        self.assertIn("automation_observability_rules", text)
        self.assertIn("edge_automation_handoffs:rate5m", text)
        self.assertIn(
            "sum by (action, mode, result, reason) (rate(edge_automation_handoffs_total[5m]))",
            text,
        )


if __name__ == "__main__":
    unittest.main()
