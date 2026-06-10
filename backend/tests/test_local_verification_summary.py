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

        statuses = {entry["name"]: entry["status"] for entry in summary["results"]}

        self.assertEqual(summary["status"], "passed")
        self.assertEqual(statuses["Backend verification"], "skipped")
        self.assertEqual(statuses["Frontend verification"], "skipped")
        self.assertEqual(statuses["Workspace whitespace check: git diff --check"], "passed")


if __name__ == "__main__":
    unittest.main()
