"""Behavior checks for the local verification summary artifact."""
import json
import subprocess
import tempfile
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
VERIFY_SCRIPT = ROOT / "scripts" / "verify-local.ps1"


class LocalVerificationSummaryTests(unittest.TestCase):
    def test_summary_records_explicitly_skipped_backend_and_frontend_gates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            summary_path = Path(temp_dir) / "verification-summary.json"
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(VERIFY_SCRIPT),
                    "-SkipBackend",
                    "-SkipFrontend",
                    "-SummaryPath",
                    str(summary_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))

        entries = {entry["name"]: entry for entry in summary["results"]}
        statuses = {name: entry["status"] for name, entry in entries.items()}

        self.assertEqual(summary["status"], "passed")
        self.assertEqual(
            summary["counts"],
            {
                "total": 3,
                "passed": 1,
                "failed": 0,
                "skipped": 2,
            },
        )
        self.assertEqual(statuses["Backend verification"], "skipped")
        self.assertEqual(statuses["Frontend verification"], "skipped")
        self.assertEqual(statuses["Workspace whitespace check: git diff --check"], "passed")
        self.assertEqual(entries["Backend verification"]["reason"], "-SkipBackend was supplied")
        self.assertEqual(entries["Frontend verification"]["reason"], "-SkipFrontend was supplied")
        self.assertIsNone(entries["Workspace whitespace check: git diff --check"]["reason"])


if __name__ == "__main__":
    unittest.main()
