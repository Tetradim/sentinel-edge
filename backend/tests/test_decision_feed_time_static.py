"""Static checks for shared Decision Feed time formatting."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
DECISION_FEED = ROOT / "frontend" / "src" / "components" / "dashboards" / "DecisionFeed.tsx"
TIME_UTIL = ROOT / "frontend" / "src" / "lib" / "time.ts"


class DecisionFeedTimeStaticTests(unittest.TestCase):
    def test_decision_feed_uses_shared_compact_age_formatter(self):
        text = DECISION_FEED.read_text(encoding="utf-8")

        self.assertIn("import { formatCompactAge } from '@/lib/time'", text)
        self.assertIn("{formatCompactAge(entry.timestamp)}", text)
        self.assertNotIn("function timeAgo", text)

    def test_compact_age_formatter_handles_invalid_and_future_timestamps(self):
        text = TIME_UTIL.read_text(encoding="utf-8")

        self.assertIn("export function formatCompactAge(iso: string | null | undefined)", text)
        self.assertIn("if (Number.isNaN(then)) return 'unknown'", text)
        self.assertIn("Math.max(0, Math.floor((Date.now() - then) / 1000))", text)
        self.assertIn("return `${Math.floor(seconds / 86400)}d ago`", text)


if __name__ == "__main__":
    unittest.main()
