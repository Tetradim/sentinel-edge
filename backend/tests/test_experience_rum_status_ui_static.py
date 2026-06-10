"""Static checks for backend RUM ingest visibility in the Experience dashboard."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
EXPERIENCE = ROOT / "frontend" / "src" / "components" / "dashboards" / "ExperienceDashboard.tsx"


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


if __name__ == "__main__":
    unittest.main()
