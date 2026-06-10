"""Static checks for handoff outcome visibility in Protection dashboard."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
PROTECTION = ROOT / "frontend" / "src" / "components" / "dashboards" / "ProtectionDashboard.tsx"


class ProtectionHandoffStatusStaticTests(unittest.TestCase):
    def test_protection_dashboard_surfaces_last_handoff_and_suppression(self):
        text = PROTECTION.read_text(encoding="utf-8")

        self.assertIn("last_handoff", text)
        self.assertIn("last_suppressed", text)
        self.assertIn("Latest handoff", text)
        self.assertIn("Latest suppression", text)
        self.assertIn("suppressed_reason", text)
        self.assertIn("HandoffEventCard", text)
        self.assertIn("formatHandoffTime", text)

    def test_failed_handoff_is_visually_distinct(self):
        text = PROTECTION.read_text(encoding="utf-8")

        self.assertIn("handoff.sent === false", text)
        self.assertIn("Delivery failed", text)
        self.assertIn("border-red-500/30", text)

    def test_guarded_actions_surface_operator_errors(self):
        text = PROTECTION.read_text(encoding="utf-8")

        self.assertIn("const [actionError, setActionError] = useState<string | null>(null)", text)
        self.assertIn("setActionError(null)", text)
        self.assertIn("catch (err)", text)
        self.assertIn("setActionError(err instanceof Error ? err.message : 'Protection action failed')", text)
        self.assertIn("{actionError &&", text)
        self.assertIn("{actionError}", text)


if __name__ == "__main__":
    unittest.main()
