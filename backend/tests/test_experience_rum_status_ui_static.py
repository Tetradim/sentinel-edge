"""Static checks for backend RUM ingest visibility in the Experience dashboard."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
EXPERIENCE = ROOT / "frontend" / "src" / "components" / "dashboards" / "ExperienceDashboard.tsx"
README = ROOT / "README.md"


class ExperienceRumStatusUiStaticTests(unittest.TestCase):
    def test_dashboard_polls_backend_rum_status(self):
        text = EXPERIENCE.read_text(encoding="utf-8")

        self.assertIn("loadFrontendRumStatus", text)
        self.assertIn("api.getFrontendRumStatus()", text)
        self.assertIn("setInterval(loadFrontendRumStatus, 30000)", text)

    def test_dashboard_surfaces_backend_rum_freshness(self):
        text = EXPERIENCE.read_text(encoding="utf-8")

        self.assertIn("Backend RUM", text)
        self.assertIn("Backend samples", text)
        self.assertIn("Routes monitored", text)
        self.assertIn("Freshness", text)
        self.assertIn("backendStatus?.sample_count", text)
        self.assertIn("backendStatus?.route_count", text)
        self.assertIn("formatRumFreshness", text)
        self.assertIn("import { formatElapsedAge } from '@/lib/time'", text)
        self.assertIn("formatElapsedAge(backendStatus.seconds_since_last)", text)
        self.assertNotIn("function formatAge(value?: number | null)", text)

    def test_copy_prometheus_reports_clipboard_failures(self):
        text = EXPERIENCE.read_text(encoding="utf-8")

        self.assertIn("const [copyFailed, setCopyFailed] = useState(false)", text)
        self.assertIn("try {", text)
        self.assertIn("await navigator.clipboard.writeText(toPrometheusText(snapshot))", text)
        self.assertIn("catch", text)
        self.assertIn("setCopyFailed(true)", text)
        self.assertIn("Copy failed", text)

    def test_experience_dashboard_exposes_observability_panels(self):
        text = EXPERIENCE.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")

        self.assertIn("OBSERVABILITY_PANEL_CARDS", text)
        self.assertIn("Observability Panels", text)
        self.assertIn("Prometheus expression", text)
        self.assertIn("Runbook", text)
        self.assertIn("edge_frontend_web_vital_value", text)
        self.assertIn("edge_frontend_rum_last_received_timestamp_seconds", text)
        self.assertIn("edge_rate_limit_rejections_total", text)
        self.assertIn("edge_rate_limit_active_buckets", text)
        self.assertIn("docs/runbooks/frontend-core-web-vitals.md", text)
        self.assertIn("docs/runbooks/frontend-rum-ingest-missing.md", text)
        self.assertIn("docs/runbooks/api-rate-limit-rejections.md", text)
        self.assertIn("docs/runbooks/api-rate-limit-bucket-pressure.md", text)
        self.assertIn("formatObservabilityPanelValue", text)
        self.assertIn("Grafana-style observability panels inside Experience", readme)


if __name__ == "__main__":
    unittest.main()
