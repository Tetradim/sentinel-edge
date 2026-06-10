"""Static checks for readiness-aware protection controls."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
PROTECTION = ROOT / "frontend" / "src" / "components" / "dashboards" / "ProtectionDashboard.tsx"


class ProtectionReadinessGuardStaticTests(unittest.TestCase):
    def test_protection_dashboard_fetches_and_surfaces_readiness(self):
        text = PROTECTION.read_text(encoding="utf-8")

        self.assertIn("type NormalizedEdgeReadiness", text)
        self.assertIn("ready: NormalizedEdgeReadiness | null", text)
        self.assertNotIn("ready: any | null", text)
        self.assertIn("api.getReadiness()", text)
        self.assertIn("protection-readiness-guard", text)
        self.assertIn("readinessDetails", text)
        self.assertIn("failingReadinessDetails", text)
        self.assertIn("state.ready?.failing_check_details ?? []", text)
        self.assertIn("state.ready?.check_details ?? {}", text)
        self.assertNotIn("Array.isArray(state.ready?.failing_check_details)", text)
        self.assertNotIn("typeof state.ready.check_details === 'object'", text)
        self.assertNotIn("readinessFailures.map((check)", text)
        self.assertNotIn("readinessDetails[check] || {", text)
        self.assertIn("detail.label", text)
        self.assertIn("title={detail.description || detail.name}", text)
        self.assertIn("Readiness blockers", text)
        self.assertIn("protection-readiness-checks", text)
        self.assertIn("Object.entries(readinessChecks).map(([check, ok])", text)
        self.assertIn("const detail = readinessDetails[check]", text)
        self.assertIn("{detail.label}: {ok ? 'ok' : 'blocked'}", text)

    def test_unknown_readiness_copy_is_explicit(self):
        text = PROTECTION.read_text(encoding="utf-8")

        self.assertIn("const readinessGuardTitle = state.ready", text)
        self.assertIn("'Readiness unavailable'", text)
        self.assertIn("const readinessGuardMessage = state.ready", text)
        self.assertIn("'Unable to confirm Edge runtime readiness.", text)
        self.assertIn("const readinessCheckedAt = formatAge(state.ready?.timestamp || null)", text)
        self.assertIn("Readiness checked", text)
        self.assertIn("{readinessCheckedAt}", text)
        self.assertIn("{readinessGuardTitle}", text)
        self.assertIn("{readinessGuardMessage}", text)

    def test_paper_handoff_is_disabled_when_runtime_not_ready(self):
        text = PROTECTION.read_text(encoding="utf-8")

        self.assertIn("runtimeReady", text)
        self.assertIn("handoffBlocked", text)
        self.assertIn("disabled={busyAction === 'automation' || handoffBlocked}", text)
        self.assertIn("Edge runtime must be ready before enabling paper handoff.", text)


if __name__ == "__main__":
    unittest.main()
