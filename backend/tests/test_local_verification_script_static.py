"""Static checks for the local verification script."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
VERIFY_SCRIPT = ROOT / "scripts" / "verify-local.ps1"
README = ROOT / "README.md"
GITIGNORE = ROOT / ".gitignore"


class LocalVerificationScriptStaticTests(unittest.TestCase):
    def test_script_runs_current_backend_and_frontend_gates(self):
        script = VERIFY_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("backend\\.venv\\Scripts\\python.exe", script)
        self.assertIn("requirements-dev.txt", script)
        self.assertIn("[switch]$InstallFrontendDeps", script)
        self.assertIn("[string]$SummaryPath", script)
        self.assertIn("Add-VerificationResult", script)
        self.assertIn("Add-VerificationSkipped", script)
        self.assertIn("Write-VerificationSummary", script)
        self.assertIn("ConvertTo-Json -Depth 5", script)
        self.assertIn("verification summary written", script)
        self.assertIn("npm ci", script)
        self.assertIn("npm install", script)
        self.assertIn("Test-Path (Join-Path $Frontend \"node_modules\")", script)
        self.assertIn("frontend node_modules are missing", script)
        self.assertIn("-m unittest discover -s backend/tests", script)
        self.assertIn('-m unittest discover -s backend/tests -p "test_*static.py"', script)
        self.assertIn("npm run lint", script)
        self.assertIn("npm run build", script)
        self.assertIn("npm audit --audit-level=moderate", script)
        self.assertIn("git diff --check", script)

    def test_readme_points_to_one_command_local_verification(self):
        readme = README.read_text(encoding="utf-8")

        self.assertIn(".\\scripts\\verify-local.ps1", readme)
        self.assertIn(".\\scripts\\verify-local.ps1 -InstallBackendDevDeps", readme)
        self.assertIn(".\\scripts\\verify-local.ps1 -InstallBackendDevDeps -InstallFrontendDeps", readme)
        self.assertIn(".\\scripts\\verify-local.ps1 -SummaryPath .\\verification-summary.json", readme)

    def test_local_summary_artifact_is_gitignored(self):
        gitignore = GITIGNORE.read_text(encoding="utf-8")

        self.assertIn("verification-summary.json", gitignore)


if __name__ == "__main__":
    unittest.main()
