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

    def test_pulse_feedback_is_visible_on_handoff_cards(self):
        text = PROTECTION.read_text(encoding="utf-8")

        self.assertIn("handoff.handoff_status", text)
        self.assertIn("handoff.pulse_feedback", text)
        self.assertIn("Pulse:", text)
        self.assertIn("pulse_feedback.reason", text)
        self.assertIn("Pulse handoff id", text)
        self.assertIn("HTTP status", text)
        self.assertIn("Legacy fallback", text)
        self.assertIn("Primary endpoint", text)
        self.assertIn("pulse_feedback.response.handoff_id", text)
        self.assertIn("pulse_feedback.status_code", text)
        self.assertIn("pulse_feedback.legacy_fallback", text)
        self.assertIn("pulse_feedback.primary_feedback", text)

    def test_guarded_actions_surface_operator_errors(self):
        text = PROTECTION.read_text(encoding="utf-8")

        self.assertIn("const [actionError, setActionError] = useState<string | null>(null)", text)
        self.assertIn("setActionError(null)", text)
        self.assertIn("catch (err)", text)
        self.assertIn("setActionError(err instanceof Error ? err.message : 'Protection action failed')", text)
        self.assertIn("{actionError &&", text)
        self.assertIn("{actionError}", text)

    def test_protection_dashboard_surfaces_partial_refresh_failures(self):
        text = PROTECTION.read_text(encoding="utf-8")

        self.assertIn("const failedLoads = [health, stats, ready, pulse, killSwitch, automation, positions, queue].filter", text)
        self.assertIn("setState((prev) => ({", text)
        self.assertIn("error: failedLoads.length > 0 ? 'Protection data failed to refresh. Showing latest available data.' : null", text)
        self.assertIn("health: health.status === 'fulfilled' ? health.value : prev.health", text)
        self.assertIn("ready: ready.status === 'fulfilled' ? ready.value : prev.ready", text)
        self.assertIn("positions: positions.status === 'fulfilled' ? normalizePositions(positions.value) : prev.positions", text)
        self.assertIn("{state.error &&", text)
        self.assertIn('role="alert"', text)


if __name__ == "__main__":
    unittest.main()
