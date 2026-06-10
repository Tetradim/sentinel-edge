"""Static checks for the installer workflow quality gate."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
BUILD_WORKFLOW = ROOT / ".github" / "workflows" / "build.yml"


class BuildWorkflowQualityGateStaticTests(unittest.TestCase):
    def test_build_workflow_runs_local_verification_before_packaging(self):
        text = BUILD_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("quality-gate:", text)
        self.assertIn("name: Quality Gate", text)
        self.assertIn("runs-on: windows-latest", text)
        self.assertIn("python -m venv backend/.venv", text)
        self.assertIn("npm ci", text)
        self.assertIn("scripts\\verify-local.ps1 -InstallBackendDevDeps", text)
        self.assertIn("needs: quality-gate", text)
        self.assertLess(text.index("quality-gate:"), text.index("build:"))

    def test_build_workflow_quality_gate_runs_on_dependency_and_script_changes(self):
        text = BUILD_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("'backend/requirements-dev.txt'", text)
        self.assertIn("'frontend/package-lock.json'", text)
        self.assertIn("'scripts/**'", text)


if __name__ == "__main__":
    unittest.main()
