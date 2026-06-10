"""Static checks for the local verification script."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
VERIFY_SCRIPT = ROOT / "scripts" / "verify-local.ps1"
README = ROOT / "README.md"


class LocalVerificationScriptStaticTests(unittest.TestCase):
    def test_script_runs_current_backend_and_frontend_gates(self):
        script = VERIFY_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("backend\\.venv\\Scripts\\python.exe", script)
        self.assertIn("requirements-dev.txt", script)
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


if __name__ == "__main__":
    unittest.main()
