"""Static checks for frontend live/ready runtime visibility."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "frontend" / "src" / "lib" / "api.ts"
ADVISOR_HEALTH = ROOT / "frontend" / "src" / "components" / "dashboards" / "AdvisorHealth.tsx"


class FrontendReadinessUiStaticTests(unittest.TestCase):
    def test_api_client_exposes_live_and_ready_endpoints(self):
        text = API.read_text(encoding="utf-8")

        self.assertIn("export interface EdgeLiveness", text)
        self.assertIn("export interface EdgeReadinessCheckDetail", text)
        self.assertIn("export interface EdgeReadiness", text)
        self.assertIn("failing_checks: string[]", text)
        self.assertIn("failing_check_details?: EdgeReadinessCheckDetail[]", text)
        self.assertIn("check_details?: Record<string, EdgeReadinessCheckDetail>", text)
        self.assertIn("async getLiveness()", text)
        self.assertIn("fetchJSON<EdgeLiveness>('/api/live')", text)
        self.assertIn("async getReadiness()", text)
        self.assertIn("normalizeEdgeReadiness(await fetchJSON<EdgeReadiness>('/api/ready'))", text)
        self.assertIn("return normalizeEdgeReadiness(err.detail)", text)
        self.assertIn("function normalizeEdgeReadiness(readiness: EdgeReadiness): EdgeReadiness", text)
        self.assertIn("const failingChecks = Array.isArray(readiness.failing_checks)", text)
        self.assertIn("failingChecks.map((check)", text)
        self.assertIn("failing_checks: failingChecks", text)
        self.assertIn("failing_check_details: failingCheckDetails", text)
        self.assertIn("err instanceof ApiError && err.status === 503", text)

    def test_advisor_health_surfaces_runtime_readiness(self):
        text = ADVISOR_HEALTH.read_text(encoding="utf-8")

        self.assertIn("type EdgeLiveness", text)
        self.assertIn("type EdgeReadiness", text)
        self.assertIn("live: EdgeLiveness | null", text)
        self.assertIn("ready: EdgeReadiness | null", text)
        self.assertNotIn("live: any | null", text)
        self.assertNotIn("ready: any | null", text)
        self.assertIn("api.getLiveness()", text)
        self.assertIn("api.getReadiness()", text)
        self.assertIn("Runtime Readiness", text)
        self.assertIn("readinessDetails", text)
        self.assertIn("failingReadinessDetails", text)
        self.assertIn("state.ready?.failing_check_details", text)
        self.assertIn("state.ready?.check_details", text)
        self.assertNotIn("readinessFailures.map((check)", text)
        self.assertIn("detail.label", text)
        self.assertIn("title={detail.description || detail.name}", text)
        self.assertIn("edge-readiness-checks", text)
        self.assertIn("failing readiness checks", text)


if __name__ == "__main__":
    unittest.main()
